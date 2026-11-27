"""Source-pinned review of one retained RiftWorld scene/candidate/build chain.

Supports the observed single-region scene-request-selection export. All
input paths are explicit caller arguments. No manifest locators are followed,
no Detour binary is interpreted, no sibling code is imported. Byte and
metadata consistency do not authenticate a producer, validate mesh
traversability, or establish a current live coordinate transform.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from .contracts import TraceError, _read_bounded, _strict_json, _number
from .world_candidate_review import review_bytes, content_id, require, xyz, HEX

MAX_METADATA = 8*1024*1024
MAX_PAYLOAD = 64*1024*1024
SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
BUILD_FIELDS = ("sourceObjSha256","bounds","profile","pipelineRevision",
                "dependencies","builderVersion","worldContext","sourceRequestBounds")
ROLES = ("geometry","scene","navmesh","preparedObj")


def _same(a,b,label):
    # Canonical JSON distinguishes bool from number and integral floats from
    # integers, which are significant in the upstream content-ID algorithm.
    require(content_id(a)==content_id(b),label+" mismatch")


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _pinned(path,pin):
    require(isinstance(pin,str) and HEX.fullmatch(pin),"explicit metadata SHA required")
    raw=_read_bounded(Path(path),MAX_METADATA,"world metadata")
    require(_hash(raw)==pin,"metadata SHA mismatch")
    return raw


def _payload(path,expected):
    require(isinstance(expected,str) and SHA.fullmatch(expected),"invalid payload SHA")
    raw=_read_bounded(Path(path),MAX_PAYLOAD,"world payload")
    actual=_hash(raw)
    require(actual==expected.lower(),"payload SHA mismatch")
    return {"sha256":actual,"bytes":len(raw)}


def _box(value):
    require(isinstance(value,list) and len(value)==6,"invalid XYZ box")
    v=tuple(_number(x,"request bound") for x in value)
    require(all(abs(x)<=1e6 for x in v) and all(v[i]<v[i+3] for i in range(3)),
            "invalid XYZ box extent")
    return v


def _inside(point,bounds):
    p=xyz(point)
    return all(bounds[i]<=p[i]<=bounds[i+3] for i in range(3))


def _counts(rows,states):
    require(isinstance(rows,list),"invalid scene state inventory")
    result={k:0 for k in states}
    for row in rows:
        require(isinstance(row,dict) and set(row)=={"key","state"} and row["key"] is not None
                and row["state"] in states,"invalid scene state record")
        result[row["state"]]+=1
    return result


def _verify(candidate,patch,build,scene,paths):
    require(patch["schema"]=="riftworld.patch/1"
            and build["schema"]=="riftworld.navigation-build/1"
            and scene["schema"]=="riftworld.scene/1","unsupported chain schema")
    identity={k:patch[k] for k in ("sourceWorld","coordinates","content","coverage")}
    require(content_id(identity)==patch["patchId"]==candidate["patchId"],"patch identity mismatch")
    require(content_id({k:build[k] for k in BUILD_FIELDS}).upper()
            ==build["buildId"]==build["cacheKey"]==candidate["planner"]["buildId"],
            "build identity mismatch")
    _same(patch["coordinates"],candidate["coordinates"],"candidate coordinate frame")
    require(candidate["world"]["sourceWorld"]==patch["sourceWorld"],"candidate world mismatch")
    _same(build["worldContext"],{"patchId":patch["patchId"],"sourceWorld":patch["sourceWorld"],
                                 "coordinates":patch["coordinates"]},"build context")
    for key in ("profile","bounds","pipelineRevision"):
        _same(candidate["planner"][key],build[key],"planner "+key)
    content=patch["content"]
    require(build["sourceObjSha256"]==content["geometrySha256"],"build geometry identity mismatch")
    source=patch["source"]
    require(source["provider"]=="riftworld-scene"
            and source["offlineCandidatePermission"]=="explicit-partial-diagnostic",
            "unsupported scene provider or permission")
    require(scene["sceneId"]==content["sceneId"]==source["sceneId"]
            and source["sceneSchema"]==scene["schema"],"scene identity reference mismatch")
    _same(scene["coordinates"],patch["coordinates"],"scene coordinate frame")
    require(scene["sourceWorld"]["key"]==patch["sourceWorld"]
            and scene["sourceWorld"]["authority"]==source["sourceWorldAuthority"],
            "scene world context mismatch")
    _same(scene["counts"],patch["counts"],"scene counts")
    coverage=patch["coverage"]
    require(coverage["kind"]=="scene-request-selection"
            and coverage["navigationEligible"] is True
            and coverage["transformConflicts"]==[],"unsupported or conflicting coverage")
    require(isinstance(coverage["sourceRequestBounds"],list)
            and len(coverage["sourceRequestBounds"])==1,"single request region required")
    bounds=_box(coverage["sourceRequestBounds"][0])
    _same(build["sourceRequestBounds"],coverage["sourceRequestBounds"],"build request bounds")
    _same(scene["coverage"],coverage["sceneCoverage"],"scene coverage")
    request=scene["requestSelection"]["areaRequest"]
    a,b=request["boundsXZ"]["min"],request["boundsXZ"]["max"]
    v=request["verticalSelection"]
    _same([a[0],v["minY"],a[1],b[0],v["maxY"],b[1]],
          coverage["sourceRequestBounds"][0],"scene request region")
    _same(request["sourceWorld"],scene["sourceWorld"],"request world")
    require(all(request["coordinateFrame"].get(k)==scene["coordinates"].get(k)
                for k in ("frameId","axisOrder","upAxis","units","handedness")),
            "request frame mismatch")
    sc=coverage["sceneCoverage"]
    require(sc["state"] in ("declared","partial"),"unsupported scene coverage state")
    require(isinstance(coverage["qualification"],str) and bool(coverage["qualification"]),
            "missing coverage qualification")
    summary={"schema":"riftworld.source-request-coverage-summary/1","patchId":patch["patchId"],
             "kind":coverage["kind"],"coverageSha256":content_id(coverage),
             "sourceRequestBounds":coverage["sourceRequestBounds"],"navigationEligible":True,
             "transformConflictCount":0,"qualification":coverage["qualification"],
             "sceneCoverage":{"sceneId":content["sceneId"],"state":sc["state"],
                 "modelStateCounts":_counts(sc["modelStates"],("available","missing","unknown")),
                 "recordStateCounts":_counts(sc["recordStates"],("selected","excluded","unresolved"))}}
    expected={**patch["evidence"],"walkability":"estimated","sourceRequestCoverage":summary}
    _same(candidate["evidence"],expected,"candidate evidence")
    # A single convex XYZ box contains every straight segment between its
    # contained endpoints. This is request-bound containment only, not a
    # collision check or proof of source completeness.
    require(all(_inside(p["xyz"],bounds) for p in candidate["points"]),
            "route leaves declared request box")
    require(all(_inside(candidate["query"][k],bounds) for k in
                ("requestedStartXYZ","requestedGoalXYZ","snappedStartXYZ","snappedGoalXYZ")),
            "query endpoint outside declared request box")
    require(set(patch["files"])=={"geometry","scene"}
            and set(build["files"])=={"navmesh","preparedObj"},"unsupported payload inventory")
    require(patch["files"]["geometry"]["sha256"]==content["geometrySha256"]
            and patch["files"]["scene"]["sha256"]==content["sceneManifestSha256"],
            "patch payload reference mismatch")
    require(set(paths)==set(ROLES),"explicit payload paths required")
    refs={**patch["files"],**build["files"]}
    # Scene bytes already pinned and parsed by the caller. Do not reopen
    # them; all other payloads are read exactly once and hashed here.
    for ref in refs.values():
        require(isinstance(ref,dict) and set(ref)=={"path","sha256"}
                and isinstance(ref["path"],str) and bool(ref["path"]),"invalid payload reference")
    payloads={k:_payload(paths[k],refs[k]["sha256"]) for k in ROLES if k!="scene"}
    return summary,payloads


def audit_chain(candidate,patch,build,*,candidate_sha256,patch_sha256,build_sha256,
                source_commit,payload_paths):
    """Check exact metadata snapshots and explicitly supplied payload files."""
    try:
        cr=_pinned(candidate,candidate_sha256)
        pr=_pinned(patch,patch_sha256)
        br=_pinned(build,build_sha256)
        review=review_bytes(cr,expected_sha256=candidate_sha256,source_commit=source_commit)
        c,p,b=(_strict_json(raw,"world metadata") for raw in (cr,pr,br))
        require(set(payload_paths)==set(ROLES),"explicit payload paths required")
        sr=_read_bounded(Path(payload_paths["scene"]),MAX_METADATA,"scene metadata")
        expected=p["content"]["sceneManifestSha256"]
        require(isinstance(expected,str) and SHA.fullmatch(expected) and _hash(sr)==expected.lower(),
                "scene payload SHA mismatch")
        scene=_strict_json(sr,"scene metadata")
        coverage,payloads=_verify(c,p,b,scene,payload_paths)
        payloads["scene"]={"sha256":_hash(sr),"bytes":len(sr)}
        return {"schema":"taxi.world-chain-review/1","classification":"OFFLINE_REVIEW_ONLY",
                "source":review["source"],"candidateId":review["candidateId"],
                "patchId":review["patchId"],"buildId":review["buildId"],
                "metadataSHA256":{"candidate":candidate_sha256,"patch":patch_sha256,
                                  "navigation":build_sha256},
                "payloads":payloads,"coverage":coverage,
                "requestBoxContainmentVerified":True,"metadataChainConsistent":True,
                "retainedPayloadHashesMatched":True,
                "sourceAuthenticityEstablished":False,"sceneFullyValidated":False,
                "pipelineDependenciesVerified":False,"detourCompatibilityVerified":False,
                "transformQualified":False,"endpointConnectorsVerified":False,
                "physicalQualification":False,"productionInputAuthorized":False}
    except TraceError:
        raise
    except (KeyError,TypeError,ValueError,AttributeError,IndexError,OverflowError,RecursionError) as exc:
        raise TraceError("world chain: malformed or unsupported metadata") from exc


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for role in ("candidate","patch","build"):
        p.add_argument(role,type=Path)
        p.add_argument("--"+role+"-sha256",required=True)
    p.add_argument("--source-commit",required=True)
    for role in ROLES:
        p.add_argument("--"+role,type=Path,required=True)
    p.add_argument("--out",type=Path)
    a=p.parse_args(argv)
    try:
        result=audit_chain(a.candidate,a.patch,a.build,
            candidate_sha256=a.candidate_sha256,patch_sha256=a.patch_sha256,
            build_sha256=a.build_sha256,source_commit=a.source_commit,
            payload_paths={role:getattr(a,role) for role in ROLES})
        encoded=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
        if a.out is not None:
            with a.out.open("x",encoding="utf-8",newline="\n") as stream:
                stream.write(encoded)
        print(encoded,end="")
        return 0
    except (TraceError,OSError,ValueError) as exc:
        p.exit(2,f"World chain review refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
