"""Offline, review-only intake of a pinned RiftWorld candidate-path export.

No sibling imports, process access, game interaction or physical clearance
claims. This validates a deliberately narrow subset of the upstream contract;
patch, navigation binary, transform authority and physical traversal are not
independently established by a standalone candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from .contracts import TraceError, _read_bounded, _strict_json, _number

MAX_BYTES = 8 * 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
IDENTITY_FIELDS = ("schema", "patchId", "status", "world", "coordinates",
                   "query", "points", "planner", "evidence")
ENDPOINTS = ("requestedStartXYZ", "requestedGoalXYZ",
             "snappedStartXYZ", "snappedGoalXYZ")


def require(ok, reason):
    if not ok:
        raise TraceError("world candidate: " + reason)


def content_id(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def xyz(value):
    require(isinstance(value, list) and len(value) == 3, "expected XYZ list")
    out = tuple(_number(v, "coordinate") for v in value)
    require(all(abs(v) <= 1e6 for v in out), "coordinate outside review bounds")
    return out


def label(value):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= 256,
            "invalid identifier or label")
    return value


def _validate(candidate):
    require(isinstance(candidate, dict), "object required")
    require(candidate.get("schema") == "riftworld.candidate-path/1", "unsupported schema")
    for key in ("coordinates", "world", "query", "planner", "evidence"):
        require(isinstance(candidate.get(key), dict), "invalid " + key)
    for key in ("candidateId", "patchId"):
        require(isinstance(candidate.get(key), str) and HEX.fullmatch(candidate[key]),
                "invalid " + key)
    identity = {key: candidate[key] for key in IDENTITY_FIELDS}
    identity["plannerResult"] = candidate.get("plannerResult")
    require(content_id(identity) == candidate["candidateId"], "semantic identity mismatch")
    # Initial package scope is complete candidates with explicit endpoints.
    # Partial/unavailable exports remain upstream research data.
    require(candidate["status"] == "complete", "complete candidate required")
    c = candidate["coordinates"]
    require(c.get("axisOrder") == ["x", "y", "z"] and c.get("upAxis") == "y",
            "unsupported coordinate axes")
    label(c.get("frameId"))
    label(c.get("units"))
    require(isinstance(c.get("transformToRr2Native"), dict), "transform declaration required")
    # Preserve source coordinates, without applying any transform or following
    # sourceRefs paths. Those need independently validated patch evidence.
    world = candidate["world"]
    label(world.get("sourceWorld"))
    label(world.get("authority"))
    evidence = candidate["evidence"]
    for key, allowed in (
        ("geometry", ("render-mesh-approximation", "measured", "unknown")),
        ("walkability", ("estimated", "unknown")),
        ("traversal", ("verified", "unverified")),
    ):
        require(evidence.get(key) in allowed, "invalid evidence: " + key)
    query = candidate["query"]
    ends = {key: xyz(query[key]) for key in ENDPOINTS}
    points = candidate["points"]
    require(isinstance(points, list) and 2 <= len(points) <= 500, "invalid point inventory")
    ids = set()
    normalized = []
    for point in points:
        require(isinstance(point, dict), "invalid point")
        ident = label(point.get("id"))
        require(ident not in ids, "duplicate point ID")
        ids.add(ident)
        pos = xyz(point["xyz"])
        require(type(point.get("flags")) is int and 0 <= point["flags"] <= 2**32-1,
                "invalid point flags")
        normalized.append({"id": ident, "xyz": list(pos), "flags": point["flags"]})
    planner = candidate["planner"]
    build = label(planner.get("buildId"))
    raw = candidate.get("plannerResult")
    require(isinstance(raw, dict) and raw.get("status") == "complete"
            and raw.get("cacheKey") == build, "missing or inconsistent planner result")
    waypoints = raw.get("waypoints")
    require(isinstance(waypoints, list) and len(waypoints) == len(normalized),
            "planner point inventory mismatch")
    for p, q in zip(normalized, waypoints, strict=True):
        require(isinstance(q, dict) and xyz(q["pos"]) == tuple(p["xyz"])
                and type(q.get("flags")) is int and q["flags"] == p["flags"],
                "planner waypoint mismatch")
    require(all(xyz(raw[key]) == ends[key] for key in ENDPOINTS), "planner endpoint mismatch")
    # No implicit connector: this narrow review format requires matching
    # snapped path endpoints. Unknown or nonzero requested snaps stay visible.
    require(tuple(normalized[0]["xyz"]) == ends["snappedStartXYZ"]
            and tuple(normalized[-1]["xyz"]) == ends["snappedGoalXYZ"],
            "path endpoints disagree with snapped endpoints")
    snaps = {}
    for name, a, b in (("start", ends["requestedStartXYZ"], ends["snappedStartXYZ"]),
                       ("goal", ends["requestedGoalXYZ"], ends["snappedGoalXYZ"])):
        snaps[name] = {"horizontalXZ": math.hypot(a[0]-b[0], a[2]-b[2]),
                       "verticalY": abs(a[1]-b[1])}
    # Compare any retained source snap metrics; do not invent qualification
    # when limits are absent. Even a valid source snap is not a connector.
    if "endpointSnaps" in raw:
        declared = raw["endpointSnaps"]
        require(isinstance(declared, dict) and set(declared) == {"limits", "start", "goal"},
                "invalid snap evidence")
        limits = declared["limits"]
        require(isinstance(limits, dict) and set(limits) == {"maxHorizontalXZ", "maxVerticalY"},
                "invalid snap limits")
        for v in limits.values():
            require(v is None or _number(v, "snap limit") >= 0., "invalid snap limit")
        require(any(v is not None for v in limits.values()), "empty snap limits")
        for name, measured in snaps.items():
            row = declared[name]
            require(isinstance(row, dict) and set(row) == {"horizontalXZ","verticalY","accepted"},
                    "invalid snap record")
            require(all(math.isclose(_number(row[k], k), measured[k], rel_tol=0., abs_tol=1e-8)
                        for k in measured), "snap measurement mismatch")
            accepted = all(limits[lim] is None or measured[k] <= limits[lim]
                           for k, lim in (("horizontalXZ","maxHorizontalXZ"),("verticalY","maxVerticalY")))
            require(accepted and row["accepted"] is True, "source rejected endpoint snap")
    return {"candidateId": candidate["candidateId"], "patchId": candidate["patchId"],
            "buildId": build, "world": world, "coordinates": c,
            "sourceEvidence": evidence, "points": normalized, "endpointOffsets": snaps,
            "query": {key: list(value) for key,value in ends.items()}}


def inspect_candidate(path, *, expected_sha256, source_commit):
    """Validate the exact caller-pinned export; never follow source paths."""
    raw = _read_bounded(Path(path), MAX_BYTES, "RiftWorld candidate")
    return review_bytes(raw, expected_sha256=expected_sha256, source_commit=source_commit)


def review_bytes(raw, *, expected_sha256, source_commit):
    """Validate the same immutable bytes used by the portable package."""
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "invalid source byte size")
    require(isinstance(expected_sha256,str) and HEX.fullmatch(expected_sha256), "exact source SHA required")
    require(isinstance(source_commit,str) and COMMIT.fullmatch(source_commit), "source revision required")
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, "source SHA mismatch")
    try:
        candidate = _strict_json(raw, "RiftWorld candidate")
        reviewed = _validate(candidate)
    except TraceError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError) as exc:
        raise TraceError("world candidate: malformed export") from exc
    return {"schema":"taxi.world-candidate-review/1",
            "classification":"OFFLINE_REVIEW_ONLY",
            "source":{"repository":"RiftWorld","commit":source_commit,"sha256":expected_sha256},
            **reviewed, "sourceAuthenticityEstablished":False,
            "patchCoverageVerified":False,"transformQualified":False,
            "endpointConnectorsVerified":False,"physicalQualification":False,
            "productionInputAuthorized":False,"gameInputSent":False}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("candidate", type=Path)
    p.add_argument("--expected-sha256",required=True)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--out",type=Path)
    a = p.parse_args(argv)
    try:
        result = inspect_candidate(a.candidate,expected_sha256=a.expected_sha256,
                                   source_commit=a.source_commit)
        encoded = json.dumps(result,indent=2,allow_nan=False)+"\n"
        if a.out is not None:
            with a.out.open("x",encoding="utf-8",newline="\n") as stream:
                stream.write(encoded)
        print(encoded,end="")
        return 0
    except (TraceError,OSError,ValueError) as exc:
        p.exit(2,f"Candidate review refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
