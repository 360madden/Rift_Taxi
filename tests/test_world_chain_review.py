"""Constructed scene chain and explicit opaque payloads; no sibling access."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from rift_taxi.contracts import TraceError
from rift_taxi.world_candidate_review import content_id, IDENTITY_FIELDS
from rift_taxi.world_chain_review import audit_chain, BUILD_FIELDS
from test_world_candidate_review import fixture


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class ChainTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.paths={k:self.root/k for k in ("geometry","scene","navmesh","preparedObj")}
        for role,path in self.paths.items():
            if role!="scene":
                path.write_bytes(("synthetic "+role).encode())
        self.c=fixture()
        coord=self.c["coordinates"]
        bounds=[-1,-1,-1,5,1,1]
        coverage={"kind":"scene-request-selection","sourceRequestBounds":[bounds],
                  "navigationEligible":True,"transformConflicts":[],"qualification":"partial synthetic",
                  "sceneCoverage":{"state":"partial","modelStates":[{"key":"m","state":"available"}],
                                   "recordStates":[{"key":"r","state":"selected"}]}}
        self.scene={"schema":"riftworld.scene/1","sceneId":"e"*64,
                    "coordinates":coord,"sourceWorld":{"key":"synthetic","authority":"fixture"},
                    "counts":{"models":1},"coverage":coverage["sceneCoverage"],
                    "requestSelection":{"areaRequest":{"boundsXZ":{"min":[-1,-1],"max":[5,1]},
                        "verticalSelection":{"minY":-1,"maxY":1},
                        "coordinateFrame":coord,"sourceWorld":{"key":"synthetic","authority":"fixture"}}}}
        self.paths["scene"].write_text(json.dumps(self.scene),encoding="utf-8")
        def ref(k):
            return {"path":"intentionally-not-followed/"+k,"sha256":digest(self.paths[k].read_bytes()).upper()}
        self.p={"schema":"riftworld.patch/1","sourceWorld":"synthetic","coordinates":coord,
                "content":{"geometrySha256":ref("geometry")["sha256"],
                           "sceneManifestSha256":ref("scene")["sha256"],"sceneId":"e"*64},
                "coverage":coverage,"source":{"provider":"riftworld-scene","sceneId":"e"*64,
                  "sceneSchema":"riftworld.scene/1","sourceWorldAuthority":"fixture",
                  "offlineCandidatePermission":"explicit-partial-diagnostic"},
                "counts":{"models":1},"evidence":{**self.c["evidence"],"walkability":"unbuilt"},
                "files":{k:ref(k) for k in ("geometry","scene")}}
        self.b={"schema":"riftworld.navigation-build/1","sourceObjSha256":self.p["content"]["geometrySha256"],
                "bounds":bounds,"profile":{"agent_radius":.5},"pipelineRevision":"f"*40,
                "dependencies":{},"builderVersion":"fixture","sourceRequestBounds":[bounds],
                "files":{k:ref(k) for k in ("navmesh","preparedObj")}}
        self.rebind()

    def rebind(self):
        self.p["patchId"]=content_id({k:self.p[k] for k in ("sourceWorld","coordinates","content","coverage")})
        self.b["worldContext"]={"patchId":self.p["patchId"],"sourceWorld":self.p["sourceWorld"],
                                "coordinates":self.p["coordinates"]}
        self.b["buildId"]=self.b["cacheKey"]=content_id({k:self.b[k] for k in BUILD_FIELDS}).upper()
        self.c["patchId"]=self.p["patchId"]
        self.c["planner"]={k:self.b[k] for k in ("buildId","bounds","profile","pipelineRevision")}
        self.c["plannerResult"]["cacheKey"]=self.b["buildId"]
        cov=self.p["coverage"]
        self.c["evidence"]={**self.p["evidence"],"walkability":"estimated",
                "sourceRequestCoverage":{"schema":"riftworld.source-request-coverage-summary/1",
                  "patchId":self.p["patchId"],"kind":cov["kind"],"coverageSha256":content_id(cov),
                  "sourceRequestBounds":cov["sourceRequestBounds"],"navigationEligible":True,
                  "transformConflictCount":0,"qualification":cov["qualification"],
                  "sceneCoverage":{"sceneId":"e"*64,"state":"partial",
                    "modelStateCounts":{"available":1,"missing":0,"unknown":0},
                    "recordStateCounts":{"selected":1,"excluded":0,"unresolved":0}}}}

    def audit(self):
        identity={k:self.c[k] for k in IDENTITY_FIELDS}
        identity["plannerResult"]=self.c["plannerResult"]
        self.c["candidateId"]=content_id(identity)
        paths=[];pins=[]
        for role,doc in (("candidate",self.c),("patch",self.p),("build",self.b)):
            raw=json.dumps(doc).encode()
            path=self.root/(role+".json")
            path.write_bytes(raw)
            paths.append(path);pins.append(digest(raw))
        return audit_chain(*paths,candidate_sha256=pins[0],patch_sha256=pins[1],
            build_sha256=pins[2],source_commit="c"*40,payload_paths=self.paths)

    def test_consistent_chain_preserves_partial_and_false_authority(self):
        r=self.audit()
        self.assertTrue(r["metadataChainConsistent"])
        self.assertTrue(r["retainedPayloadHashesMatched"])
        self.assertEqual(r["coverage"]["sceneCoverage"]["state"],"partial")
        self.assertEqual(set(r["payloads"]),set(self.paths))
        for field in ("sceneFullyValidated","pipelineDependenciesVerified","detourCompatibilityVerified",
                      "transformQualified","endpointConnectorsVerified","physicalQualification",
                      "productionInputAuthorized"):
            self.assertIs(r[field],False)

    def test_payload_hash_mismatch_refused(self):
        self.paths["navmesh"].write_bytes(b"changed")
        with self.assertRaisesRegex(TraceError,"payload SHA mismatch"):
            self.audit()

    def test_build_context_and_identity_mutation_refused(self):
        self.b["worldContext"]["sourceWorld"]="other"
        with self.assertRaisesRegex(TraceError,"build identity"):
            self.audit()

    def test_candidate_coverage_forgery_refused_even_after_rehash(self):
        self.c["evidence"]["sourceRequestCoverage"]["sceneCoverage"]["state"]="declared"
        with self.assertRaisesRegex(TraceError,"candidate evidence"):
            self.audit()

    def test_candidate_leaving_request_box_refused(self):
        self.c["points"].insert(1,{"id":"mid","xyz":[2,2,0],"flags":0})
        self.c["plannerResult"]["waypoints"].insert(1,{"pos":[2,2,0],"flags":0})
        with self.assertRaisesRegex(TraceError,"leaves declared request"):
            self.audit()

    def test_scene_metadata_mismatch_refused_even_if_rehashed(self):
        self.scene["coverage"]=deepcopy(self.scene["coverage"])
        self.scene["coverage"]["state"]="declared"
        self.paths["scene"].write_text(json.dumps(self.scene),encoding="utf-8")
        pin=digest(self.paths["scene"].read_bytes()).upper()
        self.p["content"]["sceneManifestSha256"]=pin
        self.p["files"]["scene"]["sha256"]=pin
        self.rebind()
        with self.assertRaisesRegex(TraceError,"scene coverage"):
            self.audit()
