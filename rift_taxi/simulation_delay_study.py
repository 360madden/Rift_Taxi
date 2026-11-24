"""Synthetic transport-delay sensitivity study; no game or OS interaction.

Entry point: evaluate_delay_study(). Reuse the frozen v2 geometry and initial
conditions and the ordered-corner model. Delay is a count of integration
steps, so nominal seconds vary with each scenario's timestep. This is an
ideal command FIFO, not measured actuator dynamics or sensor latency.
"""
from collections import Counter
from .simulation import simulate_route
from .simulation_holdout import _case_trace
from .simulation_holdout_v2 import evaluate_holdout_v2, _verify_trajectory
from .simulation_ordered_comparison import verify_ordered_passages

_KEYS = ("routeId","routeXYZ","initialXYZ","initialYawDegrees",
         "lateralOffset","headingOffsetDegrees","speed","maxYawRate","dt")
_DELAYS = (0,1,2,4)


def evaluate_delay_study():
    """Preserve every matched outcome, including failures and queued motion.

    Arrival means the original geometric criterion first became true, not
    settled arrival after commands drain. The FIFO starts stationary and
    is never flushed into the trajectory after the observation boundary.
    """
    rows = []
    for case in evaluate_holdout_v2()["cases"]:
        trace = _case_trace({k:case[k] for k in _KEYS},generator="taxi-holdout-v2")
        for delay in _DELAYS:
            result = simulate_route(trace, speed=case["speed"],
                                    max_yaw_rate=case["maxYawRate"], dt=case["dt"],
                                    max_seconds=40., speed_policy="turn-limited-ordered",
                                    delay_steps=delay)
            verify_ordered_passages(result,trace)
            # Only applied velocity contributes to original duty and progress.
            # Pending commands at termination remain explicitly unqualified.
            pending = result.get("syntheticDelay",{}).get("pendingCommands",[])
            rows.append({"case":case["case"],"routeId":case["routeId"],
                         "scenarioSHA256":trace.trace_sha256,"delaySteps":delay,
                         "nominalDelaySeconds":delay*case["dt"],
                         "status":result["status"],"metrics":result["metrics"],
                         "pendingNonzeroAtBoundary":any(
                             p["speed"]!=0. or p["yawRateDegreesPerSecond"]!=0.
                             for p in pending),
                         "settledArrivalVerified":False})
    summary = []
    for delay in _DELAYS:
        group = [r for r in rows if r["delaySteps"]==delay]
        arrived = [r for r in group if r["metrics"]["syntheticArrival"]]
        summary.append({"delaySteps":delay,"cases":len(group),
                        "geometricArrivals":len(arrived),
                        "arrivalAndDutyTarget":sum(r["metrics"]["forwardDutyRatio"]>=.95 for r in arrived),
                        "arrivalsWithPendingMotion":sum(r["pendingNonzeroAtBoundary"] for r in arrived),
                        "statusCounts":dict(sorted(Counter(r["status"] for r in group).items()))})
    return {"schema":"taxi.synthetic-delay-study/1",
            "classification":"SYNTHETIC_CLOSED_LOOP_ONLY",
            "scenarioSet":"route-shape-holdout-v2","speedPolicy":"turn-limited-ordered",
            "summary":summary,"cases":rows,"gameInputSent":False,
            "liveArrivalVerified":False,"settledArrivalVerified":False,
            "limitations":["Ideal whole-step FIFO delay; no measured RIFT response.",
                           "Nominal delay varies with timestep; final partial step may be shorter.",
                           "Geometry-only arrival ends observation without draining commands.",
                           "Previously used synthetic scenarios, not fresh validation."]}
