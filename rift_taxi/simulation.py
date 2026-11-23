"""Bounded offline kinematic feedback experiment; never a RIFT actuator.

Reuse the geometry preview's arc lengths, lookahead and synthetic yaw convention.
Only the first recorded synthetic pose seeds the plant; every later pose is
computed from previous simulated motion. No historical/live trace is accepted.
"""
from __future__ import annotations

import math
from typing import Any

from .contracts import MovementTrace, TraceError
from .steering import _segments, _lookahead_point, _angle_delta, _xz_distance


def _bounded_number(value: float, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TraceError(f"{name} must be numeric")
    try:
        number = float(value)
    except (ValueError, OverflowError) as error:
        raise TraceError(f"{name} out of range") from error
    if not math.isfinite(number) or not low <= number <= high:
        raise TraceError(f"{name} must be within {low}..{high}")
    return number


def _project(points, cumulative, position, low, high):
    """Closest point only on an admissible forward arc interval.

    A later crossing cannot teleport progress ahead of the movement budget.
    Ties favor the earlier arc position. This is not obstacle/corridor proof.
    """
    candidates = []
    for i, (a, b) in enumerate(zip(points, points[1:])):
        length = cumulative[i+1] - cumulative[i]
        if length <= 1e-12 or cumulative[i+1] < low or cumulative[i] > high:
            continue
        left = max(0., (low-cumulative[i])/length)
        right = min(1., (high-cumulative[i])/length)
        if left > right:
            continue
        dx, dz = b.xyz[0]-a.xyz[0], b.xyz[2]-a.xyz[2]
        fraction = ((position[0]-a.xyz[0])*dx + (position[2]-a.xyz[2])*dz)/(length*length)
        fraction = max(left, min(right, fraction))
        nearest = (a.xyz[0]+fraction*dx, position[1], a.xyz[2]+fraction*dz)
        candidates.append((_xz_distance(position, nearest), cumulative[i]+fraction*length))
    if not candidates:
        raise TraceError("no admissible synthetic projection")
    error, progress = min(candidates)
    return max(low, min(high, progress)), error


def simulate_route(trace: MovementTrace, *, dt: float = .05, speed: float = 3.,
                   lookahead: float = 1.5, max_yaw_rate: float = 180.,
                   max_seconds: float = 30., max_cross_track: float = 2.) -> dict[str, Any]:
    """Run a deterministic ideal kinematic plant with feedback, no OS input.

    Units, speed, yaw rate, turn response and stopping are explicitly synthetic.
    No actuator, obstacle, delay, collision, elevation or coasting model.
    """
    if trace.source_type != "synthetic" or trace.frame.get("frameId") != "synthetic-local-xyz":
        raise TraceError("simulation accepts only synthetic-local-xyz traces")
    if any(p.kind in {"mandatory_passage", "hard_stop"} for p in trace.points):
        raise TraceError("constraint controller required for mandatory passages/hard stops")
    dt = _bounded_number(dt, "dt", .01, .2)
    speed = _bounded_number(speed, "speed", .1, 20.)
    lookahead = _bounded_number(lookahead, "lookahead", .1, 20.)
    max_yaw_rate = _bounded_number(max_yaw_rate, "max_yaw_rate", 10., 720.)
    max_seconds = _bounded_number(max_seconds, "max_seconds", .2, 120.)
    max_cross_track = _bounded_number(max_cross_track, "max_cross_track", .1, 50.)
    tolerance = _bounded_number(trace.arrival_tolerance_xz, "arrival tolerance", .01, 5.)
    if len(trace.points) < 2 or not trace.poses:
        raise TraceError("synthetic route and initial pose required")
    initial = trace.poses[0]
    for position in (initial.xyz, *(p.xyz for p in trace.points)):
        if len(position) != 3 or any(not math.isfinite(v) or abs(v) > 1e6 for v in position):
            raise TraceError("synthetic coordinates invalid or unbounded")
        if abs(position[1]-initial.xyz[1]) > 1e-9:
            raise TraceError("flat synthetic route required")
    if initial.actor_yaw_deg is None or not math.isfinite(initial.actor_yaw_deg):
        raise TraceError("initial synthetic actor yaw required")
    cumulative, total = _segments(trace.points)
    if any(b-a <= 1e-9 for a,b in zip(cumulative,cumulative[1:])):
        raise TraceError("duplicate horizontal route points")
    if total <= tolerance:
        raise TraceError("route length must exceed arrival tolerance")
    position = initial.xyz
    yaw = _angle_delta(initial.actor_yaw_deg, 0.)
    progress = 0.
    progress_budget = 0.
    traveled = 0.
    forward_time = 0.
    turning_forward_time = 0.
    turn_signs = []
    frames = []
    max_error = 0.
    goal = trace.points[-1].xyz
    status = "time-budget-exhausted"
    time = 0.
    max_steps = math.ceil(max_seconds/dt)
    for i in range(max_steps+1):
        progress, error = _project(trace.points, cumulative, position, progress,
                                   min(total, progress+progress_budget))
        max_error = max(max_error, error)
        distance = _xz_distance(position, goal)
        if error > max_cross_track:
            status = "cross-track-limit"
            break
        if distance <= tolerance and progress >= total-tolerance:
            status = "synthetic-arrived"
            break
        remaining_time = max_seconds-time
        if i == max_steps or remaining_time <= 1e-10:
            break
        step = min(dt, remaining_time)
        target = _lookahead_point(trace.points, cumulative, min(total, progress+lookahead))
        dx, dz = target[0]-position[0], target[2]-position[2]
        chord = math.hypot(dx, dz)
        if chord <= 1e-9:
            status = "lookahead-degenerate"
            break
        heading_error = _angle_delta(math.degrees(math.atan2(dz,dx)), yaw)
        # Proportional heading feedback, rate-limited. An ideal actuator,
        # not RIFT A/D or a physical steering calibration.
        yaw_rate = max(-max_yaw_rate, min(max_yaw_rate, 5.*heading_error))
        velocity = speed if abs(heading_error) < 85. else 0.
        if total-progress <= lookahead:
            velocity = min(velocity, max(.15, 2.*distance), distance/step)
        frames.append({"t": time, "xyz": list(position), "yawDegrees": yaw,
                       "progress": progress, "crossTrackErrorXZ": error,
                       "lookaheadXYZ": list(target), "headingErrorDegrees": heading_error,
                       "speed": velocity, "yawRateDegreesPerSecond": yaw_rate,
                       "stepSeconds": step})
        # Midpoint integration of an ideal planar velocity/turn plant.
        delta_yaw = yaw_rate*step
        mid = math.radians(yaw+delta_yaw/2.)
        delta = velocity*step
        position = (position[0]+delta*math.cos(mid), position[1],
                    position[2]+delta*math.sin(mid))
        yaw = _angle_delta(yaw+delta_yaw, 0.)
        traveled += delta
        progress_budget = 2.*delta
        if velocity > 0:
            forward_time += step
            if abs(yaw_rate) > 1.:
                turning_forward_time += step
                sign = 1 if yaw_rate > 0 else -1
                if not turn_signs or sign != turn_signs[-1]:
                    turn_signs.append(sign)
        time += step
    frames.append({"t": time, "xyz": list(position), "yawDegrees": yaw,
                   "progress": progress, "crossTrackErrorXZ": error,
                   "speed": 0., "yawRateDegreesPerSecond": 0., "stepSeconds": 0.})
    return {
        "schema": "taxi.synthetic-feedback/1",
        "classification": "SYNTHETIC_CLOSED_LOOP_ONLY",
        "status": status, "routeId": trace.route_id, "inputTraceSHA256": trace.trace_sha256,
        "model": {"dtSeconds": dt, "speedSyntheticUnitsPerSecond": speed,
                  "lookaheadSyntheticUnits": lookahead, "maxYawRateDegreesPerSecond": max_yaw_rate,
                  "maxSeconds": max_seconds, "maxCrossTrackSyntheticUnits": max_cross_track,
                  "headingGainPerSecond": 5., "projectionAdvanceBudgetFactor": 2.},
        "metrics": {"elapsedSeconds": time, "simulatedDistanceXZ": traveled,
                    "forwardSeconds": forward_time,
                    "forwardDutyRatio": forward_time/time if time else 0.,
                    "turningWhileForwardSeconds": turning_forward_time,
                    "turnSignRuns": len(turn_signs), "maxCrossTrackErrorXZ": max_error,
                    "finalXZError": _xz_distance(position, goal), "routeLengthXZ": total,
                    "finalProgress": progress, "withinDeclaredXZTolerance": _xz_distance(position, goal) <= tolerance,
                    "syntheticArrival": status == "synthetic-arrived"},
        "frames": frames,
        "gameInputSent": False, "liveNavigabilityVerified": False,
        "liveArrivalVerified": False,
        "limitations": [
            "Only route geometry and first synthetic pose seed the simulation; subsequent recorded poses/events are ignored.",
            "Ideal planar kinematic feedback, not calibrated RIFT physics, key mapping, collision, coasting or source freshness.",
            "Monotonic forward projection is locally budgeted, not a verified traversable corridor or topology proof.",
            "No live controller or OS input is connected.",
        ],
    }
