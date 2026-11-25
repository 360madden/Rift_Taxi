"""Bounded offline kinematic feedback experiment; never a RIFT actuator.

Reuse the geometry preview's arc lengths, lookahead and synthetic yaw convention.
Only the first recorded synthetic pose seeds the plant; every later pose is
computed from previous simulated motion. No historical/live trace is accepted.

Entry point: simulate_route(), also used by the CLI and paired benchmarks.
Input coordinates are synthetic X/Y/Z with Y up; headings use +X = 0 degrees,
increasing toward +Z. Time is synthetic seconds, never a wall-clock reading.
The return value contains model parameters, generated frames, metrics and
terminal status; this module performs no I/O or real input.

Keep the fixed policy reproducible: the turn-limited policy is an opt-in
experiment, not a production default. Preserve failures as evidence when
adjusting the model, rather than loosening arrival or deviation thresholds.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterable
import math
from typing import Any

from .contracts import MovementTrace, TraceError
from .steering import _segments, _lookahead_point, _angle_delta, _xz_distance, _project


def _bounded_number(value: float, name: str, low: float, high: float) -> float:
    """Reject ambiguous/nonfinite parameters before any simulated step.

    bool is excluded because Python considers it an int. Explicit upper
    bounds also limit the work and memory required by the frame loop.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TraceError(f"{name} must be numeric")
    try:
        number = float(value)
    except (ValueError, OverflowError) as error:
        raise TraceError(f"{name} out of range") from error
    if not math.isfinite(number) or not low <= number <= high:
        raise TraceError(f"{name} must be within {low}..{high}")
    return number


def _turn_limited_speed(speed: float, heading_error: float, chord: float,
                        max_yaw_rate: float) -> float:
    """Cap ideal forward velocity from lookahead curvature and yaw capacity.

    Curvature magnitude is 2*abs(sin(alpha))/chord, in inverse synthetic
    units, with alpha in degrees and chord in units. Angular rate must
    be converted to radians/s before applying v <= omega/curvature.
    This heuristic only models continuous velocity; it cannot establish
    that a real discrete movement actuator supports the same response.
    """
    curvature = 2. * abs(math.sin(math.radians(heading_error))) / chord
    # Leave 20% angular-rate headroom for ideal feedback correction.
    return min(speed, .8 * math.radians(max_yaw_rate) / curvature) if curvature > 1e-9 else speed


def _sharp_vertices(points, cumulative) -> list[tuple[int, float]]:
    """Identify sharp synthetic reversals in route order, not by proximity.

    The angle is the absolute signed heading change between consecutive
    nonzero XZ segments. A 100-degree threshold is a model heuristic.
    """
    result = []
    for i in range(1, len(points)-1):
        a,b,c = points[i-1].xyz, points[i].xyz, points[i+1].xyz
        incoming = math.degrees(math.atan2(b[2]-a[2], b[0]-a[0]))
        outgoing = math.degrees(math.atan2(c[2]-b[2], c[0]-b[0]))
        if abs(_angle_delta(outgoing, incoming)) >= 100.:
            result.append((i, cumulative[i]))
    return result


def _predict_pending_pose(
    position: tuple[float, float, float], yaw: float,
    pending: Iterable[tuple[float, float]], dt: float,
) -> tuple[tuple[float, float, float], float]:
    """Forecast ideal pose just before a newly queued request takes effect.

    Every existing FIFO entry is an already requested velocity (units/s)
    and turn rate (degrees/s), applied in order for one nominal dt. This
    is exact only for the declared midpoint plant and known deterministic
    queue. No prediction is admitted as observed position, route progress,
    sharp-corner passage, arrival or release evidence. The iterable is read
    without dequeuing or mutating it; the actual plant advances separately.
    """
    for velocity, rate in pending:
        turn = rate * dt
        mid = math.radians(yaw + turn / 2.)
        delta = velocity * dt
        position = (position[0] + delta * math.cos(mid), position[1],
                    position[2] + delta * math.sin(mid))
        yaw = _angle_delta(yaw + turn, 0.)
    return position, yaw


def simulate_route(trace: MovementTrace, *, dt: float = .05, speed: float = 3.,
                   lookahead: float = 1.5, max_yaw_rate: float = 180.,
                   max_seconds: float = 30., max_cross_track: float = 2.,
                   speed_policy: str = "fixed", delay_steps: int = 0,
                   predict_command_application: bool = False) -> dict[str, Any]:
    """Run a deterministic ideal kinematic plant with feedback, no OS input.

    Units, speed, yaw rate, turn response and stopping are explicitly synthetic.
    No physical actuator, obstacle, collision, elevation or coasting model.
    Optional delay_steps is an ideal FIFO transport delay of both requested
    velocity and yaw rate, in whole integration steps. Zero preserves the
    original instant-response model and its report format. The optional
    prediction experiment is restricted to the ordered policy. It uses the
    queued ideal motion to compute a future control pose, but preserves
    actual observed arc progress, corner witnesses and terminal criteria.
    With zero delay the flag is an exact no-op, including report bytes.

    dt: integration step (seconds); speed: nominal positive units/s;
    lookahead: route arc-length distance (units); max_yaw_rate: degrees/s;
    max_seconds: finite work/time budget; max_cross_track: local projection
    error bound (units). speed_policy selects the baseline, cap, or opt-in local
    projection rejoin experiment.
    Invalid inputs raise TraceError; bounded tracking failures are returned as
    terminal statuses rather than falsely declaring arrival.
    """
    if trace.source_type != "synthetic" or trace.frame.get("frameId") != "synthetic-local-xyz":
        raise TraceError("simulation accepts only synthetic-local-xyz traces")
    if any(p.kind in {"mandatory_passage", "hard_stop"} for p in trace.points):
        raise TraceError("constraint controller required for mandatory passages/hard stops")
    if speed_policy not in ("fixed", "turn-limited", "turn-limited-rejoin", "turn-limited-ordered"):
        raise TraceError("unknown synthetic speed policy")
    if type(delay_steps) is not int or not 0 <= delay_steps <= 10:
        raise TraceError("delay_steps must be an integer within 0..10")
    if type(predict_command_application) is not bool:
        raise TraceError("predict_command_application must be boolean")
    if predict_command_application and speed_policy != "turn-limited-ordered":
        raise TraceError("command prediction requires the ordered synthetic policy")
    prediction_active = predict_command_application and delay_steps > 0
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
    # Plant state is derived from only the first supplied synthetic pose.
    # Later prerecorded positions/events must not influence this experiment.
    # A finite FIFO holds already-issued synthetic commands. Initial
    # command history is stationary. The model sees current pose without
    # sensor delay; only command application is delayed. This is not a
    # measured physical actuator or a key-event queue.
    pending = deque([(0., 0.)] * delay_steps)
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
    # Recovery belongs to this synthetic experiment alone. Hysteresis prevents
    # the target from flipping between normal lookahead and its local anchor
    # every integration step as the vehicle approaches the route.
    rejoining = False
    rejoin_entries = 0
    # Sequential synthetic sharp-corner gates. Gate completion never assigns
    # progress directly; the original per-step displacement budget still
    # bounds every projection. Prior policy behavior remains unchanged.
    ordered = speed_policy == "turn-limited-ordered"
    sharp = _sharp_vertices(trace.points, cumulative) if ordered else []
    sharp_cursor = 0
    # Keep actual model-space witnesses instead of reporting only a count.
    # The comparator can independently check every passage radius and arc.
    sharp_passages = []
    passed_arc = 0.
    goal = trace.points[-1].xyz
    status = "time-budget-exhausted"
    time = 0.
    # Separate arc progress from distance traveled. Each update may consume
    # at most twice the prior step's displacement on the route arc; this
    # experimental allowance permits corner cutting without arbitrary jumps.
    # It is not an obstacle-clearance or topology guarantee.
    max_steps = math.ceil(max_seconds/dt)
    for i in range(max_steps+1):
        low = progress
        high = min(total, progress+progress_budget)
        if ordered:
            # Pending sharp corners bound the eligible arc interval. After
            # spatial and arc evidence of a passed corner, prefer its outgoing
            # arc, but only within the original displacement-derived budget.
            if sharp_cursor < len(sharp):
                high = min(high, sharp[sharp_cursor][1])
            low = min(high, max(low, passed_arc))
        progress, error = _project(trace.points, cumulative, position, low,
                                   high)
        if ordered and sharp_cursor < len(sharp):
            index, arc = sharp[sharp_cursor]
            radius = min(.10*lookahead, .5*tolerance)
            if (arc-progress <= radius
                    and _xz_distance(position, trace.points[index].xyz) <= radius):
                sharp_passages.append({
                    "vertexIndex": index, "vertexArc": arc, "t": time,
                    "xyz": list(position), "progress": progress,
                })
                passed_arc = arc
                sharp_cursor += 1
                rejoining = False
        max_error = max(max_error, error)
        distance = _xz_distance(position, goal)
        if error > max_cross_track:
            status = "cross-track-limit"
            break
        # Require both local progress and endpoint proximity. A route that
        # returns near its start must not be marked arrived at t=0.
        if (distance <= tolerance and progress >= total-tolerance
                and (not ordered or sharp_cursor == len(sharp))):
            status = "synthetic-arrived"
            break
        remaining_time = max_seconds-time
        if i == max_steps or remaining_time <= 1e-10:
            break
        step = min(dt, remaining_time)
        # Only steering's reference pose is predicted. The target arc, rejoin
        # decisions, passage witnesses and progress budget still use actual
        # observations above. A prediction must never skip a sharp corner.
        control_position, control_yaw = position, yaw
        control_distance = distance
        if prediction_active:
            control_position, control_yaw = _predict_pending_pose(position, yaw, pending, dt)
            control_distance = _xz_distance(control_position, goal)
        target_arc = min(total, progress+lookahead)
        if ordered and sharp_cursor < len(sharp):
            target_arc = min(target_arc, sharp[sharp_cursor][1])
        target = _lookahead_point(trace.points, cumulative, target_arc)
        dx, dz = target[0]-control_position[0], target[2]-control_position[2]
        chord = math.hypot(dx, dz)
        if speed_policy in ("turn-limited-rejoin", "turn-limited-ordered"):
            # A short chord can occur even when substantial arc remains:
            # closely spaced bends let the plant reach a future geometric
            # target while its monotonic arc projection is still behind.
            # With v <= omega/kappa and kappa proportional to 1/chord,
            # velocity then collapses. Do not increase the progress budget
            # or force a minimum speed through an ill-defined heading.
            # Instead, temporarily target the already-admissible arc point.
            # Entry/exit distances scale with lookahead; retain ordinary
            # deviation/time limits and the original arrival test.
            if rejoining and error <= .15 * lookahead:
                rejoining = False
            if (not rejoining and chord <= .20 * lookahead
                    and error > .35 * lookahead):
                rejoining = True
                rejoin_entries += 1
            if rejoining:
                target = _lookahead_point(trace.points, cumulative, progress)
                dx, dz = target[0]-control_position[0], target[2]-control_position[2]
                chord = math.hypot(dx, dz)
        # A coincident target has no well-defined bearing. Keep the failure
        # explicit rather than guessing a yaw or skipping an unverified leg.
        # Holdout v1 exposes this limitation on tightly spaced zigzags.
        if chord <= 1e-9:
            status = "lookahead-degenerate"
            break
        heading_error = _angle_delta(math.degrees(math.atan2(dz,dx)), control_yaw)
        # Proportional heading feedback, rate-limited. An ideal actuator,
        # not RIFT A/D or a physical steering calibration.
        yaw_rate = max(-max_yaw_rate, min(max_yaw_rate, 5.*heading_error))
        velocity = speed if abs(heading_error) < 85. else 0.
        if speed_policy in ("turn-limited", "turn-limited-rejoin", "turn-limited-ordered") and velocity > 0.:
            velocity = _turn_limited_speed(velocity, heading_error, chord, max_yaw_rate)
        # Terminal approach bounds the ideal step by remaining Euclidean
        # distance and reduces velocity near the goal. No coast/braking
        # dynamics are implied by this instantaneous model.
        if ordered and sharp_cursor < len(sharp) and target_arc == sharp[sharp_cursor][1] and not rejoining:
            # Avoid stepping past a close anchor while aligning. Keep the
            # curvature cap; no forced minimum velocity at a singularity.
            velocity = min(velocity, chord/step)
        if total-progress <= lookahead:
            velocity = min(velocity, max(.15, 2.*control_distance), control_distance/step)
        # Record both requested and applied commands for nonzero delay.
        # Motion metrics and projection budget use the applied values only.
        requested_velocity, requested_yaw_rate = velocity, yaw_rate
        if delay_steps:
            pending.append((velocity, yaw_rate))
            velocity, yaw_rate = pending.popleft()
        frames.append({"t": time, "xyz": list(position), "yawDegrees": yaw,
                       "progress": progress, "crossTrackErrorXZ": error,
                       "lookaheadXYZ": list(target), "headingErrorDegrees": heading_error,
                       "speed": velocity, "yawRateDegreesPerSecond": yaw_rate,
                       "stepSeconds": step})
        if prediction_active:
            frames[-1]["predictedApplicationXYZ"] = list(control_position)
            frames[-1]["predictedApplicationYawDegrees"] = control_yaw
        if delay_steps:
            frames[-1]["requestedSpeed"] = requested_velocity
            frames[-1]["requestedYawRateDegreesPerSecond"] = requested_yaw_rate
        # Only the recovery variant adds target-mode diagnostics, keeping
        # prior policy reports byte-reproducible.
        if speed_policy in ("turn-limited-rejoin", "turn-limited-ordered"):
            frames[-1]["targetMode"] = "local-projection-rejoin" if rejoining else "lookahead"
        if ordered:
            frames[-1]["orderedSharpCornersPassed"] = sharp_cursor
        # Midpoint integration of an ideal planar velocity/turn plant.
        delta_yaw = yaw_rate*step
        mid = math.radians(yaw+delta_yaw/2.)
        delta = velocity*step
        position = (position[0]+delta*math.cos(mid), position[1],
                    position[2]+delta*math.sin(mid))
        yaw = _angle_delta(yaw+delta_yaw, 0.)
        traveled += delta
        progress_budget = 2.*delta
        # Duty is modeled positive-velocity time divided by elapsed time,
        # not W key-down duration. Turn-sign runs are a coarse diagnostic,
        # not a verified count of distinct physical bends.
        if velocity > 0:
            forward_time += step
            if abs(yaw_rate) > 1.:
                turning_forward_time += step
                sign = 1 if yaw_rate > 0 else -1
                if not turn_signs or sign != turn_signs[-1]:
                    turn_signs.append(sign)
        time += step
    # Explicit terminal frame has zero requested velocity/rate regardless of
    # success or failure; it is not evidence that a physical key was released.
    frames.append({"t": time, "xyz": list(position), "yawDegrees": yaw,
                   "progress": progress, "crossTrackErrorXZ": error,
                   "speed": 0., "yawRateDegreesPerSecond": 0., "stepSeconds": 0.})
    # Add recovery diagnostics only to the new variant, preserving the
    # original report schemas and exact baseline reproduction.
    recovery = ({"syntheticRecovery": {"rejoinEntries": rejoin_entries,
                                        "activeAtTermination": rejoining,
                                        "entryChordFractionOfLookahead": .20,
                                        "entryErrorFractionOfLookahead": .35,
                                        "exitErrorFractionOfLookahead": .15}}
                if speed_policy in ("turn-limited-rejoin", "turn-limited-ordered") else {})
    if ordered:
        recovery["syntheticRecovery"]["orderedSharpCorners"] = len(sharp)
        recovery["syntheticRecovery"]["orderedSharpCornersPassed"] = sharp_cursor
        recovery["syntheticRecovery"]["orderedSharpCornerRadius"] = min(.10*lookahead, .5*tolerance)
        recovery["syntheticRecovery"]["orderedSharpCornerMinimumDegrees"] = 100.
        recovery["syntheticRecovery"]["orderedSharpCornerPassages"] = sharp_passages
    # Terminal frame is the end of the observation, not a drained FIFO.
    # Do not claim settled arrival under delay: queued motion could persist
    # after the position criterion is first satisfied. Expose pending state.
    delay_diagnostics = ({
        "syntheticDelay": {
            "steps": delay_steps, "nominalSeconds": delay_steps*dt,
            "pendingCommands": [{"speed": v, "yawRateDegreesPerSecond": r}
                                for v,r in pending],
            "settledArrivalVerified": False,
            "terminalFrameIsObservationBoundary": True,
        }
    } if delay_steps else {})
    return {
        **recovery,
        **delay_diagnostics,
        **({"syntheticCommandPrediction": {"method": "queued-pose-midpoint/1",
                                           "observedProgressOnly": True,
                                           "nominalHorizonSeconds": delay_steps*dt}}
           if prediction_active else {}),
        "schema": "taxi.synthetic-feedback/1",
        "classification": "SYNTHETIC_CLOSED_LOOP_ONLY",
        "status": status, "routeId": trace.route_id, "inputTraceSHA256": trace.trace_sha256,
        "model": {"dtSeconds": dt, "speedSyntheticUnitsPerSecond": speed,
                  "lookaheadSyntheticUnits": lookahead, "maxYawRateDegreesPerSecond": max_yaw_rate,
                  "maxSeconds": max_seconds, "maxCrossTrackSyntheticUnits": max_cross_track,
                  "headingGainPerSecond": 5., "projectionAdvanceBudgetFactor": 2.,
                  "speedPolicy": speed_policy},
        "metrics": {"elapsedSeconds": time, "simulatedDistanceXZ": traveled,
                    "forwardSeconds": forward_time,
                    "forwardDutyRatio": forward_time/time if time else 0.,
                    "meanSpeedSyntheticUnitsPerSecond": traveled/time if time else 0.,
                    "meanMovingSpeedSyntheticUnitsPerSecond": traveled/forward_time if forward_time else 0.,
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
