"""Ordered constraint evidence for authored synthetic movement traces.

This is an offline acceptance checker, not a planner or actuator. A mandatory
passage is an explicitly supplied bounded XYZ region, never a center-point
stop. Hard stops and destination require exact repeated synthetic coordinates
and no supplied key activity over a bounded, sampled dwell interval. Even a
passing report does not establish swept-volume clearance or continuous
stationarity between observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from .contracts import TraceError, load_trace, _strict_json, _read_bounded, _number

SCHEMA = "taxi.synthetic-route-constraints/1"
MAX_POLICY_BYTES = 128 * 1024


def require(ok, reason):
    if not ok:
        raise TraceError("route constraint audit: " + reason)


def bounded(value, label, low, high):
    n = _number(value, label)
    require(low <= n <= high, label + " outside bounds")
    return n


def xyz(value, label):
    require(isinstance(value, list) and len(value) == 3, label + " requires XYZ")
    return tuple(bounded(v, label, -1e6, 1e6) for v in value)


def _policy(trace, policy):
    """Bind each mandatory point index to one explicit region.

    Ordered route point indices, not names or nearest-coordinate guesses,
    identify obligations even when a route revisits an identical location.
    """
    require(trace.source_type == "synthetic"
            and trace.frame.get("frameId") == "synthetic-local-xyz"
            and trace.frame.get("units") == "synthetic-units",
            "synthetic local coordinates required")
    fields = {"schema", "traceSHA256", "maxSampleGapSeconds",
              "stopDwellSeconds", "stopYTolerance", "passageRegions"}
    require(isinstance(policy, dict) and set(policy) == fields
            and policy["schema"] == SCHEMA
            and policy["traceSHA256"] == trace.trace_sha256,
            "policy fields or trace pin mismatch")
    gap = bounded(policy["maxSampleGapSeconds"], "sample gap", .001, 5.)
    dwell = bounded(policy["stopDwellSeconds"], "stop dwell", .01, 30.)
    height = bounded(policy["stopYTolerance"], "stop Y tolerance", .001, 5.)
    tolerance = bounded(trace.arrival_tolerance_xz, "stop XZ tolerance", .001, 5.)
    mandatory = [i for i,p in enumerate(trace.points) if p.kind == "mandatory_passage"]
    rows = policy["passageRegions"]
    require(isinstance(rows,list) and len(rows) == len(mandatory),
            "every mandatory passage needs exactly one region")
    regions = {}
    for expected,row in zip(mandatory,rows,strict=True):
        require(isinstance(row,dict) and set(row)=={"pointIndex","minXYZ","maxXYZ"}
                and type(row["pointIndex"]) is int and row["pointIndex"] == expected,
                "region index/order mismatch")
        lo,hi = xyz(row["minXYZ"],"region min"),xyz(row["maxXYZ"],"region max")
        require(all(a < b for a,b in zip(lo,hi)), "region must have positive extent")
        # The route's nominal guide must actually belong to its declared
        # region, but a sample need not visit that nominal coordinate.
        require(all(a <= v <= b for a,v,b in zip(lo,trace.points[expected].xyz,hi)),
                "passage point outside declared region")
        regions[expected] = (lo,hi)
    return gap,dwell,height,tolerance,regions


def _quiet_intervals(trace):
    """For adjacent samples, track key state and intervening supplied events.

    At a left sample an UP may complete a release. Any event strictly after
    that sample and through the next sample breaks the stationary witness.
    All supplied keys count, including turning/backward/strafe keys.
    """
    held = set()
    events = iter(trace.events)
    event = next(events,None)
    quiet = [False]
    first = trace.poses[0].t
    while event is not None and event.t <= first:
        if event.edge == "down":
            held.add(event.key)
        else:
            held.remove(event.key)
        event = next(events,None)
    for pose in trace.poses[1:]:
        idle_before = not held
        activity = False
        while event is not None and event.t <= pose.t:
            activity = True
            if event.edge == "down":
                held.add(event.key)
            else:
                held.remove(event.key)
            event = next(events,None)
        quiet.append(idle_before and not activity and not held)
    return quiet


def audit_constraints(trace, policy):
    """Find successive sampled witnesses; never interpolate a passage hit.

    Search in strictly increasing sample indices. Failed obligations block
    later ones rather than treating a destination hit as journey completion.
    A destination witness must extend through the final observed sample.
    This is a conservative discrete acceptance rule, not continuous proof.
    """
    gap,dwell,height,tolerance,regions = _policy(trace,policy)
    quiet = _quiet_intervals(trace)
    poses = trace.poses
    cursor = 0
    while cursor < len(poses) and poses[cursor].t < trace.window_start:
        cursor += 1
    results = []
    blocked = False
    for i,point in enumerate(trace.points):
        if point.kind not in ("mandatory_passage","hard_stop","destination"):
            continue
        row = {"pointIndex":i,"kind":point.kind,"name":point.name,
               "status":"blocked-by-prior-obligation" if blocked else "not-observed",
               "witness":None}
        if blocked:
            results.append(row)
            continue
        if point.kind == "mandatory_passage":
            lo,hi = regions[i]
            for j in range(cursor,len(poses)):
                if all(a<=v<=b for a,v,b in zip(lo,poses[j].xyz,hi)):
                    row.update(status="sampled-region-observed",
                               witness={"sampleIndex":j,"t":poses[j].t,
                                        "xyz":list(poses[j].xyz)})
                    cursor = j+1
                    break
        else:
            # Exact synthetic XYZ equality, rather than tiny per-step drift
            # that could accumulate over a long stop. The dwell witness
            # requires consecutive samples with no key activity and a bounded
            # intersample gap. No claim about unobserved motion between them.
            start = None
            for j in range(cursor,len(poses)):
                pose = poses[j]
                near = (math.hypot(pose.xyz[0]-point.xyz[0],pose.xyz[2]-point.xyz[2])<=tolerance
                        and abs(pose.xyz[1]-point.xyz[1])<=height)
                if not near:
                    start = None
                    continue
                if (start is None or not quiet[j] or poses[j].xyz!=poses[j-1].xyz
                        or pose.t-poses[j-1].t>gap+1e-12):
                    start = j
                if (pose.t-poses[start].t+1e-12>=dwell
                        and (point.kind!="destination" or j==len(poses)-1)):
                    row.update(status="sampled-stop-observed",
                               witness={"firstSampleIndex":start,"lastSampleIndex":j,
                                        "start":poses[start].t,"end":pose.t,
                                        "durationSeconds":pose.t-poses[start].t,
                                        "xyz":list(pose.xyz)})
                    cursor = j+1
                    break
        blocked = row["witness"] is None
        results.append(row)
    return {"schema":"taxi.synthetic-route-constraint-audit/1",
            "classification":"SYNTHETIC_SAMPLED_EVIDENCE_ONLY",
            "routeId":trace.route_id,"traceSHA256":trace.trace_sha256,
            "allObligationsObserved":not blocked,
            "obligations":results,
            "ordinaryGuideCount":sum(p.kind in ("guide","optional") for p in trace.points),
            "physicalQualification":False,"gameInputSent":False,
            "continuousStationarityVerified":False,"corridorClearanceVerified":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace",type=Path)
    parser.add_argument("policy",type=Path)
    parser.add_argument("--out",type=Path)
    parser.add_argument("--require-observed",action="store_true",
                        help="exit 1 if any ordered obligation lacks a witness")
    args=parser.parse_args(argv)
    try:
        if args.out is not None and args.out.exists():
            raise FileExistsError(args.out)
        raw=_read_bounded(args.policy,MAX_POLICY_BYTES,"constraint policy")
        result=audit_constraints(load_trace(args.trace),_strict_json(raw,"constraint policy"))
        result["policySHA256"]=hashlib.sha256(raw).hexdigest()
        encoded=json.dumps(result,indent=2,allow_nan=False)+"\n"
        if args.out is not None:
            with args.out.open("x",encoding="utf-8",newline="\n") as stream:
                stream.write(encoded)
        print(encoded,end="")
        return 1 if args.require_observed and not result["allObligationsObserved"] else 0
    except (TraceError,OSError,ValueError) as exc:
        parser.exit(2,f"Constraint audit refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
