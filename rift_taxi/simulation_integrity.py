"""Independent consistency audit of generated synthetic trajectories.

Entry point: verify_synthetic_trajectory(result, trace). No file I/O,
native process access, control output or real-world observation.
Check ideal midpoint integration, FIFO semantics, and ordered bounded arc
projection against recorded frames, then recalculate report metrics. This is an internal
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


def _reference_projection(points, arcs, position, low, high):
    """Independent full-segment scan of the declared local XZ arc interval.

    Do not call the simulator's indexed projector: the verifier must detect
    errors in its segment selection and crossing tie-break. Earliest arc
    wins equal-distance ties, including a zero-width progress window.
    """
    best = None
    for i, (a,b) in enumerate(zip(points,points[1:])):
        length = arcs[i+1]-arcs[i]
        if arcs[i+1] < low or arcs[i] > high or length <= 1e-12:
            continue
        left = max(0., (low-arcs[i])/length)
        right = min(1., (high-arcs[i])/length)
        if left > right:
            continue
        dx, dz = b[0]-a[0], b[2]-a[2]
        fraction = ((position[0]-a[0])*dx+(position[2]-a[2])*dz)/(length*length)
        fraction = max(left,min(right,fraction))
        x,z = a[0]+fraction*dx,a[2]+fraction*dz
        candidate = (math.hypot(position[0]-x,position[2]-z), arcs[i]+fraction*length)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise TraceError("synthetic audit has no admissible projection")
    return max(low,min(high,best[1])),best[0]


def _reference_sharp_vertices(points, arcs):
    """Reconstruct ordered reversal gates from geometry, not report metadata."""
    result = []
    for i in range(1,len(points)-1):
        a,b,c = points[i-1:i+2]
        incoming = math.degrees(math.atan2(b[2]-a[2],b[0]-a[0]))
        outgoing = math.degrees(math.atan2(c[2]-b[2],c[0]-b[0]))
        if abs(_yaw_delta(outgoing,incoming)) >= 100.:
            result.append((i,arcs[i]))
    return result


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
    lookahead = _number(model["lookaheadSyntheticUnits"],"lookahead",.1,20.)
    _same(model["projectionAdvanceBudgetFactor"],2.,"projection budget factor")
    policy = model["speedPolicy"]
    if policy not in ("fixed","turn-limited","turn-limited-rejoin","turn-limited-ordered"):
        raise TraceError("invalid synthetic speed policy")
    ordered = policy == "turn-limited-ordered"
    if (not isinstance(frames,list) or not frames
            or len(frames)>math.ceil(time_cap/dt)+1):
        raise TraceError("invalid synthetic frame count")
    tolerance = _number(trace.arrival_tolerance_xz,"arrival tolerance",.01,5.)
    points = [_xyz(p.xyz) for p in trace.points]
    if len(points)<2 or not trace.poses:
        raise TraceError("invalid synthetic source geometry")
    arcs = [0.]
    for a,b in zip(points,points[1:]):
        length = math.hypot(b[0]-a[0],b[2]-a[2])
        if not math.isfinite(length) or length <= 1e-9:
            raise TraceError("invalid synthetic source segment")
        arcs.append(arcs[-1]+length)
    total = arcs[-1]
    if not math.isfinite(total) or total <= tolerance:
        raise TraceError("invalid synthetic source route length")
    sharp = _reference_sharp_vertices(points,arcs) if ordered else []
    radius = min(.10*lookahead,.5*tolerance)
    sharp_cursor = 0
    passed_arc = 0.
    witnesses = []
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
    prediction = result.get("syntheticCommandPrediction")
    predicting = "syntheticCommandPrediction" in result
    assumed = n
    if predicting:
        if (not n or model.get("speedPolicy") != "turn-limited-ordered"
                or prediction["observedProgressOnly"] is not True):
            raise TraceError("invalid synthetic command prediction declaration")
        method = prediction["method"]
        if method == "assumed-queue-midpoint/1":
            assumed = prediction["assumedDelaySteps"]
            if type(assumed) is not int or not 1 <= assumed <= 10 or assumed == n:
                raise TraceError("invalid synthetic assumed delay")
        elif method != "queued-pose-midpoint/1" or "assumedDelaySteps" in prediction:
            raise TraceError("invalid synthetic command prediction declaration")
        _same(prediction["nominalHorizonSeconds"], assumed*dt, "prediction horizon")
    # Independently reconstruct the controller's assumed request history
    # alongside the actual FIFO. Neither forecast can alter observed motion.
    forecast_queue = deque([(0., 0.)]*assumed) if assumed != n else queue

    # Accumulate using the actual applied velocity and duration, never
    # requested motion. Stationary and turning-only intervals stay in the
    # elapsed denominator. Reconstruct next pose from each previous frame.
    elapsed = traveled = moving = turning = maximum_error = 0.
    turn_runs = 0
    last_sign = None
    # Recompute progress from the actual recorded positions, previous
    # independently projected arc, and previous applied displacement.
    # A plausible progress delta is not sufficient evidence of projection.
    audited_progress = 0.
    advance_budget = 0.
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
        low = audited_progress
        high = min(total,audited_progress+advance_budget)
        if ordered:
            if sharp_cursor < len(sharp):
                high = min(high,sharp[sharp_cursor][1])
            low = min(high,max(low,passed_arc))
        audited_progress, audited_error = _reference_projection(points,arcs,position,low,high)
        _same(progress,audited_progress,"projected progress")
        _same(error,audited_error,"projected cross-track error")
        if ordered and sharp_cursor < len(sharp):
            vertex,arc = sharp[sharp_cursor]
            x,_,z = points[vertex]
            if arc-audited_progress <= radius and math.hypot(position[0]-x,position[2]-z) <= radius:
                witnesses.append((vertex,arc,t,position,audited_progress))
                passed_arc = arc
                sharp_cursor += 1
        if ordered and not terminal:
            claimed = a["orderedSharpCornersPassed"]
            if type(claimed) is not int or claimed != sharp_cursor:
                raise TraceError("synthetic ordered frame corner count disagrees")
        elif "orderedSharpCornersPassed" in a:
            raise TraceError("unexpected synthetic ordered frame corner count")
        # Independently replay the pending FIFO before adding the new request.
        # A future pose is diagnostic only; never replace the actual frame
        # position used below for integration, progress or arrival checks.
        prediction_fields = {"predictedApplicationXYZ", "predictedApplicationYawDegrees"}
        if predicting and not terminal:
            px, py, pz = position
            forecast_yaw = yaw
            for queued_speed, queued_rate in forecast_queue:
                turn = queued_rate*dt
                direction = math.radians(forecast_yaw+turn/2.)
                px += queued_speed*dt*math.cos(direction)
                pz += queued_speed*dt*math.sin(direction)
                forecast_yaw = _yaw_delta(forecast_yaw+turn, 0.)
            for actual, expected in zip(_xyz(a["predictedApplicationXYZ"]), (px,py,pz)):
                _same(actual, expected, "predicted application XYZ")
            _same(_yaw_delta(_number(a["predictedApplicationYawDegrees"], "predicted yaw", -180., 180.),
                             forecast_yaw), 0., "predicted application yaw")
            tx, _, tz = _xyz(a["lookaheadXYZ"])
            bearing = math.degrees(math.atan2(tz-pz, tx-px))
            _same(_yaw_delta(_number(a["headingErrorDegrees"], "predicted heading error"),
                             _yaw_delta(bearing, forecast_yaw)), 0., "predicted heading error")
        elif prediction_fields.intersection(a):
            raise TraceError("unexpected synthetic prediction fields")
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
            if assumed != n:
                forecast_queue.append(requested)
                forecast_queue.popleft()
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
        advance_budget = 2.*displacement
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
    if ordered:
        recovery = result["syntheticRecovery"]
        for key,expected_count in (("orderedSharpCorners",len(sharp)),
                                   ("orderedSharpCornersPassed",sharp_cursor)):
            if type(recovery[key]) is not int or recovery[key] != expected_count:
                raise TraceError("synthetic ordered corner count disagrees")
        _same(recovery["orderedSharpCornerRadius"],radius,"ordered corner radius")
        _same(recovery["orderedSharpCornerMinimumDegrees"],100.,"ordered corner threshold")
        claimed = recovery["orderedSharpCornerPassages"]
        if not isinstance(claimed,list) or len(claimed)!=len(witnesses):
            raise TraceError("synthetic ordered corner witness coverage disagrees")
        for row,(vertex,arc,t,xyz,progress_at_pass) in zip(claimed,witnesses,strict=True):
            if (not isinstance(row,dict) or type(row["vertexIndex"]) is not int
                    or row["vertexIndex"] != vertex):
                raise TraceError("synthetic ordered corner witness vertex disagrees")
            _same(row["vertexArc"],arc,"corner witness arc")
            _same(row["t"],t,"corner witness timestamp")
            _same(row["progress"],progress_at_pass,"corner witness progress")
            for actual,expected in zip(_xyz(row["xyz"]),xyz):
                _same(actual,expected,"corner witness XYZ")
    elif isinstance(result.get("syntheticRecovery"),dict) and any(
            key.startswith("orderedSharp") for key in result["syntheticRecovery"]):
        raise TraceError("unexpected synthetic ordered corner evidence")
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
    if arrived and (endpoint>tolerance or progress<total-tolerance or error>deviation_cap
                    or (ordered and sharp_cursor!=len(sharp))):
        raise TraceError("synthetic arrival violates endpoint/progress requirement")
    if status=="cross-track-limit" and error<=deviation_cap:
        raise TraceError("synthetic deviation failure disagrees with terminal frame")
    if status=="time-budget-exhausted":
        _same(elapsed,time_cap,"exhausted time budget")
