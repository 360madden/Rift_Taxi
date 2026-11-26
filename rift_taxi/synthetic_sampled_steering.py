"""Closed-loop research: sampled observations drive an ideal synthetic plant.

Unlike fixed-trajectory replay, each requested velocity changes future
captures. Plant truth is kept outside the controller, which receives only
delivered immutable observations and its own request history. This is a
separate bounded model, not a live controller or production policy change.
"""
import argparse
from collections import deque
from dataclasses import dataclass
from itertools import product
import json
import math
from pathlib import Path

from .contracts import TraceError
from .simulation import _predict_pending_pose, _sharp_vertices, _turn_limited_speed, _bounded_number
from .simulation_holdout import _case_trace
from .steering import _angle_delta, _lookahead_point, _project, _segments, _xz_distance
from .synthetic_observation_replay import DT, MAX_POSE_AGE, PROFILES, TICKS, delivery_tick
from .synthetic_journey_batch import paired_metrics
from .synthetic_response_estimator import ResponseEstimator, NOMINAL
from .synthetic_response_estimator_v2 import RobustResponseEstimator
from .synthetic_sensor_noise import measurement, PROFILES as NOISE_PROFILES
from .synthetic_corner_certificate import AXIS_ERROR_BOUND, worst_case_distance_xz
from .synthetic_corner_speed import BASE_GAIN, EXTRA_GAIN, KNEE_XZ, tapered_corner_cap

MODES = ("held-pose", "predict-application", "predict-age-cap")
MAX_TICKS = 640  # 40 synthetic seconds, before terminal queue drain.
LOOKAHEAD = 1.5
MAX_ERROR = 2.
ZERO = (0., 0.)
CORNER_POLICIES = ("legacy","bounded","bounded-taper")
CORNER_APPROACH_GAIN = BASE_GAIN  # preserve the established bounded approach

# Author the comparison geometry and profiles before inspecting outcomes.
ROUTES = (
    ("sampled-long-s", ((0,0,0),(6,0,0),(10,0,4),(17,0,4),(22,0,7))),
    ("sampled-sharp-return", ((0,0,0),(6,0,0),(2,0,2),(8,0,5),(14,0,5))),
)
SPEEDS = (2.5, 3.5)
DELAYS = (0, 3)


@dataclass(frozen=True)
class Observation:
    """Immutable sample in the common synthetic tick epoch, not delivery time."""
    tick: int
    xyz: tuple
    yaw: float


def arrival_tick(capture, profile):
    """Reuse fixed transport schedules, with one initial fault window.

    Steady/jitter/stale patterns continue for the whole run. Dropout and
    reorder events occur once at the original capture indices. Use the
    original replay function for its first 64 captures and its period for
    later captures, rather than duplicate the delay definitions.
    """
    if type(capture) is not int or not 0 <= capture <= MAX_TICKS:
        raise TraceError("capture tick outside sampled approach")
    local = capture if capture < TICKS else capture % 4
    due = delivery_tick(local, profile)
    return None if due is None else capture + due - local


def _actuator_gain(value, label):
    """Bound research-only dimensionless velocity/rate response multipliers."""
    return _bounded_number(value, label, .5, 1.5)


def _response_change(value):
    """One optional piecewise-constant actuator change, applied at a plant tick.

    The switch belongs to the plant only; it is never given to the predictor.
    A queued request experiences the response in effect when it is applied,
    including commands still pending at STOP. Fixed latency remains unchanged.
    """
    if value is None:
        return None
    if (not isinstance(value,(tuple,list)) or len(value)!=3
            or type(value[0]) is not int or not 1 <= value[0] <= MAX_TICKS+10):
        raise TraceError("invalid synthetic actuator change")
    return (value[0],_actuator_gain(value[1],"changed speed gain"),
            _actuator_gain(value[2],"changed yaw gain"))


def _gains_at(tick, initial_v, initial_r, change):
    return change[1:] if change is not None and tick >= change[0] else (initial_v,initial_r)


class SampledController:
    """Route progress uses delivered positions only, never forecast or plant truth.

    Decisions run every nominal tick on the latest admitted sample. Prediction
    integrates the controller's own historical commands under the known ideal
    FIFO delay; the age-cap variant additionally reduces positive velocity
    linearly with sample age, with a 25% floor before the hard expiry gate.
    This fixed heuristic is a research candidate, not an optimized threshold.
    """
    def __init__(self, trace, speed, rate, delay, mode, *, speed_gain=1., yaw_gain=1.,
                 corner_policy="legacy"):
        self.trace = trace
        # Here delay and gains belong to the controller estimate ONLY. No
        # actual plant parameters are visible to the decision algorithm.
        self.speed, self.rate, self.delay, self.mode = speed, rate, delay, mode
        self.speed_gain, self.yaw_gain = speed_gain, yaw_gain
        if corner_policy not in CORNER_POLICIES:
            raise TraceError("invalid synthetic corner policy")
        self.corner_policy = corner_policy
        self.cumulative, self.total = _segments(trace.points)
        self.sharp = _sharp_vertices(trace.points, self.cumulative)
        self.cursor = 0
        self.progress = 0.
        self.error = 0.
        self.passed_arc = 0.
        self.rejoining = False
        self.latest = None
        self.status = None
        self.witnesses = []
        self.admissions = []

    def expire(self, tick):
        # A missing first sample is also bounded. STOP is latched, and no
        # subsequent packet or forecast can rearm this experimental run.
        if self.status is None:
            age = (tick - (self.latest.tick if self.latest else 0)) * DT
            if age > MAX_POSE_AGE:
                self.status = "observation-expired" if self.latest else "initial-observation-timeout"

    def observe(self, sample, tick):
        """Admit one source sample; update local arc and sharp witnesses."""
        if self.status is not None:
            return
        if sample.tick > tick or (tick-sample.tick)*DT > MAX_POSE_AGE:
            self.status = "observation-stale"
            return
        previous = self.latest
        if previous is not None and sample.tick <= previous.tick:
            self.status = "observation-sequence-rollback"
            return
        # Sparse samples only earn twice the measured source-to-source chord,
        # not the hidden plant's traveled distance between those samples.
        budget = 0. if previous is None else 2.*_xz_distance(previous.xyz, sample.xyz)
        low, high = self.progress, min(self.total, self.progress+budget)
        if self.cursor < len(self.sharp):
            high = min(high, self.sharp[self.cursor][1])
        low = min(high, max(low, self.passed_arc))
        self.progress, self.error = _project(
            self.trace.points, self.cumulative, sample.xyz, low, high)
        self.latest = sample
        self.admissions.append({"captureTick": sample.tick, "deliveryTick": tick,
                                "progress": self.progress, "budget": budget,
                                "crossTrackErrorXZ": self.error})
        if self.cursor < len(self.sharp):
            index, arc = self.sharp[self.cursor]
            radius = min(.10*LOOKAHEAD, .5*self.trace.arrival_tolerance_xz)
            vertex = self.trace.points[index].xyz
            upper = (worst_case_distance_xz(sample.xyz,vertex) if self.corner_policy!="legacy"
                     else _xz_distance(sample.xyz,vertex))
            # Certify the captured position against the declared rectangle,
            # without exposing truth or the hidden noise profile.
            if arc-self.progress <= radius and upper <= radius:
                self.witnesses.append({"vertexIndex": index, "captureTick": sample.tick,
                                       "deliveryTick": tick, "progress": self.progress,
                                       **({"upperDistanceXZ":upper,"radiusXZ":radius}
                                          if self.corner_policy!="legacy" else {})})
                self.cursor += 1
                self.passed_arc = arc
                self.rejoining = False
        if self.error > MAX_ERROR:
            self.status = "observed-cross-track-limit"

    def decide(self, tick, requests):
        """Return a bounded velocity/rate pair and diagnostic control pose."""
        if self.status is not None or self.latest is None:
            return ZERO, None
        sample = self.latest
        tol = self.trace.arrival_tolerance_xz
        goal = self.trace.points[-1].xyz
        observed_distance = _xz_distance(sample.xyz, goal)
        if (observed_distance <= tol and self.progress >= self.total-tol
                and self.cursor == len(self.sharp)):
            # Observation-based arrival is only a stop request. The model
            # must still drain its actual FIFO and independently check truth.
            self.status = "observed-arrival"
            return ZERO, None
        position, yaw = sample.xyz, sample.yaw
        if self.mode != "held-pose":
            # At plant interval j the request j-delay is applied. From the
            # source epoch through the application of our next request, all
            # such indices refer to already-issued commands or initial zeros.
            history = (requests[j-self.delay] if j >= self.delay else ZERO
                       for j in range(sample.tick, tick+self.delay))
            known = ((v*self.speed_gain, r*self.yaw_gain) for v,r in history)
            position, yaw = _predict_pending_pose(position, yaw, known, DT)
        distance = _xz_distance(position, goal)
        arc = min(self.total, self.progress+LOOKAHEAD)
        if self.cursor < len(self.sharp):
            arc = min(arc, self.sharp[self.cursor][1])
        target = _lookahead_point(self.trace.points, self.cumulative, arc)
        dx, dz = target[0]-position[0], target[2]-position[2]
        chord = math.hypot(dx, dz)
        if self.rejoining and self.error <= .15*LOOKAHEAD:
            self.rejoining = False
        if not self.rejoining and chord <= .20*LOOKAHEAD and self.error > .35*LOOKAHEAD:
            self.rejoining = True
        if self.rejoining:
            target = _lookahead_point(self.trace.points, self.cumulative, self.progress)
            dx, dz = target[0]-position[0], target[2]-position[2]
            chord = math.hypot(dx, dz)
        # Narrow terminal rejoin follows the existing observed-progress gate.
        terminal_rejoin = (self.mode != "held-pose" and arc == self.total
                           and self.cursor == len(self.sharp) and self.progress < self.total-tol
                           and observed_distance <= tol and distance <= .1*tol)
        if terminal_rejoin:
            target = _lookahead_point(self.trace.points, self.cumulative, self.progress)
            dx, dz = target[0]-position[0], target[2]-position[2]
            chord = math.hypot(dx, dz)
        pending_corner = (self.cursor < len(self.sharp) and arc == self.sharp[self.cursor][1]
                          and not self.rejoining)
        if chord <= 1e-9:
            if self.corner_policy!="legacy" and pending_corner:
                # A zero forecast chord is not passage evidence.
                return ZERO, {"xyz":list(position),"yaw":yaw,"sourceTick":sample.tick,
                              "targetXYZ":list(target)}
            self.status = "lookahead-degenerate"
            return ZERO, None
        heading = _angle_delta(math.degrees(math.atan2(dz, dx)), yaw)
        rate = max(-self.rate, min(self.rate, 5.*heading))
        velocity = self.speed if abs(heading) < 85. else 0.
        if velocity:
            velocity = _turn_limited_speed(velocity, heading, chord, self.rate)
        if pending_corner or terminal_rejoin:
            velocity = min(velocity, chord/DT)
            if pending_corner and self.corner_policy!="legacy":
                # Local braking does not relax spatial or arc admission.
                cap = (tapered_corner_cap(chord) if self.corner_policy=="bounded-taper"
                       else CORNER_APPROACH_GAIN*chord)
                velocity = min(velocity, cap)
        elif self.total-self.progress <= LOOKAHEAD:
            velocity = min(velocity, max(.15, 2.*distance), distance/DT)
        if self.mode == "predict-age-cap":
            # Only the experimental candidate changes speed. The hard
            # expiry/arrival/progress gates are identical across all modes.
            velocity *= max(.25, 1.-(tick-sample.tick)*DT/MAX_POSE_AGE)
        return (velocity, rate), {"xyz": list(position), "yaw": yaw,
                                  "sourceTick": sample.tick, "targetXYZ": list(target)}


def run(trace, *, speed=3., rate=100., delay=0, profile="immediate", mode="held-pose",
        assumed_delay=None, actual_speed_gain=1., actual_yaw_gain=1.,
        assumed_speed_gain=1., assumed_yaw_gain=1., adaptive=False,
        response_change=None, adaptive_policy="legacy", sensor_noise="none",
        corner_policy="legacy"):
    """Run closed-loop approach, then real model FIFO drain and zero witness.

    Optional gain multipliers are constant ideal actuator response errors,
    not inertia, friction, collision or physical measurements. Assumed delay
    defaults to the actual delay for legacy exact-model runs; assumed gains
    default to unit response. Only the plant applies actual gains.
    The opt-in adaptive predictor starts from a fixed nominal model, then
    learns only from admitted consecutive source poses and issued commands.
    response_change=(tick, speed_gain, yaw_gain) is an optional step change
    in the plant, with the same fixed command delay; no advance notice.
    Optional sensor_noise changes only captured measurements. The robust
    adaptive policy is experimental; original output is preserved by default.
    corner_policy="bounded" uses a fixed research error envelope and local
    velocity cap, not hidden sensor metadata or plant truth.
    "bounded-taper" preserves the same certificate and near-corner cap,
    allowing a higher cap only beyond a fixed forecast-chord knee.
    Only a synthetic flat route with bounded coordinates is admitted. All
    actual frame states are retained for independent internal consistency
    checks; reports do not claim collision clearance or physical stopping.
    """
    if (trace.source_type != "synthetic" or trace.frame.get("frameId") != "synthetic-local-xyz"
            or len(trace.points) < 2 or not trace.poses
            or any(p.kind in {"mandatory_passage", "hard_stop"} for p in trace.points)):
        raise TraceError("sampled model requires an unconstrained synthetic route")
    speed = _bounded_number(speed, "speed", .1, 20.)
    rate = _bounded_number(rate, "yaw rate", 10., 720.)
    tol = _bounded_number(trace.arrival_tolerance_xz, "arrival tolerance", .01, 5.)
    if type(delay) is not int or not 0 <= delay <= 10 or mode not in MODES or profile not in PROFILES:
        raise TraceError("invalid sampled model mode, profile or delay")
    seed = trace.poses[0]
    if seed.actor_yaw_deg is None or not math.isfinite(seed.actor_yaw_deg):
        raise TraceError("invalid seed heading")
    for xyz in (seed.xyz, *(p.xyz for p in trace.points)):
        if len(xyz) != 3 or any(not math.isfinite(v) or abs(v) > 1e6 for v in xyz) or xyz[1] != seed.xyz[1]:
            raise TraceError("sampled model requires finite flat geometry")
    cumulative, total = _segments(trace.points)
    if total <= tol or any(b-a <= 1e-9 for a,b in zip(cumulative, cumulative[1:])):
        raise TraceError("invalid sampled route segments")
    if corner_policy not in CORNER_POLICIES:
        raise TraceError("invalid sampled corner policy")
    if (adaptive_policy not in ("legacy","robust") or sensor_noise not in NOISE_PROFILES
            or (adaptive_policy != "legacy" and adaptive is not True)):
        raise TraceError("invalid sampled estimator or sensor profile")
    if type(adaptive) is not bool or (adaptive and mode != "predict-application"):
        raise TraceError("adaptive research requires predictive application mode")
    if assumed_delay is None:
        assumed_delay = NOMINAL[0] if adaptive else delay
    if type(assumed_delay) is not int or not 0 <= assumed_delay <= 10:
        raise TraceError("invalid assumed sampled delay")
    actual_speed_gain = _actuator_gain(actual_speed_gain,"actual speed gain")
    actual_yaw_gain = _actuator_gain(actual_yaw_gain,"actual yaw gain")
    assumed_speed_gain = _actuator_gain(assumed_speed_gain,"assumed speed gain")
    assumed_yaw_gain = _actuator_gain(assumed_yaw_gain,"assumed yaw gain")
    change = _response_change(response_change)
    if adaptive and (assumed_delay, assumed_speed_gain, assumed_yaw_gain) != NOMINAL:
        raise TraceError("adaptive research starts with the fixed nominal model")
    # Explicit opt-in declaration only when parameters depart from the
    # legacy default. Baseline estimates are meaningless and must not vary.
    if mode == "held-pose" and (assumed_delay != delay or assumed_speed_gain != 1. or assumed_yaw_gain != 1.):
        raise TraceError("held-pose mode does not use actuator estimates")
    model = {"assumedDelaySteps": assumed_delay,
             "actualSpeedGain": actual_speed_gain, "actualYawGain": actual_yaw_gain,
             "assumedSpeedGain": assumed_speed_gain, "assumedYawGain": assumed_yaw_gain}
    extended = (assumed_delay != delay or any(model[key] != 1. for key in
                ("actualSpeedGain","actualYawGain","assumedSpeedGain","assumedYawGain")))
    controller = SampledController(trace, speed, rate, assumed_delay, mode,
                                   speed_gain=assumed_speed_gain, yaw_gain=assumed_yaw_gain,
                                   corner_policy=corner_policy)
    estimator = (RobustResponseEstimator() if adaptive_policy=="robust" else ResponseEstimator()) if adaptive else None
    position, yaw = seed.xyz, _angle_delta(seed.actor_yaw_deg, 0.)
    # Truth at capture is kept outside the controller, for retrospective
    # scoring of noisy corner observations only.
    capture_truth = []
    pending = deque([ZERO]*delay)
    requests, frames = [], []
    deliveries = {}
    delivered = []
    for tick in range(MAX_TICKS+1):
        # The transport is the only path from plant truth to controller.
        due = arrival_tick(tick, profile)
        capture_truth.append(tuple(position))
        if due is not None:
            measured_xyz, measured_yaw = measurement(tick, position, yaw, sensor_noise)
            deliveries.setdefault(due, []).append(Observation(tick, measured_xyz, measured_yaw))
        controller.expire(tick)
        for obs in deliveries.pop(tick, []):
            delivered.append({"captureTick": obs.tick, "deliveryTick": tick})
            count = len(controller.admissions)
            controller.observe(obs, tick)
            if estimator is not None and len(controller.admissions) > count:
                # The estimator gets neither actual gain nor current truth;
                # the capture may precede its delivery by several ticks.
                estimator.observe(obs.tick, obs.xyz, obs.yaw, tick, requests)
        response = None
        if estimator is not None:
            response = estimator.estimate(tick)
            controller.delay = response["delay"]
            controller.speed_gain = response["speedGain"]
            controller.yaw_gain = response["yawGain"]
        request, reference = controller.decide(tick, requests)
        if controller.status is None and tick == MAX_TICKS:
            controller.status = "time-budget-exhausted"
        if controller.status is not None:
            stop = {"tick": tick, "xyz": list(position), "yaw": yaw,
                    "reason": controller.status}
            break
        requests.append(request)
        pending.append(request)
        queued_v, queued_r = pending.popleft()
        gv,gr = _gains_at(tick,actual_speed_gain,actual_yaw_gain,change)
        applied = (queued_v*gv,queued_r*gr)
        frames.append({"tick": tick, "xyz": list(position), "yaw": yaw,
                       "requested": list(request), "applied": list(applied),
                       "controlPose": reference,
                       **({"responseEstimate": response} if adaptive else {})})
        position, yaw = _predict_pending_pose(position, yaw, (applied,), DT)

    # A STOP request cannot erase in-flight commands. The ideal actuator
    # applies every queued request in order, then a full stationary interval.
    # Fault termination is never counted as an arrived journey.
    drain = []
    for j,(v,r) in enumerate([*pending, ZERO]):
        gv,gr = _gains_at(stop["tick"]+j,actual_speed_gain,actual_yaw_gain,change)
        command = (v*gv,r*gr)
        position, yaw = _predict_pending_pose(position, yaw, (command,), DT)
        drain.append({"applied": list(command), "xyz": list(position), "yaw": yaw})
    final_error = _xz_distance(position, trace.points[-1].xyz)
    observed_arrival = stop["reason"] == "observed-arrival"
    # A noisy observed corner can be inside the admission radius while
    # the modeled character is outside it. Check actual source positions
    # retrospectively; never use plant truth to drive the controller.
    truth_witness_error = max((_xz_distance(capture_truth[w["captureTick"]],
        trace.points[w["vertexIndex"]].xyz) for w in controller.witnesses), default=0.)
    truth_witnesses_valid = truth_witness_error <= min(.10*LOOKAHEAD,.5*tol)
    settled = (observed_arrival and final_error <= tol and
               ((sensor_noise=="none" and corner_policy=="legacy") or truth_witnesses_valid))
    elapsed = (len(frames)+len(drain))*DT
    forward = DT*(sum(f["applied"][0] > 0. for f in frames) + sum(f["applied"][0] > 0. for f in drain))
    result = {"schema": "taxi.synthetic-sampled-steering/1", "classification": "SYNTHETIC_ONLY",
              "scenarioSHA256": trace.trace_sha256, "profile": profile, "mode": mode,
              "speed": speed, "rate": rate, "actualDelaySteps": delay, "dtSeconds": DT,
              **({"actuatorModel": model} if extended else {}),
              **({"adaptiveResponse": True} if adaptive else {}),
              **({"adaptivePolicy": adaptive_policy} if adaptive_policy!="legacy" else {}),
              **({"sensorNoise": sensor_noise} if sensor_noise!="none" else {}),
              **({"cornerPolicy":{"name":corner_policy,"axisErrorBound":AXIS_ERROR_BOUND,
                                 "approachGainPerSecond":CORNER_APPROACH_GAIN,
                                 **({"extraGainPerSecond":EXTRA_GAIN,"kneeXZ":KNEE_XZ}
                                    if corner_policy=="bounded-taper" else {})}}
                 if corner_policy!="legacy" else {}),
              **({"actualResponseChange": list(change)} if change is not None else {}),
              "frames": frames, "delivered": delivered, "admissions": controller.admissions,
              "sharpWitnesses": controller.witnesses, "stop": stop, "drain": drain,
              "summary": {"finalModelSettled": settled, "observedArrival": observed_arrival,
                          "status": "model-settled" if settled else (
                              "observed-arrival-unsettled" if observed_arrival else stop["reason"]),
                          "totalElapsedSeconds": elapsed, "totalForwardDutyRatio": forward/elapsed,
                          "finalModelErrorXZ": final_error, "approachSeconds": len(frames)*DT,
                          "drainSeconds": len(drain)*DT, "sharpCornersPassed": controller.cursor,
                          **({"truthSharpWitnessesValid": truth_witnesses_valid,
                              "maxSharpWitnessTruthErrorXZ": truth_witness_error}
                              if sensor_noise!="none" or corner_policy!="legacy" else {}),
                          "maxObservedCrossTrackErrorXZ": max(
                              (a["crossTrackErrorXZ"] for a in controller.admissions), default=None)},
              "gameInputSent": False, "physicalQualification": False}
    verify(result, trace)
    return result


def verify(result, trace):
    """Independently reconstruct actual integration, forecast and admission bounds.

    Checks the actual applied history, source epoch/delivery mapping, forecast
    from recorded source pose and past requests, displacement-budget progress,
    and post-STOP FIFO drain. This is internal consistency, not a complete
    independent implementation of every steering decision.
    """
    def insist(ok, reason):
        if not ok:
            raise TraceError("sampled model audit: "+reason)

    def same(a, b):
        return math.isclose(a, b, abs_tol=1e-8, rel_tol=0.)

    def integrate(xyz, yaw, command):
        v, r = command
        heading = math.radians(yaw+r*DT/2.)
        return (xyz[0]+v*DT*math.cos(heading), xyz[1],
                xyz[2]+v*DT*math.sin(heading)), (yaw+r*DT+180.)%360.-180.

    def check_pose(xyz, yaw, row):
        insist(all(same(a,b) for a,b in zip(xyz,row["xyz"], strict=True))
               and same(_angle_delta(yaw,row["yaw"]),0.), "pose integration")

    frames, stop, drain = result["frames"], result["stop"], result["drain"]
    delay = result["actualDelaySteps"]
    mode = result["mode"]
    insist(type(delay) is int and 0 <= delay <= 10 and mode in MODES, "actual delay/mode")
    declared = result.get("actuatorModel")
    if "actuatorModel" in result:
        insist(isinstance(declared,dict) and set(declared) == {
            "assumedDelaySteps","actualSpeedGain","actualYawGain","assumedSpeedGain","assumedYawGain"},
            "actuator declaration shape")
        estimate = declared["assumedDelaySteps"]
        insist(type(estimate) is int and 0 <= estimate <= 10, "assumed delay")
        av, ar, ev, er = (_actuator_gain(declared[k],k) for k in
                         ("actualSpeedGain","actualYawGain","assumedSpeedGain","assumedYawGain"))
        insist(estimate != delay or (av,ar,ev,er) != (1.,1.,1.,1.), "redundant actuator declaration")
    else:
        estimate, av, ar, ev, er = delay, 1., 1., 1., 1.
    insist(mode != "held-pose" or (estimate == delay and (ev,er) == (1.,1.)), "baseline estimate")
    change = _response_change(result.get("actualResponseChange"))
    insist("actualResponseChange" not in result or change is not None,"response change declaration")
    adaptive = "adaptiveResponse" in result
    insist(not adaptive or (result["adaptiveResponse"] is True and mode == "predict-application"
                             and (estimate,ev,er) == NOMINAL), "adaptive initial model")
    policy = result.get("adaptivePolicy","legacy")
    noise = result.get("sensorNoise","none")
    bounded_corners = "cornerPolicy" in result
    taper = False
    if bounded_corners:
        declaration = result["cornerPolicy"]
        insist(isinstance(declaration,dict) and declaration.get("name") in
               ("bounded","bounded-taper"), "corner policy name")
        taper = declaration["name"]=="bounded-taper"
        insist(declaration=={"name":declaration["name"],"axisErrorBound":AXIS_ERROR_BOUND,
                            "approachGainPerSecond":CORNER_APPROACH_GAIN,
                            **({"extraGainPerSecond":EXTRA_GAIN,"kneeXZ":KNEE_XZ}
                               if taper else {})}, "corner policy declaration")
    insist(("adaptivePolicy" not in result or (adaptive and policy=="robust")) and
           policy in ("legacy","robust"), "adaptive policy declaration")
    insist(noise in NOISE_PROFILES and ("sensorNoise" not in result or noise!="none"), "sensor profile declaration")
    estimator = (RobustResponseEstimator() if policy=="robust" else ResponseEstimator()) if adaptive else None
    insist(len(frames) == stop["tick"] <= MAX_TICKS and len(drain) == delay+1, "bounded duration")
    requests = [f["requested"] for f in frames]
    truth = [*frames, stop]
    measured = [measurement(i,f["xyz"],f["yaw"],noise) for i,f in enumerate(truth)]
    position, yaw = trace.poses[0].xyz, _angle_delta(trace.poses[0].actor_yaw_deg,0.)
    # Rebuild expected delivery order directly from source indices, including
    # the terminal observation tick but never future captures.
    expected = [{"captureTick": i, "deliveryTick": due} for i in range(stop["tick"]+1)
                if (due := arrival_tick(i, result["profile"])) is not None and due <= stop["tick"]]
    expected.sort(key=lambda row: (row["deliveryTick"], row["captureTick"]))
    insist(expected == result["delivered"], "transport schedule")
    expected_pairs = {(a["captureTick"], a["deliveryTick"]) for a in expected}
    admitted = result["admissions"]
    cumulative,total = _segments(trace.points)
    sharp = _sharp_vertices(trace.points,cumulative)
    cursor = 0
    passed_arc = 0.
    verified_witnesses = []
    previous = None
    for a in admitted:
        i, tick = a["captureTick"], a["deliveryTick"]
        insist((i, tick) in expected_pairs
               and (tick-i)*DT <= MAX_POSE_AGE and (previous is None or i>previous["captureTick"]),
               "observation admission")
        budget = 0. if previous is None else 2.*_xz_distance(
            measured[i][0],measured[previous["captureTick"]][0])
        prior = 0. if previous is None else previous["progress"]
        insist(same(a["budget"],budget) and prior-1e-8 <= a["progress"] <= prior+budget+1e-8,
               "observed progress budget")
        # Independently recompute eligible arc projection from source frames,
        # and require each sharp witness to come from a delivered sample.
        low, high = prior, min(total, prior+budget)
        if cursor < len(sharp):
            high = min(high, sharp[cursor][1])
        low = min(high, max(low, passed_arc))
        progress,error = _project(trace.points,cumulative,measured[i][0],low,high)
        insist(same(a["progress"],progress) and same(a["crossTrackErrorXZ"],error),
               "observed projection")
        if cursor < len(sharp):
            index,arc = sharp[cursor]
            radius = min(.10*LOOKAHEAD,.5*trace.arrival_tolerance_xz)
            vertex = trace.points[index].xyz
            if bounded_corners:
                # Independent enumeration of the four rectangle corners.
                dx = measured[i][0][0]-vertex[0]
                dz = measured[i][0][2]-vertex[2]
                upper = max(math.hypot(dx+sx*AXIS_ERROR_BOUND,dz+sz*AXIS_ERROR_BOUND)
                            for sx in (-1,1) for sz in (-1,1))
            else:
                upper = _xz_distance(measured[i][0],vertex)
            if arc-progress <= radius and upper <= radius:
                if bounded_corners:
                    insist(_xz_distance(truth[i]["xyz"],vertex)<=radius,"corner certificate truth")
                verified_witnesses.append({"vertexIndex":index,"captureTick":i,
                                            "deliveryTick":tick,"progress":progress,
                                            **({"upperDistanceXZ":upper,"radiusXZ":radius}
                                               if bounded_corners else {})})
                cursor += 1
                passed_arc = arc
        previous = a
    insist(verified_witnesses == result["sharpWitnesses"], "sharp passage witnesses")
    admission_cursor = 0
    latest = None
    # Reconstruct only the tapered candidate's corner approach decisions.
    # Older receipt schemas and steering modes keep their existing verifier.
    taper_cursor = 0
    taper_rejoining = False
    for i, f in enumerate(frames):
        insist(f["tick"] == i, "frame tick")
        check_pose(position,yaw,f)
        v,r = requests[i]
        insist(0. <= v <= result["speed"] and abs(r) <= result["rate"], "request bound")
        v,r = requests[i-delay] if i>=delay else ZERO
        gv,gr = _gains_at(i,av,ar,change)
        applied = [v*gv,r*gr]
        insist(f["applied"] == applied, "actual command FIFO and actuator gains")
        while admission_cursor < len(admitted) and admitted[admission_cursor]["deliveryTick"] <= i:
            latest = admitted[admission_cursor]["captureTick"]
            if estimator is not None:
                # Independently rebuild the causal estimator feed, limiting
                # the command list to already-issued requests at delivery.
                delivery = admitted[admission_cursor]["deliveryTick"]
                estimator.observe(latest, measured[latest][0], measured[latest][1],
                                  delivery, requests[:delivery])
            admission_cursor += 1
        if estimator is not None:
            learned = estimator.estimate(i)
            insist(f.get("responseEstimate") == learned, "causal response estimate")
            estimate, ev, er = learned["delay"], learned["speedGain"], learned["yawGain"]
        else:
            insist("responseEstimate" not in f, "unexpected response estimate")
        ref = f["controlPose"]
        if latest is None:
            insist(ref is None and requests[i] == list(ZERO), "motion before observation")
        else:
            insist(ref is not None and ref["sourceTick"] == latest and (i-latest)*DT <= MAX_POSE_AGE,
                   "reference source age")
            px, pyaw = measured[latest]
            if mode != "held-pose":
                for j in range(latest,i+estimate):
                    v,r = requests[j-estimate] if j>=estimate else ZERO
                    px,pyaw = integrate(px,pyaw,(v*ev,r*er))
            check_pose(px,pyaw,ref)
            if taper:
                # Each delivered witness advances the same ordered corner
                # cursor and clears rejoin state. Neither a future witness
                # nor the actual plant position can change the speed cap.
                while (taper_cursor < len(verified_witnesses) and
                       verified_witnesses[taper_cursor]["deliveryTick"] <= i):
                    taper_cursor += 1
                    taper_rejoining = False
                admission = admitted[admission_cursor-1]
                progress = admission["progress"]
                error = admission["crossTrackErrorXZ"]
                arc = min(total,progress+LOOKAHEAD)
                if taper_cursor < len(sharp):
                    arc = min(arc,sharp[taper_cursor][1])
                target = _lookahead_point(trace.points,cumulative,arc)
                chord = _xz_distance(px,target)
                if taper_rejoining and error<=.15*LOOKAHEAD:
                    taper_rejoining = False
                if not taper_rejoining and chord<=.20*LOOKAHEAD and error>.35*LOOKAHEAD:
                    taper_rejoining = True
                if taper_rejoining:
                    target = _lookahead_point(trace.points,cumulative,progress)
                tol = trace.arrival_tolerance_xz
                goal = trace.points[-1].xyz
                if (mode!="held-pose" and arc==total and taper_cursor==len(sharp)
                        and progress<total-tol and _xz_distance(measured[latest][0],goal)<=tol
                        and _xz_distance(px,goal)<=.1*tol):
                    target = _lookahead_point(trace.points,cumulative,progress)
                insist(all(same(a,b) for a,b in zip(target,ref["targetXYZ"],strict=True)),
                       "tapered corner target")
                if (taper_cursor<len(sharp) and arc==sharp[taper_cursor][1]
                        and not taper_rejoining):
                    chord = _xz_distance(px,target)
                    cap = (BASE_GAIN*chord if chord<=KNEE_XZ else
                           (BASE_GAIN+EXTRA_GAIN)*chord-EXTRA_GAIN*KNEE_XZ)
                    insist(requests[i][0]<=min(chord/DT,cap)+1e-8,
                           "tapered corner approach speed cap")
        position,yaw = integrate(position,yaw,applied)
    check_pose(position,yaw,stop)
    for j,row in enumerate(drain):
        index = len(frames)+j-delay
        v,r = requests[index] if 0 <= index < len(frames) else ZERO
        gv,gr = _gains_at(len(frames)+j,av,ar,change)
        cmd = [v*gv,r*gr]
        insist(row["applied"] == cmd, "terminal FIFO drain and actuator gains")
        position,yaw = integrate(position,yaw,cmd)
        check_pose(position,yaw,row)
    insist(drain[-1]["applied"] == list(ZERO), "stationary witness")
    summary = result["summary"]
    error = _xz_distance(position,trace.points[-1].xyz)
    insist(same(summary["finalModelErrorXZ"],error), "terminal error")
    arrived = stop["reason"] == "observed-arrival"
    if arrived:
        tol = trace.arrival_tolerance_xz
        insist(previous is not None and
               (stop["tick"]-previous["captureTick"])*DT <= MAX_POSE_AGE and
               previous["progress"] >= total-tol and cursor == len(sharp) and
               previous["crossTrackErrorXZ"] <= MAX_ERROR and
               _xz_distance(measured[previous["captureTick"]][0],trace.points[-1].xyz) <= tol,
               "observed arrival lacks source witness")
    elapsed = (len(frames)+len(drain))*DT
    moving = DT*sum(row["applied"][0] > 0. for row in [*frames,*drain])
    insist(same(summary["totalElapsedSeconds"],elapsed) and
           same(summary["totalForwardDutyRatio"],moving/elapsed) and
           same(summary["approachSeconds"],len(frames)*DT) and
           same(summary["drainSeconds"],len(drain)*DT), "time/duty accounting")
    insist(summary["sharpCornersPassed"] == cursor and summary["observedArrival"] is arrived,
           "arrival/witness accounting")
    truth_witness_error = max((_xz_distance(truth[w["captureTick"]]["xyz"],
        trace.points[w["vertexIndex"]].xyz) for w in verified_witnesses), default=0.)
    truth_witnesses_valid = truth_witness_error <= min(.10*LOOKAHEAD,.5*trace.arrival_tolerance_xz)
    if noise!="none" or bounded_corners:
        insist(same(summary["maxSharpWitnessTruthErrorXZ"],truth_witness_error) and
               summary["truthSharpWitnessesValid"] is truth_witnesses_valid,"noisy truth witness scoring")
    insist(summary["finalModelSettled"] == (arrived and error<=trace.arrival_tolerance_xz
           and ((noise=="none" and not bounded_corners) or truth_witnesses_valid)), "false settled arrival")
    insist(result["gameInputSent"] is False and result["physicalQualification"] is False, "classification")


def evaluate():
    """56 plant conditions, 168 paired runs; retain compact results of all runs."""
    rows = []
    for (name, points), speed, delay, profile in product(ROUTES,SPEEDS,DELAYS,PROFILES):
        trace = _case_trace({"routeId": name, "routeXYZ": [list(p) for p in points],
                             "initialXYZ": [0.,0.,.15], "initialYawDegrees": 5.},
                            generator="taxi-sampled-steering-20261126-v1")
        results = {}
        for mode in MODES:
            report = run(trace,speed=speed,delay=delay,profile=profile,mode=mode)
            key = "baseline" if mode == "held-pose" else mode
            results[key] = {"summary": report["summary"], "stop": report["stop"],
                            "admittedSamples": len(report["admissions"])}
        rows.append({"route": name, "scenarioSHA256": trace.trace_sha256,
                     "speed": speed, "actualDelaySteps": delay, "profile": profile,
                     "results": results})
    groups = []
    for profile, delay in product(PROFILES,DELAYS):
        matched = [r for r in rows if r["profile"] == profile and r["actualDelaySteps"] == delay]
        groups.append({"profile": profile, "actualDelaySteps": delay,
                       "comparisons": {m: paired_metrics(matched,m) for m in MODES[1:]}})
    return {"schema":"taxi.synthetic-sampled-steering-study/1", "classification":"SYNTHETIC_ONLY",
            "caseCount":len(rows), "executionCount":len(rows)*len(MODES),
            "groups":groups, "rows":rows, "gameInputSent":False, "physicalQualification":False,
            "limitations":["Separate research controller, not the legacy journey engine.",
                           "Exact fixed command delay and ideal known actuator, not physical telemetry.",
                           "Terminal queue drains without active correction; no live arrival claim."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.out is not None and args.out.exists():
            raise FileExistsError(args.out)
        result = evaluate()
        if args.out is not None:
            with args.out.open("x",encoding="utf-8",newline="\n") as f:
                f.write(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
        if args.summary or args.out is None:
            view = {k:v for k,v in result.items() if k!="rows"} if args.summary else result
            print(json.dumps(view,sort_keys=True,indent=2,allow_nan=False))
        return 0
    except (TraceError,ValueError,OSError) as exc:
        parser.exit(2,f"Sampled steering refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
