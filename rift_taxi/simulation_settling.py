"""Offline terminal FIFO drain audit for the ideal synthetic plant.

Entry point: evaluate_settling_study(). Reuses frozen v2 cases and the
original first-arrival simulation without changing its behavior or metrics.
After geometric arrival, model requesting zero velocity and yaw rate for
each remaining FIFO step, then one full stationary verification step.
There is no feedback correction during drain, no physical actuator, no
game access, and no collision or braking model. Sampled errors describe
integration boundaries, not a continuous swept-volume guarantee.
"""
from collections import Counter
import math
from statistics import mean

from .contracts import TraceError
from .simulation import simulate_route, _bounded_number
from .simulation_holdout import _case_trace
from .simulation_holdout_v2 import evaluate_holdout_v2
from .simulation_ordered_comparison import verify_ordered_passages
from .simulation_delay_study import _KEYS, _DELAYS
from .steering import _angle_delta


def drain_after_arrival(result, trace):
    """Return separate post-arrival observations without mutating the report.

    The ideal plant applies each already queued velocity/rate pair for one
    full nominal dt, in FIFO order, using the same midpoint integration as
    simulate_route. Each new request is zero, so after exactly N steps the
    N-slot queue contains only zeros. One additional stationary interval
    demonstrates the model's zero-command behavior; this does not model
    inertia, delayed observations, or physical game key release.
    """
    if (trace.source_type != "synthetic"
            or result.get("classification") != "SYNTHETIC_CLOSED_LOOP_ONLY"
            or result.get("model", {}).get("speedPolicy") != "turn-limited-ordered"
            or result.get("inputTraceSHA256") != trace.trace_sha256):
        raise TraceError("settling audit requires matching synthetic ordered report")
    verify_ordered_passages(result, trace)
    if not result["metrics"]["syntheticArrival"]:
        # A failed approach is not a terminal arrival test. Retain its
        # original status in the study, never count it as settled.
        return {"status":"not-geometrically-arrived","settledWithinTolerance":False}
    model = result["model"]
    dt = _bounded_number(model["dtSeconds"], "dt", .01, .2)
    speed_limit = _bounded_number(model["speedSyntheticUnitsPerSecond"],"speed",.1,20.)
    yaw_limit = _bounded_number(model["maxYawRateDegreesPerSecond"],"max yaw rate",10.,720.)
    tolerance = _bounded_number(trace.arrival_tolerance_xz,"arrival tolerance",.01,5.)
    delay = result.get("syntheticDelay")
    commands = []
    if delay is not None:
        n = delay["steps"]
        if type(n) is not int or not 1 <= n <= 10 or len(delay["pendingCommands"]) != n:
            raise TraceError("invalid synthetic terminal queue length")
        if not math.isclose(delay["nominalSeconds"],n*dt,abs_tol=1e-9,rel_tol=0.):
            raise TraceError("invalid synthetic nominal delay")
        for command in delay["pendingCommands"]:
            v = _bounded_number(command["speed"],"queued speed",0.,speed_limit)
            rate = _bounded_number(command["yawRateDegreesPerSecond"],"queued yaw rate",-yaw_limit,yaw_limit)
            commands.append((v,rate))
        # Independently compare retained queue to the last N requested
        # pairs, including stationary initial history for short runs.
        requested = [(0.,0.)]*n + [
            (f["requestedSpeed"],f["requestedYawRateDegreesPerSecond"])
            for f in result["frames"][:-1]]
        if commands != requested[-n:]:
            raise TraceError("terminal queue disagrees with request history")
    terminal = result["frames"][-1]
    x,y,z = terminal["xyz"]
    yaw = terminal["yawDegrees"]
    goal = trace.points[-1].xyz
    first_error = math.hypot(x-goal[0],z-goal[2])
    worst = first_error
    traveled = 0.
    observations = [{"elapsedAfterArrivalSeconds":0.,"xyz":[x,y,z],
                     "yawDegrees":yaw,"destinationErrorXZ":first_error}]
    # Append a stationary witness interval after the delayed requests drain.
    # Do not rewrite the previous observation-boundary frame or its duty.
    for i,(velocity,rate) in enumerate(commands+[(0.,0.)],start=1):
        delta_yaw = rate*dt
        mid = math.radians(yaw+delta_yaw/2.)
        delta = velocity*dt
        x += delta*math.cos(mid)
        z += delta*math.sin(mid)
        yaw = _angle_delta(yaw+delta_yaw,0.)
        traveled += delta
        error = math.hypot(x-goal[0],z-goal[2])
        worst = max(worst,error)
        observations.append({"elapsedAfterArrivalSeconds":i*dt,"xyz":[x,y,z],
                             "yawDegrees":yaw,"destinationErrorXZ":error,
                             "appliedSpeed":velocity,"appliedYawRateDegreesPerSecond":rate})
    final_error = observations[-1]["destinationErrorXZ"]
    return {"status":"model-settled-inside" if final_error<=tolerance else "model-settled-outside",
            "settledWithinTolerance":final_error<=tolerance,
            "firstArrivalErrorXZ":first_error,"settledErrorXZ":final_error,
            "maxSampledErrorXZ":worst,"leftToleranceAtSample":worst>tolerance,
            "postArrivalDistanceXZ":traveled,"queueDrainSeconds":len(commands)*dt,
            "stationaryVerificationSeconds":dt,"observations":observations,
            "physicalSettlingVerified":False}


def evaluate_settling_study():
    """Repeat 432 frozen synthetic cases; preserve all first-arrival outcomes."""
    rows = []
    for case in evaluate_holdout_v2()["cases"]:
        trace = _case_trace({k:case[k] for k in _KEYS},generator="taxi-holdout-v2")
        for delay in _DELAYS:
            result = simulate_route(trace,speed=case["speed"],max_yaw_rate=case["maxYawRate"],
                                    dt=case["dt"],max_seconds=40.,speed_policy="turn-limited-ordered",
                                    delay_steps=delay)
            drain = drain_after_arrival(result,trace)
            rows.append({"case":case["case"],"routeId":case["routeId"],
                         "scenarioSHA256":trace.trace_sha256,"delaySteps":delay,
                         "nominalDelaySeconds":delay*case["dt"],"firstArrivalStatus":result["status"],
                         "firstArrivalMetrics":result["metrics"],"terminalDrain":drain})
    summary = []
    for delay in _DELAYS:
        group = [r for r in rows if r["delaySteps"]==delay]
        arrived = [r["terminalDrain"] for r in group if r["firstArrivalMetrics"]["syntheticArrival"]]
        summary.append({"delaySteps":delay,"cases":len(group),"geometricArrivals":len(arrived),
                        "settledWithinTolerance":sum(r["settledWithinTolerance"] for r in arrived),
                        "leftToleranceAtSample":sum(r["leftToleranceAtSample"] for r in arrived),
                        "meanPostArrivalDistanceXZ":mean(r["postArrivalDistanceXZ"] for r in arrived) if arrived else None,
                        "maxSettledErrorXZ":max((r["settledErrorXZ"] for r in arrived),default=None),
                        "statusCounts":dict(sorted(Counter(r["terminalDrain"]["status"] for r in group).items()))})
    return {"schema":"taxi.synthetic-settling-study/1","classification":"SYNTHETIC_CLOSED_LOOP_ONLY",
            "scenarioSet":"route-shape-holdout-v2","speedPolicy":"turn-limited-ordered",
            "summary":summary,"cases":rows,"gameInputSent":False,"liveArrivalVerified":False,
            "physicalSettlingVerified":False,"limitations":[
                "Ideal FIFO drain after geometric arrival; no active correction, inertia, collision or physical actuator.",
                "Full nominal dt steps after boundary are separate from the original 40-second approach budget.",
                "Tolerance excursions measured only at integration boundaries.",
                "Settling is an ideal model observation, not game-consumed release or physical arrival evidence.",
                "Frozen development scenarios are not fresh validation."]}
