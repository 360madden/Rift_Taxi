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

MODES = ("held-pose", "predict-application", "predict-age-cap")
MAX_TICKS = 640  # 40 synthetic seconds, before terminal queue drain.
LOOKAHEAD = 1.5
MAX_ERROR = 2.
ZERO = (0., 0.)
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


class SampledController:
    """Route progress uses delivered positions only, never forecast or plant truth.

    Decisions run every nominal tick on the latest admitted sample. Prediction
    integrates the controller's own historical commands under the known ideal
    FIFO delay; the age-cap variant additionally reduces positive velocity
    linearly with sample age, with a 25% floor before the hard expiry gate.
    This fixed heuristic is a research candidate, not an optimized threshold.
    """
    def __init__(self, trace, speed, rate, delay, mode):
        self.trace = trace
        self.speed, self.rate, self.delay, self.mode = speed, rate, delay, mode
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
            if arc-self.progress <= radius and _xz_distance(sample.xyz, self.trace.points[index].xyz) <= radius:
                self.witnesses.append({"vertexIndex": index, "captureTick": sample.tick,
                                       "deliveryTick": tick, "progress": self.progress})
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
            known = (requests[j-self.delay] if j >= self.delay else ZERO
                     for j in range(sample.tick, tick+self.delay))
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
        if chord <= 1e-9:
            self.status = "lookahead-degenerate"
            return ZERO, None
        heading = _angle_delta(math.degrees(math.atan2(dz, dx)), yaw)
        rate = max(-self.rate, min(self.rate, 5.*heading))
        velocity = self.speed if abs(heading) < 85. else 0.
        if velocity:
            velocity = _turn_limited_speed(velocity, heading, chord, self.rate)
        if (self.cursor < len(self.sharp) and arc == self.sharp[self.cursor][1]
                and not self.rejoining) or terminal_rejoin:
            velocity = min(velocity, chord/DT)
        elif self.total-self.progress <= LOOKAHEAD:
            velocity = min(velocity, max(.15, 2.*distance), distance/DT)
        if self.mode == "predict-age-cap":
            # Only the experimental candidate changes speed. The hard
            # expiry/arrival/progress gates are identical across all modes.
            velocity *= max(.25, 1.-(tick-sample.tick)*DT/MAX_POSE_AGE)
        return (velocity, rate), {"xyz": list(position), "yaw": yaw,
                                  "sourceTick": sample.tick, "targetXYZ": list(target)}


def run(trace, *, speed=3., rate=100., delay=0, profile="immediate", mode="held-pose"):
    """Run closed-loop approach, then real model FIFO drain and zero witness.

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
    controller = SampledController(trace, speed, rate, delay, mode)
    position, yaw = seed.xyz, _angle_delta(seed.actor_yaw_deg, 0.)
    pending = deque([ZERO]*delay)
    requests, frames = [], []
    deliveries = {}
    delivered = []
    for tick in range(MAX_TICKS+1):
        # The transport is the only path from plant truth to controller.
        due = arrival_tick(tick, profile)
        if due is not None:
            deliveries.setdefault(due, []).append(Observation(tick, position, yaw))
        controller.expire(tick)
        for obs in deliveries.pop(tick, []):
            delivered.append({"captureTick": obs.tick, "deliveryTick": tick})
            controller.observe(obs, tick)
        request, reference = controller.decide(tick, requests)
        if controller.status is None and tick == MAX_TICKS:
            controller.status = "time-budget-exhausted"
        if controller.status is not None:
            stop = {"tick": tick, "xyz": list(position), "yaw": yaw,
                    "reason": controller.status}
            break
        requests.append(request)
        pending.append(request)
        applied = pending.popleft()
        frames.append({"tick": tick, "xyz": list(position), "yaw": yaw,
                       "requested": list(request), "applied": list(applied),
                       "controlPose": reference})
        position, yaw = _predict_pending_pose(position, yaw, (applied,), DT)

    # A STOP request cannot erase in-flight commands. The ideal actuator
    # applies every queued request in order, then a full stationary interval.
    # Fault termination is never counted as an arrived journey.
    drain = []
    for command in [*pending, ZERO]:
        position, yaw = _predict_pending_pose(position, yaw, (command,), DT)
        drain.append({"applied": list(command), "xyz": list(position), "yaw": yaw})
    final_error = _xz_distance(position, trace.points[-1].xyz)
    observed_arrival = stop["reason"] == "observed-arrival"
    settled = observed_arrival and final_error <= tol
    elapsed = (len(frames)+len(drain))*DT
    forward = DT*(sum(f["applied"][0] > 0. for f in frames) + sum(f["applied"][0] > 0. for f in drain))
    result = {"schema": "taxi.synthetic-sampled-steering/1", "classification": "SYNTHETIC_ONLY",
              "scenarioSHA256": trace.trace_sha256, "profile": profile, "mode": mode,
              "speed": speed, "rate": rate, "actualDelaySteps": delay, "dtSeconds": DT,
              "frames": frames, "delivered": delivered, "admissions": controller.admissions,
              "sharpWitnesses": controller.witnesses, "stop": stop, "drain": drain,
              "summary": {"finalModelSettled": settled, "observedArrival": observed_arrival,
                          "status": "model-settled" if settled else (
                              "observed-arrival-unsettled" if observed_arrival else stop["reason"]),
                          "totalElapsedSeconds": elapsed, "totalForwardDutyRatio": forward/elapsed,
                          "finalModelErrorXZ": final_error, "approachSeconds": len(frames)*DT,
                          "drainSeconds": len(drain)*DT, "sharpCornersPassed": controller.cursor,
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
    insist(len(frames) == stop["tick"] <= MAX_TICKS and len(drain) == delay+1, "bounded duration")
    requests = [f["requested"] for f in frames]
    truth = [*frames, stop]
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
            truth[i]["xyz"],truth[previous["captureTick"]]["xyz"])
        prior = 0. if previous is None else previous["progress"]
        insist(same(a["budget"],budget) and prior-1e-8 <= a["progress"] <= prior+budget+1e-8,
               "observed progress budget")
        # Independently recompute eligible arc projection from source frames,
        # and require each sharp witness to come from a delivered sample.
        low, high = prior, min(total, prior+budget)
        if cursor < len(sharp):
            high = min(high, sharp[cursor][1])
        low = min(high, max(low, passed_arc))
        progress,error = _project(trace.points,cumulative,truth[i]["xyz"],low,high)
        insist(same(a["progress"],progress) and same(a["crossTrackErrorXZ"],error),
               "observed projection")
        if cursor < len(sharp):
            index,arc = sharp[cursor]
            radius = min(.10*LOOKAHEAD,.5*trace.arrival_tolerance_xz)
            if arc-progress <= radius and _xz_distance(truth[i]["xyz"],trace.points[index].xyz) <= radius:
                verified_witnesses.append({"vertexIndex":index,"captureTick":i,
                                           "deliveryTick":tick,"progress":progress})
                cursor += 1
                passed_arc = arc
        previous = a
    insist(verified_witnesses == result["sharpWitnesses"], "sharp passage witnesses")
    admission_cursor = 0
    latest = None
    for i, f in enumerate(frames):
        insist(f["tick"] == i, "frame tick")
        check_pose(position,yaw,f)
        v,r = requests[i]
        insist(0. <= v <= result["speed"] and abs(r) <= result["rate"], "request bound")
        applied = requests[i-delay] if i>=delay else list(ZERO)
        insist(f["applied"] == applied, "actual command FIFO")
        while admission_cursor < len(admitted) and admitted[admission_cursor]["deliveryTick"] <= i:
            latest = admitted[admission_cursor]["captureTick"]
            admission_cursor += 1
        ref = f["controlPose"]
        if latest is None:
            insist(ref is None and requests[i] == list(ZERO), "motion before observation")
        else:
            insist(ref is not None and ref["sourceTick"] == latest and (i-latest)*DT <= MAX_POSE_AGE,
                   "reference source age")
            px, pyaw = truth[latest]["xyz"], truth[latest]["yaw"]
            if mode != "held-pose":
                for j in range(latest,i+delay):
                    cmd = requests[j-delay] if j>=delay else ZERO
                    px,pyaw = integrate(px,pyaw,cmd)
            check_pose(px,pyaw,ref)
        position,yaw = integrate(position,yaw,applied)
    check_pose(position,yaw,stop)
    for j,row in enumerate(drain):
        index = len(frames)+j-delay
        cmd = requests[index] if 0 <= index < len(frames) else list(ZERO)
        insist(row["applied"] == cmd, "terminal FIFO drain")
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
               _xz_distance(truth[previous["captureTick"]]["xyz"],trace.points[-1].xyz) <= tol,
               "observed arrival lacks source witness")
    elapsed = (len(frames)+len(drain))*DT
    moving = DT*sum(row["applied"][0] > 0. for row in [*frames,*drain])
    insist(same(summary["totalElapsedSeconds"],elapsed) and
           same(summary["totalForwardDutyRatio"],moving/elapsed) and
           same(summary["approachSeconds"],len(frames)*DT) and
           same(summary["drainSeconds"],len(drain)*DT), "time/duty accounting")
    insist(summary["sharpCornersPassed"] == cursor and summary["observedArrival"] is arrived,
           "arrival/witness accounting")
    insist(summary["finalModelSettled"] == (arrived and error<=trace.arrival_tolerance_xz),
           "false settled arrival")
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
