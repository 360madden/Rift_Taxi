"""Offline comparison of the experimental ordered sharp-corner policy.

Entry point: compare_ordered_corners(). Reuses the two frozen synthetic
scenario families, original simulator, and trajectory-consistency validator.
No game access, map import, OS input, or file writes. Both sets informed
development, so they are regression sets, not independent holdouts for
this fourth policy. Preserve all baseline outcomes and negative results.
"""
from collections import Counter
import math
from statistics import mean

from .contracts import TraceError
from .simulation import simulate_route
from .simulation_holdout import _case_trace, evaluate_holdout
from .simulation_holdout_v2 import _verify_trajectory, evaluate_holdout_v2
from .steering import _angle_delta

_KEYS = ("routeId", "routeXYZ", "initialXYZ", "initialYawDegrees",
         "lateralOffset", "headingOffsetDegrees", "speed", "maxYawRate", "dt")
_BASE = "turn-limited-rejoin"
_NEW = "turn-limited-ordered"


def verify_ordered_passages(result, trace):
    """Check the synthetic checkpoint witnesses against source route geometry.

    Recalculate corner eligibility and arc distances from source vertices,
    and match every claimed passage to an actual generated frame. This
    validates internal model behavior, not traversability or ground truth.
    """
    _verify_trajectory(result, trace)
    cumulative = [0.]
    for a,b in zip(trace.points, trace.points[1:]):
        cumulative.append(cumulative[-1]+math.hypot(b.xyz[0]-a.xyz[0], b.xyz[2]-a.xyz[2]))
    expected = []
    for i in range(1,len(trace.points)-1):
        a,b,c = (trace.points[j].xyz for j in (i-1,i,i+1))
        first = math.degrees(math.atan2(b[2]-a[2],b[0]-a[0]))
        second = math.degrees(math.atan2(c[2]-b[2],c[0]-b[0]))
        if abs(_angle_delta(second,first)) >= 100.:
            expected.append(i)
    recovery = result["syntheticRecovery"]
    radius = min(.10*result["model"]["lookaheadSyntheticUnits"], .5*trace.arrival_tolerance_xz)
    passages = recovery["orderedSharpCornerPassages"]
    if (recovery["orderedSharpCorners"] != len(expected)
            or recovery["orderedSharpCornersPassed"] != len(passages)
            or len(passages)>len(expected)
            or recovery["orderedSharpCornerRadius"] != radius):
        raise TraceError("ordered corner counts or radius disagree")
    frames = {f["t"]:f for f in result["frames"]}
    previous_t = -1.
    for index,witness in zip(expected,passages):
        f = frames.get(witness["t"])
        p = trace.points[index].xyz
        if (witness["vertexIndex"] != index or witness["vertexArc"] != cumulative[index]
                or witness["t"] <= previous_t or f is None
                or f["xyz"] != witness["xyz"] or f["progress"] != witness["progress"]
                or math.hypot(p[0]-f["xyz"][0],p[2]-f["xyz"][2]) > radius+1e-8
                or not -1e-8 <= cumulative[index]-f["progress"] <= radius+1e-8):
            raise TraceError("invalid ordered corner passage witness")
        previous_t = witness["t"]
    if result["metrics"]["syntheticArrival"] and len(passages)!=len(expected):
        raise TraceError("synthetic arrival lacks ordered corner evidence")


def _compare_set(baseline, version):
    """Use the exact same initial state, model bounds and metrics for each pair."""
    rows = []
    for row in baseline["cases"]:
        spec = {k:row[k] for k in _KEYS}
        trace = _case_trace(spec,generator=f"taxi-holdout-v{version}")
        if trace.trace_sha256 != row["scenarioSHA256"]:
            raise TraceError("scenario digest mismatch")
        result = simulate_route(trace,speed=row["speed"],max_yaw_rate=row["maxYawRate"],
                                dt=row["dt"],max_seconds=40.,speed_policy=_NEW)
        verify_ordered_passages(result,trace)
        metrics = result["metrics"]
        rows.append({"case":row["case"],"scenarioSHA256":trace.trace_sha256,**spec,
                     _BASE:row[_BASE],_NEW:{"status":result["status"],"metrics":metrics,
                     "arrivalAndDutyTarget":metrics["syntheticArrival"] and metrics["forwardDutyRatio"]>=.95,
                     "syntheticRecovery":result["syntheticRecovery"]}})
    def summary(group,policy):
        return {"cases":len(group),"arrivals":sum(r[policy]["metrics"]["syntheticArrival"] for r in group),
                "arrivalAndDutyTarget":sum(r[policy]["arrivalAndDutyTarget"] for r in group),
                "statusCounts":dict(sorted(Counter(r[policy]["status"] for r in group).items()))}
    both = [r for r in rows if all(r[p]["metrics"]["syntheticArrival"] for p in (_BASE,_NEW))]
    return {"scenarioSet":baseline["scenarioSet"],
            "summary":{p:summary(rows,p) for p in (_BASE,_NEW)},
            "paired":{
                "newArrivals":sum(not r[_BASE]["metrics"]["syntheticArrival"] and r[_NEW]["metrics"]["syntheticArrival"] for r in rows),
                "lostArrivals":sum(r[_BASE]["metrics"]["syntheticArrival"] and not r[_NEW]["metrics"]["syntheticArrival"] for r in rows),
                "newCombinedSuccesses":sum(not r[_BASE]["arrivalAndDutyTarget"] and r[_NEW]["arrivalAndDutyTarget"] for r in rows),
                "lostCombinedSuccesses":sum(r[_BASE]["arrivalAndDutyTarget"] and not r[_NEW]["arrivalAndDutyTarget"] for r in rows),
                "commonArrivals":len(both),
                "meanCommonArrivalSeconds":{p:mean(r[p]["metrics"]["elapsedSeconds"] for r in both) if both else None for p in (_BASE,_NEW)}},
            "byRoute":[{"routeId":name,**{p:summary([r for r in rows if r["routeId"]==name],p) for p in (_BASE,_NEW)}}
                       for name in sorted({r["routeId"] for r in rows})],"cases":rows}


def compare_ordered_corners():
    """Return two paired, fully reproducible synthetic regression comparisons."""
    return {"schema":"taxi.synthetic-ordered-corner-comparison/1",
            "classification":"SYNTHETIC_CLOSED_LOOP_ONLY",
            "sets":[_compare_set(evaluate_holdout(include_rejoin=True),1),
                    _compare_set(evaluate_holdout_v2(),2)],
            "gameInputSent":False,"liveArrivalVerified":False,"liveNavigabilityVerified":False,
            "limitations":["Both scenario sets informed development; another untuned set is needed.",
                           "Ordered sharp corners are model checkpoints, not physical corridor proof.",
                           "Positive modeled velocity duty is not physical key-down duty."]}
