"""Independent consistency audit of generated synthetic trajectories.

Entry point: verify_synthetic_trajectory(result, trace). No file I/O,
native process access, control output or real-world observation.
Check the declared ideal midpoint integration and FIFO semantics against
the recorded frames, then recalculate report metrics. This is an internal
consistency check, not authentication, controller correctness, collision
clearance, or evidence of physical movement.
"""
from collections import deque
import math

from .contracts import MovementTrace, TraceError

# Floating-point comparisons allow ordinary accumulated integration error,
# but not a different unit convention, timestamp or trajectory.
_EPS = 1e-8
_STATUSES = {"synthetic-arrived", "cross-track-limit",
             "time-budget-exhausted", "lookahead-degenerate"}


def _number(value, label, low=-math.inf, high=math.inf):
    """Reject bools, nonfinite values, overflow and out-of-domain numbers."""
    if type(value) not in (int, float):
        raise TraceError(f"invalid synthetic {label}")
    try:
        value = float(value)
    except (ValueError, OverflowError) as exc:
        raise TraceError(f"invalid synthetic {label}") from exc
    if not math.isfinite(value) or not low <= value <= high:
        raise TraceError(f"invalid synthetic {label}")
    return value


def _same(actual, expected, label):
    """Compare numeric claims without accepting NaN or bool as a number."""
    if not math.isclose(_number(actual,label), expected, abs_tol=_EPS, rel_tol=0.):
        raise TraceError(f"synthetic {label} disagrees with trajectory")


def _xyz(value):
    if not isinstance(value,(tuple,list)) or len(value)!=3:
        raise TraceError("invalid synthetic XYZ")
    return tuple(_number(v,"coordinate") for v in value)


def _yaw_delta(a,b):
    # Independently implement the circular-angle comparison; headings
    # differing by a full revolution represent the same orientation.
    return (a-b+180.)%360.-180.


def verify_synthetic_trajectory(result: dict, trace: MovementTrace) -> None:
    """Validate one report against its synthetic source and applied frames.

    Time is in model seconds, velocity in synthetic units/s, yaw in
    degrees. The last frame has no integration interval. Nonzero delay
    means exactly N whole requests in FIFO order; terminal queue contents
    are not a settled-position witness. Every successful result needs
    both endpoint proximity and admitted arc progress.
    """
    try:
        _verify(result,trace)
    except (KeyError, TypeError, IndexError, AttributeError, ValueError, OverflowError) as exc:
        # TraceError may subclass ValueError; preserve deliberate diagnostics.
        if isinstance(exc,TraceError):
            raise
        raise TraceError("malformed synthetic trajectory report") from exc


def _verify(result,trace):
    if (trace.source_type != "synthetic"
            or trace.frame.get("frameId") != "synthetic-local-xyz"
            or result["schema"] != "taxi.synthetic-feedback/1"
            or result["classification"] != "SYNTHETIC_CLOSED_LOOP_ONLY"
            or result["routeId"] != trace.route_id
            or result["inputTraceSHA256"] != trace.trace_sha256
            or any(result[k] is not False for k in
                   ("gameInputSent","liveNavigabilityVerified","liveArrivalVerified"))):
        raise TraceError("synthetic trajectory identity/classification mismatch")
    status = result["status"]
    if status not in _STATUSES:
        raise TraceError("invalid synthetic terminal status")
    model,metrics,frames = result["model"],result["metrics"],result["frames"]
    dt = _number(model["dtSeconds"],"dt",.01,.2)
    speed_cap = _number(model["speedSyntheticUnitsPerSecond"],"speed cap",.1,20.)
    yaw_cap = _number(model["maxYawRateDegreesPerSecond"],"yaw cap",10.,720.)
    time_cap = _number(model["maxSeconds"],"time cap",.2,120.)
    deviation_cap = _number(model["maxCrossTrackSyntheticUnits"],"deviation cap",.1,50.)
    _number(model["lookaheadSyntheticUnits"],"lookahead",.1,20.)
    _same(model["projectionAdvanceBudgetFactor"],2.,"projection budget factor")
    if (not isinstance(frames,list) or not frames
            or len(frames)>math.ceil(time_cap/dt)+1):
        raise TraceError("invalid synthetic frame count")
    tolerance = _number(trace.arrival_tolerance_xz,"arrival tolerance",.01,5.)
    points = [_xyz(p.xyz) for p in trace.points]
    if len(points)<2 or not trace.poses:
        raise TraceError("invalid synthetic source geometry")
    total = sum(math.hypot(b[0]-a[0],b[2]-a[2]) for a,b in zip(points,points[1:]))
    goal = points[-1]
    initial = trace.poses[0]
    initial_position = _xyz(initial.xyz)
    initial_yaw = _number(initial.actor_yaw_deg,"initial yaw")
    delay = result.get("syntheticDelay")
    n = 0
    if "syntheticDelay" in result:
        n = delay["steps"]
        if type(n) is not int or not 1<=n<=10:
            raise TraceError("invalid synthetic delay steps")
        _same(delay["nominalSeconds"],n*dt,"nominal delay")
        if (delay["settledArrivalVerified"] is not False
                or delay["terminalFrameIsObservationBoundary"] is not True):
            raise TraceError("invalid synthetic terminal delay classification")
    queue = deque([(0.,0.)]*n)

    # Accumulate using the actual applied velocity and duration, never
    # requested motion. Stationary and turning-only intervals stay in the
    # elapsed denominator. Reconstruct next pose from each previous frame.
    elapsed = traveled = moving = turning = maximum_error = 0.
    turn_runs = 0
    last_sign = None
    for i,a in enumerate(frames):
        t = _number(a["t"],"timestamp",0.,time_cap+_EPS)
        step = _number(a["stepSeconds"],"step duration",0.,dt+_EPS)
        velocity = _number(a["speed"],"applied speed",0.,speed_cap)
        rate = _number(a["yawRateDegreesPerSecond"],"applied yaw rate",-yaw_cap,yaw_cap)
        position = _xyz(a["xyz"])
        yaw = _number(a["yawDegrees"],"yaw",-180.,180.)
        progress = _number(a["progress"],"progress",0.,total+_EPS)
        error = _number(a["crossTrackErrorXZ"],"cross-track error",0.)
        maximum_error = max(maximum_error,error)
        _same(t,elapsed,"frame timestamp")
        if i==0:
            for actual,expected in zip(position,initial_position):
                _same(actual,expected,"initial position")
            _same(_yaw_delta(yaw,initial_yaw),0.,"initial yaw")
            _same(progress,0.,"initial progress")
        terminal = i==len(frames)-1
        if terminal:
            if step!=0. or velocity!=0. or rate!=0.:
                raise TraceError("invalid synthetic terminal frame")
            break
        # The model clips only the last interval to its finite time budget.
        if step<=0. or error>deviation_cap:
            raise TraceError("invalid synthetic integration interval")
        _same(step,min(dt,time_cap-t),"integration step")
        if n:
            requested = (_number(a["requestedSpeed"],"requested speed",0.,speed_cap),
                         _number(a["requestedYawRateDegreesPerSecond"],"requested yaw rate",-yaw_cap,yaw_cap))
            queue.append(requested)
            expected = queue.popleft()
            if (velocity,rate)!=expected:
                raise TraceError("synthetic FIFO applied command disagrees with request history")
        elif "requestedSpeed" in a or "requestedYawRateDegreesPerSecond" in a:
            raise TraceError("synthetic requested commands lack delay declaration")
        b = frames[i+1]
        next_position = _xyz(b["xyz"])
        displacement = velocity*step
        delta_yaw = rate*step
        midpoint = math.radians(yaw+delta_yaw/2.)
        expected_position = (position[0]+displacement*math.cos(midpoint),
                             position[1],position[2]+displacement*math.sin(midpoint))
        for actual,expected in zip(next_position,expected_position):
            _same(actual,expected,"integrated position")
        _same(_yaw_delta(_number(b["yawDegrees"],"next yaw"),yaw+delta_yaw),0.,"integrated yaw")
        advance = _number(b["progress"],"next progress")-progress
        if advance < -_EPS or advance > 2.*displacement+_EPS:
            raise TraceError("synthetic progress advance violates displacement budget")
        elapsed += step
        traveled += displacement
        if velocity>0.:
            moving += step
            if abs(rate)>1.:
                turning += step
                sign = 1 if rate>0. else -1
                if sign!=last_sign:
                    turn_runs += 1
                    last_sign = sign
    if n:
        pending = delay["pendingCommands"]
        if not isinstance(pending,list) or len(pending)!=n:
            raise TraceError("invalid synthetic terminal FIFO length")
        for actual,expected in zip(pending,queue,strict=True):
            if (_number(actual["speed"],"queued speed",0.,speed_cap),
                _number(actual["yawRateDegreesPerSecond"],"queued yaw rate",-yaw_cap,yaw_cap))!=expected:
                raise TraceError("synthetic terminal queue disagrees with request history")

    # Recalculate each summary from the source geometry and observed frames.
    # Preserve existing metrics and their exact meanings; do not tune or
    # change the historical report serialization.
    endpoint = math.hypot(position[0]-goal[0],position[2]-goal[2])
    expected = {"elapsedSeconds":elapsed,"simulatedDistanceXZ":traveled,
                "forwardSeconds":moving,"forwardDutyRatio":moving/elapsed if elapsed else 0.,
                "meanSpeedSyntheticUnitsPerSecond":traveled/elapsed if elapsed else 0.,
                "meanMovingSpeedSyntheticUnitsPerSecond":traveled/moving if moving else 0.,
                "turningWhileForwardSeconds":turning,"maxCrossTrackErrorXZ":maximum_error,
                "routeLengthXZ":total,"finalXZError":endpoint,"finalProgress":progress}
    for key,value in expected.items():
        _same(metrics[key],value,key)
    if type(metrics["turnSignRuns"]) is not int or metrics["turnSignRuns"]!=turn_runs:
        raise TraceError("synthetic turn count disagrees with trajectory")
    if metrics["withinDeclaredXZTolerance"] is not (endpoint<=tolerance):
        raise TraceError("synthetic endpoint tolerance flag disagrees")
    arrived = status=="synthetic-arrived"
    if metrics["syntheticArrival"] is not arrived:
        raise TraceError("synthetic arrival status disagrees")
    if arrived and (endpoint>tolerance or progress<total-tolerance or error>deviation_cap):
        raise TraceError("synthetic arrival violates endpoint/progress requirement")
    if status=="cross-track-limit" and error<=deviation_cap:
        raise TraceError("synthetic deviation failure disagrees with terminal frame")
    if status=="time-budget-exhausted":
        _same(elapsed,time_cap,"exhausted time budget")
