"""Offline failure analysis of the frozen V3 synthetic benchmark.

Entry point: audit_v3_failures(). Reuse the existing authored scenarios,
trace builder, simulator, witness validation, and endpoint decomposition.
No policy changes, physical maps, game access, or input. A timeout with
substantial simulated motion and little arc progress is described by its
measured quantities, not assumed to be a particular physical failure.
"""
from collections import Counter
import math

from .contracts import TraceError
from .simulation import simulate_route
from .simulation_holdout import _case_trace
from .simulation_holdout_v3 import evaluate_holdout_v3
from .simulation_ordered_comparison import verify_ordered_passages
from .simulation_terminal_errors import decompose_endpoint_error

_KEYS = ("routeId","routeXYZ","initialXYZ","initialYawDegrees",
         "lateralOffset","headingOffsetDegrees","speed","maxYawRate","dt")
_DELAYS = (0,1,3)
_POLICY = "turn-limited-ordered"
_WINDOW_SECONDS = 5.


def _tail_motion(result):
    """Measure complete frame intervals inside the last five model seconds.

    Use applied velocity and yaw rate, not requested commands. The first
    selected frame starts at or after the window boundary; no interpolation
    of progress is performed. The actual sampled duration is retained.
    Absolute yaw accumulation is angular travel, not net heading change.
    """
    frames = result["frames"]
    end = frames[-1]
    tail = [f for f in frames[:-1] if f["t"] >= end["t"]-_WINDOW_SECONDS]
    if not tail:
        raise TraceError("timeout lacks terminal motion intervals")
    elapsed = end["t"]-tail[0]["t"]
    if elapsed <= 0.:
        raise TraceError("invalid terminal motion window")
    motion = sum(f["speed"]*f["stepSeconds"] for f in tail)
    turning = sum(abs(f["yawRateDegreesPerSecond"])*f["stepSeconds"] for f in tail)
    advance = end["progress"]-tail[0]["progress"]
    return {"sampledSeconds":elapsed,"distanceXZ":motion,"arcAdvance":advance,
            "absoluteYawTravelDegrees":turning,
            "meanAppliedSpeed":motion/elapsed,
            "arcAdvancePerDistance":advance/motion if motion>0. else None}


def _classify(outcome):
    """Keep approach failures separate from unsuccessful terminal drain."""
    if not outcome["metrics"]["syntheticArrival"]:
        return "approach-failed"
    if not outcome["terminalDrain"]["settledWithinTolerance"]:
        return "settled-outside"
    return "settled-inside"


def audit_v3_failures():
    """Retain all 216 ordered-policy outcomes and investigate adverse cases.

    Evaluate unchanged V3, then rerun only unsuccessful approaches to retain
    the complete validated frame history needed by the tail-motion audit.
    Compare reruns with original metrics and recovery witnesses. For
    geometric arrivals, independently resolve final sampled errors using
    the source route's last leg. This does not tune stopping or steering.
    """
    base = evaluate_holdout_v3()
    rows = []
    for case in base["cases"]:
        trace = _case_trace({k:case[k] for k in _KEYS},generator="taxi-holdout-v3")
        if trace.trace_sha256 != case["scenarioSHA256"]:
            raise TraceError("V3 source digest mismatch")
        preceding,goal = trace.points[-2].xyz,trace.points[-1].xyz
        for delay in _DELAYS:
            original = case["outcomes"][f"{_POLICY}:{delay}"]
            metrics = original["metrics"]
            recovery = original["syntheticRecovery"]
            category = _classify(original)
            row = {"case":case["case"],"routeId":case["routeId"],
                   "scenarioSHA256":trace.trace_sha256,"delaySteps":delay,
                   "nominalDelaySeconds":delay*case["dt"],
                   "profile":{"speed":case["speed"],"maxYawRate":case["maxYawRate"],"dt":case["dt"]},
                   "category":category,"approachStatus":original["status"],
                   "finalProgress":metrics["finalProgress"],"routeLengthXZ":metrics["routeLengthXZ"],
                   "orderedCorners":recovery["orderedSharpCorners"],
                   "orderedCornersPassed":recovery["orderedSharpCornersPassed"]}
            if category=="approach-failed":
                result = simulate_route(trace,speed=case["speed"],max_yaw_rate=case["maxYawRate"],
                                        dt=case["dt"],max_seconds=40.,speed_policy=_POLICY,
                                        delay_steps=delay)
                verify_ordered_passages(result,trace)
                if (result["status"]!=original["status"] or result["metrics"]!=metrics
                        or result["syntheticRecovery"]!=recovery):
                    raise TraceError("V3 failure rerun disagrees with original outcome")
                row["terminalMotionWindow"] = _tail_motion(result)
            else:
                drain = original["terminalDrain"]
                error = decompose_endpoint_error(drain["observations"][-1]["xyz"],preceding,goal)
                if not math.isclose(error["radialXZ"],drain["settledErrorXZ"],abs_tol=1e-8,rel_tol=0.):
                    raise TraceError("V3 settled error disagrees with source geometry")
                row["settledError"] = error
                row["sampledToleranceExit"] = drain["leftToleranceAtSample"]
            rows.append(row)

    def summarize(group):
        failed = [r for r in group if r["category"]=="approach-failed"]
        return {"cases":len(group),"outcomeCounts":dict(sorted(Counter(r["category"] for r in group).items())),
                "approachFailuresBeforeFirstCorner":sum(r["orderedCorners"]>0 and r["orderedCornersPassed"]==0 for r in failed),
                "approachFailureTailMotion":({
                    "minDistanceXZ":min(r["terminalMotionWindow"]["distanceXZ"] for r in failed),
                    "maxDistanceXZ":max(r["terminalMotionWindow"]["distanceXZ"] for r in failed),
                    "maxArcAdvance":max(r["terminalMotionWindow"]["arcAdvance"] for r in failed),
                    "minAbsoluteYawTravelDegrees":min(r["terminalMotionWindow"]["absoluteYawTravelDegrees"] for r in failed)
                } if failed else None)}
    # Profiles deliberately couple speed, yaw limit and dt; grouping does
    # not identify the independent causal effect of any one variable.
    profiles = sorted({(r["profile"]["speed"],r["profile"]["maxYawRate"],r["profile"]["dt"]) for r in rows})
    return {"schema":"taxi.synthetic-v3-failure-audit/1","classification":"SYNTHETIC_CLOSED_LOOP_ONLY",
            "scenarioSet":base["scenarioSet"],"caseCount":len(rows),
            "byDelay":[{"delaySteps":d,**summarize([r for r in rows if r["delaySteps"]==d])} for d in _DELAYS],
            "byProfileAndDelay":[{"speed":s,"maxYawRate":y,"dt":dt,"delaySteps":d,
                                  **summarize([r for r in rows if r["delaySteps"]==d and
                                               (r["profile"]["speed"],r["profile"]["maxYawRate"],r["profile"]["dt"])==(s,y,dt)])}
                                 for s,y,dt in profiles for d in _DELAYS],
            "cases":rows,"gameInputSent":False,"liveArrivalVerified":False,
            "limitations":["Synthetic motion only; no physical stopping or game navigation evidence.",
                           "Tail window contains complete integration intervals; no continuous swept-path claim.",
                           "Coupled profiles confound speed, yaw cap, timestep, and nominal delay.",
                           "Frozen V3 outcomes were already observed; no new independent validation."]}
