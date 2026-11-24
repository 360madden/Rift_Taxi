"""Offline synthetic terminal-error decomposition.

Entry point: evaluate_terminal_errors(). Reuses the existing terminal FIFO
audit and frozen v2 geometry; does not change any controller, queue, or
arrival rule. The signed axes are local to the final authored XZ leg:
positive longitudinal error means beyond its endpoint plane, and positive
lateral error means left of its direction. These are geometry diagnostics,
not physical steering measurements or instructions to a game actuator.
"""
from collections import Counter
import math
from statistics import mean

from .contracts import TraceError
from .simulation import _bounded_number
from .simulation_holdout import _case_trace
from .simulation_holdout_v2 import evaluate_holdout_v2
from .simulation_delay_study import _KEYS, _DELAYS
from .simulation_settling import evaluate_settling_study


def decompose_endpoint_error(xyz, preceding, goal):
    """Resolve a displacement into signed orthogonal final-leg components.

    The leg tangent points from the penultimate vertex toward the goal.
    Its left normal is (-tz, tx) in the authored XZ coordinate convention.
    Translation and rotation of an entire route leave these components
    invariant. Refuse zero-length final legs instead of inventing a bearing.
    """
    dx, dz = goal[0]-preceding[0], goal[2]-preceding[2]
    length = math.hypot(dx,dz)
    if not math.isfinite(length) or length <= 1e-9:
        raise TraceError("terminal error requires a finite nonzero final leg")
    tx,tz = dx/length,dz/length
    ex,ez = xyz[0]-goal[0],xyz[2]-goal[2]
    along = ex*tx+ez*tz
    lateral = -ex*tz+ez*tx
    if not math.isfinite(along) or not math.isfinite(lateral):
        raise TraceError("nonfinite terminal error component")
    return {"longitudinalXZ":along,"lateralXZ":lateral,
            "radialXZ":math.hypot(along,lateral)}


def _audit_case(row, trace):
    """Check geometric identity and independently reproduce terminal errors."""
    if (trace.source_type != "synthetic" or trace.trace_sha256 != row["scenarioSHA256"]
            or trace.route_id != row["routeId"]):
        raise TraceError("terminal-error scenario identity mismatch")
    drain = row["terminalDrain"]
    if not row["firstArrivalMetrics"]["syntheticArrival"]:
        if drain["status"] != "not-geometrically-arrived" or drain["settledWithinTolerance"]:
            raise TraceError("failed approach cannot have settled-arrival evidence")
        return {"status":"not-geometrically-arrived"}
    tolerance = _bounded_number(trace.arrival_tolerance_xz,"arrival tolerance",.01,5.)
    preceding,goal = trace.points[-2].xyz,trace.points[-1].xyz
    observations = drain["observations"]
    n = row["delaySteps"]
    if type(n) is not int or not 0 <= n <= 10 or len(observations) != n+2:
        raise TraceError("unexpected terminal observation count")
    errors = []
    for sample in observations:
        components = decompose_endpoint_error(sample["xyz"],preceding,goal)
        if not math.isclose(components["radialXZ"],sample["destinationErrorXZ"],
                            abs_tol=1e-8,rel_tol=0.):
            raise TraceError("terminal observation error disagrees with geometry")
        errors.append(components)
    first,final = errors[0],errors[-1]
    worst = max(e["radialXZ"] for e in errors)
    for actual,reported in ((first["radialXZ"],drain["firstArrivalErrorXZ"]),
                            (final["radialXZ"],drain["settledErrorXZ"]),
                            (worst,drain["maxSampledErrorXZ"])):
        if not math.isclose(actual,reported,abs_tol=1e-8,rel_tol=0.):
            raise TraceError("terminal summary disagrees with sampled geometry")
    # Use the original sampled radial distance for exact tolerance boundary
    # classification; orthogonal projection introduces tiny roundoff.
    inside = drain["settledErrorXZ"] <= tolerance
    excursion = drain["maxSampledErrorXZ"] > tolerance
    if (inside != drain["settledWithinTolerance"] or excursion != drain["leftToleranceAtSample"]
            or drain["firstArrivalErrorXZ"] > tolerance
            or drain["status"] != ("model-settled-inside" if inside else "model-settled-outside")):
        raise TraceError("terminal tolerance classification disagrees")
    # Distinguish a transient exit followed by return from a final failure.
    # The endpoint plane is not a collision boundary; a negative component
    # can coexist with substantial radial failure.
    side = ("beyond-endpoint-plane" if final["longitudinalXZ"] > 1e-9 else
            "before-endpoint-plane" if final["longitudinalXZ"] < -1e-9 else
            "on-endpoint-plane")
    dominant = ("lateral" if abs(final["lateralXZ"]) > abs(final["longitudinalXZ"])
                else "longitudinal")
    return {"status":drain["status"],"initial":first,"final":final,
            "finalEndpointPlaneSide":side,"dominantFinalComponent":dominant,
            "sampledTransientExitThenReturn":excursion and inside,
            "sampledToleranceExit":excursion,
            "settledWithinTolerance":inside,
            "postArrivalDistanceXZ":drain["postArrivalDistanceXZ"]}


def evaluate_terminal_errors():
    """Group every frozen case by delay; preserve approach failures and signs."""
    source = evaluate_holdout_v2()
    traces = {r["case"]:_case_trace({k:r[k] for k in _KEYS},generator="taxi-holdout-v2")
              for r in source["cases"]}
    study = evaluate_settling_study()
    rows = []
    seen = set()
    for row in study["cases"]:
        key = (row["case"],row["delaySteps"])
        if key in seen or key[0] not in traces or key[1] not in _DELAYS:
            raise TraceError("unexpected or duplicate terminal-error scenario")
        seen.add(key)
        rows.append({"case":row["case"],"routeId":row["routeId"],
                     "scenarioSHA256":row["scenarioSHA256"],"delaySteps":row["delaySteps"],
                     "nominalDelaySeconds":row["nominalDelaySeconds"],
                     "firstArrivalStatus":row["firstArrivalStatus"],
                     **_audit_case(row,traces[row["case"]])})
    if seen != {(case,delay) for case in traces for delay in _DELAYS}:
        raise TraceError("incomplete terminal-error scenario set")
    summary = []
    for delay in _DELAYS:
        group = [r for r in rows if r["delaySteps"]==delay]
        arrived = [r for r in group if r["status"]!="not-geometrically-arrived"]
        outside = [r for r in arrived if not r["settledWithinTolerance"]]
        summary.append({"delaySteps":delay,"cases":len(group),"geometricArrivals":len(arrived),
                        "settledOutside":len(outside),
                        "transientExitThenReturn":sum(r["sampledTransientExitThenReturn"] for r in arrived),
                        "outsideEndpointPlaneSides":dict(sorted(Counter(r["finalEndpointPlaneSide"] for r in outside).items())),
                        "outsideDominantComponents":dict(sorted(Counter(r["dominantFinalComponent"] for r in outside).items())),
                        "meanAbsoluteLongitudinalXZ":mean(abs(r["final"]["longitudinalXZ"]) for r in arrived) if arrived else None,
                        "meanAbsoluteLateralXZ":mean(abs(r["final"]["lateralXZ"]) for r in arrived) if arrived else None})
    return {"schema":"taxi.synthetic-terminal-errors/1",
            "classification":"SYNTHETIC_CLOSED_LOOP_ONLY",
            "scenarioSet":source["scenarioSet"],"summary":summary,"cases":rows,
            "gameInputSent":False,"liveArrivalVerified":False,
            "limitations":["Final-leg axes describe authored synthetic geometry only.",
                           "Tolerance exits measured at sampled integration boundaries.",
                           "No controller modifications, physical observations, or independent holdout validation."]}
