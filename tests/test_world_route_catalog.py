"""Local review catalog behavior; all fixtures are invented and offline."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.world_candidate_review import content_id, IDENTITY_FIELDS
from rift_taxi.world_review_package import create_package
from rift_taxi.world_route_catalog import select_route,SCHEMA
from test_world_candidate_review import fixture


class CatalogTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.path=self.root/"catalog.json"
        self.rows=[]
        self.add("alpha",fixture())
        self.scope={"destination_id":"destination","source_world":"synthetic",
                    "frame_sha256":self.rows[0]["frameSHA256"],"patch_id":"a"*64,
                    "start_xyz":[0,0,0],"max_start_xz":.5,"max_start_y":.1,
                    "max_snap_xz":.5,"max_snap_y":.1}

    def add(self,name,doc):
        ident={k:doc[k] for k in IDENTITY_FIELDS}
        ident["plannerResult"]=doc["plannerResult"]
        doc["candidateId"]=content_id(ident)
        src=self.root/"source.json"
        raw=json.dumps(doc).encode()
        src.write_bytes(raw)
        pkg=create_package(src,expected_sha256=hashlib.sha256(raw).hexdigest(),source_commit="c"*40)
        filename=name+".json"
        (self.root/filename).write_text(json.dumps(pkg),encoding="utf-8")
        self.rows.append({"routeId":name,"destinationId":"destination","packageFile":filename,
                          "packageId":pkg["packageId"],"sourceWorld":doc["world"]["sourceWorld"],
                          "frameSHA256":content_id(doc["coordinates"]),"patchId":doc["patchId"],
                          "destinationXYZ":doc["query"]["requestedGoalXYZ"]})

    def select(self,**changes):
        raw=json.dumps({"schema":SCHEMA,"entries":self.rows}).encode()
        self.path.write_bytes(raw)
        opts={**self.scope,"catalog_sha256":hashlib.sha256(raw).hexdigest(),**changes}
        return select_route(self.path,**opts)

    def test_select_exact_scope_and_preserve_review_only(self):
        r=self.select()
        self.assertEqual(r["status"],"review-path-selected")
        self.assertEqual(r["selected"]["routeId"],"alpha")
        self.assertEqual(r["selected"]["pathLength3D"],4.)
        for k in ("connectorVerified","physicalQualification","productionInputAuthorized","gameInputSent"):
            self.assertIs(r[k],False)

    def test_scope_mismatch_does_not_open_unrelated_package(self):
        (self.root/"alpha.json").unlink()
        for kw in ({"patch_id":"d"*64},{"frame_sha256":"e"*64},
                   {"source_world":"other"},{"destination_id":"other"}):
            r=self.select(**kw)
            self.assertIsNone(r["selected"])

    def test_start_and_snap_thresholds_independent(self):
        r=self.select(start_xyz=[0,.2,0])
        self.assertEqual(r["excluded"][0]["reason"],"start-offset-exceeds-limit")
        doc=fixture()
        # Keep the same requested destination; only the projected endpoint
        # differs, so this is a valid alternative for catalog comparison.
        for target in (doc["query"],doc["plannerResult"]):
            target["snappedGoalXYZ"]=[4,2,0]
        doc["points"][-1]["xyz"]=[4,2,0]
        doc["plannerResult"]["waypoints"][-1]["pos"]=[4,2,0]
        self.add("large-snap",doc)
        r=self.select()
        self.assertEqual(r["selected"]["routeId"],"alpha")
        self.assertEqual(r["excluded"],[{"routeId":"large-snap","reason":"endpoint-snap-exceeds-limit"}])

    def test_deterministic_order_and_distance_rank(self):
        doc=fixture()
        doc["points"].insert(1,{"id":"bend","xyz":[2,0,3],"flags":0})
        doc["plannerResult"]["waypoints"].insert(1,{"pos":[2,0,3],"flags":0})
        self.add("longer",doc)
        doc=fixture()
        doc["createdAtUtc"]="different retained source bytes"
        self.add("zeta",doc)
        self.assertEqual(self.select()["selected"]["routeId"],"alpha")
        self.rows.reverse()
        self.assertEqual(self.select()["selected"]["routeId"],"alpha")

    def test_corrupt_matching_package_aborts_even_with_valid_alternate(self):
        doc=fixture()
        doc["createdAtUtc"]="alternate"
        self.add("alternate",doc)
        (self.root/"alternate.json").write_text("{}",encoding="utf-8")
        with self.assertRaises(TraceError):
            self.select()

    def test_wrong_catalog_pin_and_malicious_filename(self):
        with self.assertRaisesRegex(TraceError,"catalog SHA mismatch"):
            self.select(catalog_sha256="0"*64)
        for bad in ("../alpha.json","C:alpha.json","con.json","ALPHA.json","a/b.json"):
            self.rows[0]["packageFile"]=bad
            with self.subTest(bad=bad),self.assertRaisesRegex(TraceError,"filename"):
                self.select()

    def test_relabelled_scope_refused_after_valid_package_pin(self):
        self.rows[0]["patchId"]="d"*64
        with self.assertRaisesRegex(TraceError,"scope mismatch"):
            self.select(patch_id="d"*64)

    def test_duplicate_identity_and_numeric_alias_refused(self):
        with self.assertRaises(TraceError):
            self.select(max_start_y=True)
        self.rows.append(deepcopy(self.rows[0]))
        with self.assertRaisesRegex(TraceError,"duplicate"):
            self.select()

    def test_same_destination_label_cannot_mix_requested_coordinates(self):
        doc=fixture()
        for target in (doc["query"],doc["plannerResult"]):
            target["requestedGoalXYZ"]=[4,1,0]
        self.add("different-goal",doc)
        with self.assertRaisesRegex(TraceError,"contradictory destination"):
            self.select()

    def test_forged_destination_binding_rejected_even_with_correct_package_pin(self):
        self.rows[0]["destinationXYZ"]=[4,1,0]
        with self.assertRaisesRegex(TraceError,"requested destination mismatch"):
            self.select()
