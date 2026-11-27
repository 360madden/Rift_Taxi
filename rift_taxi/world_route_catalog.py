"""Deterministic local selection of pre-exported, source-pinned review paths.

This is not a navigation query engine. It only selects complete previously
reviewed paths within an explicitly requested source-world/frame/patch scope.
It never connects a position to a route, joins paths, reverses a route,
transforms coordinates or authorizes movement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import stat

from .contracts import TraceError, _read_bounded, _strict_json, _number
from .world_candidate_review import HEX, content_id, require, xyz
from .world_review_package import open_package

SCHEMA = "taxi.world-review-catalog/1"
MAX_CATALOG_BYTES = 256*1024
MAX_ENTRIES = 64
# Flat ASCII filenames deliberately avoid separators, Windows ADS, reserved
# device names and ambiguous case aliases. Never follow catalog subpaths.
FILENAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}\.json\Z")
IDENT = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}\Z")
RESERVED = {"con","prn","aux","nul",*(f"com{i}" for i in range(1,10)),
            *(f"lpt{i}" for i in range(1,10))}


def _id(value,label):
    require(isinstance(value,str) and IDENT.fullmatch(value),"invalid "+label)
    return value


def _sha(value,label):
    require(isinstance(value,str) and HEX.fullmatch(value),"invalid "+label)
    return value


def _limit(value,label):
    n=_number(value,label)
    require(0.<=n<=100.,"invalid "+label)
    return n


def _ordinary(path):
    """Refuse known links/reparse points before opening a local package.

    This is not a sandbox or defense against a hostile concurrent filesystem
    replacement. The external content pin remains the integrity boundary.
    """
    try:
        st=path.lstat()
    except OSError as exc:
        raise TraceError("world catalog: unavailable package") from exc
    require(stat.S_ISREG(st.st_mode)
            and not (getattr(st,"st_file_attributes",0)&0x400),
            "package is not an ordinary non-link file")


def _catalog(path,expected_sha256):
    _sha(expected_sha256,"catalog SHA")
    path=Path(path)
    raw=_read_bounded(path,MAX_CATALOG_BYTES,"world review catalog")
    require(hashlib.sha256(raw).hexdigest()==expected_sha256,"catalog SHA mismatch")
    doc=_strict_json(raw,"world review catalog")
    require(isinstance(doc,dict) and set(doc)=={"schema","entries"}
            and doc["schema"]==SCHEMA,"invalid catalog schema")
    rows=doc["entries"]
    require(isinstance(rows,list) and 1<=len(rows)<=MAX_ENTRIES,"invalid catalog size")
    names=set(); ids=set(); packages=set(); destinations={}
    for row in rows:
        require(isinstance(row,dict) and set(row)=={
            "routeId","destinationId","packageFile","packageId","sourceWorld",
            "frameSHA256","patchId","destinationXYZ"},"invalid catalog entry")
        route=_id(row["routeId"],"route ID")
        _id(row["destinationId"],"destination ID")
        name=row["packageFile"]
        require(isinstance(name,str) and FILENAME.fullmatch(name)
                and name.split(".")[0] not in RESERVED,"invalid package filename")
        pin=_sha(row["packageId"],"package ID")
        _sha(row["frameSHA256"],"frame SHA")
        _sha(row["patchId"],"patch ID")
        world=row["sourceWorld"]
        require(isinstance(world,str) and 0<len(world)<=128 and world==world.strip(),
                "invalid source world")
        # A user-defined destination label has one exact requested XYZ in
        # a given source world/frame/patch. Never rank different endpoints
        # as interchangeable merely because their labels agree.
        goal=xyz(row["destinationXYZ"])
        scope=(row["destinationId"],world,row["frameSHA256"],row["patchId"])
        require(scope not in destinations or destinations[scope]==goal,
                "contradictory destination coordinates")
        destinations[scope]=goal
        require(route not in ids and name not in names and pin not in packages,
                "duplicate catalog identity")
        ids.add(route);names.add(name);packages.add(pin)
    return path.parent,rows


def select_route(catalog,*,catalog_sha256,destination_id,source_world,
                 frame_sha256,patch_id,start_xyz,max_start_xz,max_start_y,
                 max_snap_xz,max_snap_y):
    """Choose one bounded review path; no nearest-neighbor connector.

    All source packages in the requested destination/scope are revalidated.
    Corrupt matching packages abort the query instead of being silently
    ignored. Excluded scope entries are not opened. Rank by start XZ
    offset, start Y offset, full 3D path length and stable route ID.
    """
    root,rows=_catalog(catalog,catalog_sha256)
    _id(destination_id,"destination ID")
    _sha(frame_sha256,"frame SHA")
    _sha(patch_id,"patch ID")
    start=xyz(start_xyz)
    h=_limit(max_start_xz,"start XZ limit")
    y=_limit(max_start_y,"start Y limit")
    sh=_limit(max_snap_xz,"snap XZ limit")
    sy=_limit(max_snap_y,"snap Y limit")
    candidates=[]; excluded=[]
    for row in rows:
        if (row["destinationId"]!=destination_id or row["sourceWorld"]!=source_world
                or row["frameSHA256"]!=frame_sha256 or row["patchId"]!=patch_id):
            continue
        file=root/row["packageFile"]
        _ordinary(file)
        review=open_package(file,expected_package_id=row["packageId"])
        require(review["world"]["sourceWorld"]==source_world
                and content_id(review["coordinates"])==frame_sha256
                and review["patchId"]==patch_id,"package scope mismatch")
        require(tuple(review["query"]["requestedGoalXYZ"])==xyz(row["destinationXYZ"]),
                "package requested destination mismatch")
        points=review["points"]
        a=points[0]["xyz"]
        dx=math.hypot(start[0]-a[0],start[2]-a[2])
        dy=abs(start[1]-a[1])
        offsets=review["endpointOffsets"]
        reason=None
        if dx>h or dy>y:
            reason="start-offset-exceeds-limit"
        elif any(v["horizontalXZ"]>sh or v["verticalY"]>sy for v in offsets.values()):
            reason="endpoint-snap-exceeds-limit"
        if reason:
            excluded.append({"routeId":row["routeId"],"reason":reason})
            continue
        distance=sum(math.dist(a["xyz"],b["xyz"]) for a,b in zip(points,points[1:]))
        item={"routeId":row["routeId"],"packageId":row["packageId"],
              "candidateId":review["candidateId"],
              "destinationXYZ":review["query"]["requestedGoalXYZ"],"startOffsetXZ":dx,
              "startOffsetY":dy,"pathLength3D":distance,
              "endpointOffsets":offsets,"points":points}
        candidates.append(((dx,dy,distance,row["routeId"]),item))
    candidates.sort(key=lambda item:item[0])
    excluded.sort(key=lambda item:item["routeId"])
    selected=candidates[0][1] if candidates else None
    return {"schema":"taxi.world-route-selection/1","classification":"OFFLINE_REVIEW_ONLY",
            "catalogSHA256":catalog_sha256,"destinationId":destination_id,
            "sourceWorld":source_world,"frameSHA256":frame_sha256,"patchId":patch_id,
            "queryStartXYZ":list(start),"limits":{"startXZ":h,"startY":y,"snapXZ":sh,"snapY":sy},
            "status":"review-path-selected" if selected else "no-matching-review-path",
            "selected":selected,"eligibleCount":len(candidates),"excluded":excluded,
            "connectorVerified":False,"physicalQualification":False,
            "productionInputAuthorized":False,"gameInputSent":False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("catalog",type=Path)
    p.add_argument("--catalog-sha256",required=True)
    p.add_argument("--destination-id",required=True)
    p.add_argument("--source-world",required=True)
    p.add_argument("--frame-sha256",required=True)
    p.add_argument("--patch-id",required=True)
    p.add_argument("--start-xyz",nargs=3,type=float,required=True)
    for flag in ("max-start-xz","max-start-y","max-snap-xz","max-snap-y"):
        p.add_argument("--"+flag,type=float,required=True)
    p.add_argument("--out",type=Path)
    a=p.parse_args(argv)
    try:
        result=select_route(a.catalog,catalog_sha256=a.catalog_sha256,
            destination_id=a.destination_id,source_world=a.source_world,
            frame_sha256=a.frame_sha256,patch_id=a.patch_id,start_xyz=a.start_xyz,
            max_start_xz=a.max_start_xz,max_start_y=a.max_start_y,
            max_snap_xz=a.max_snap_xz,max_snap_y=a.max_snap_y)
        encoded=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
        if a.out is not None:
            with a.out.open("x",encoding="utf-8",newline="\n") as stream:
                stream.write(encoded)
        print(encoded,end="")
        return 0 if result["selected"] is not None else 1
    except (TraceError,OSError,ValueError,RecursionError) as exc:
        p.exit(2,f"World route selection refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
