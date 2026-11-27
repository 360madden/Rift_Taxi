"""Offline telemetry delivery and control-gate replay on synthetic trajectories.

The original ideal model supplies a time-indexed truth trajectory. Delivery
schedules independently delay, drop, or reorder immutable captured samples.
An inert backend exercises the existing driver-neutral HeldInputController;
it never sends keys, opens a game process, or modifies the truth trajectory.
This is an admission/expiry experiment, not closed-loop steering under jitter.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path

from .contracts import TraceError
from .control import ControlRefused, HeldInputController, LivePose, SessionBinding
from .simulation import simulate_route
from .simulation_holdout import _case_trace
from .simulation_integrity import verify_synthetic_trajectory

# Binary-exact model tick keeps fake-clock boundary comparisons repeatable.
DT = .0625
MAX_POSE_AGE = .35
MAX_HOLD = .50
# Fixed window, independent of the route's eventual arrival outcome.
TICKS = 64
PROFILES = ("immediate", "steady-delay", "jitter-in-order",
            "short-dropout", "long-dropout", "out-of-order", "stale-stream")
ROUTES = (
    ("long-s", ((0,0,0),(6,0,0),(10,0,4),(17,0,4),(22,0,7))),
    ("wide-dogleg", ((0,0,0),(5,0,3),(9,0,8),(15,0,7),(22,0,11))),
)
# Deliberately fake binding and backend. The true verification flags below
# describe test fixtures only, never a physical or qualified RIFT session.
SESSION = SessionBinding("SYNTHETIC-FIXTURE", 1, 1, "0"*64, 1,
                         "fake-actor", "fake-zone")


class ReplayClock:
    """Read-only from the controller's perspective; replay owns time."""
    def __init__(self):
        self.now = 0.
    def __call__(self):
        return self.now


class InertBackend:
    """Accept edge requests in memory only; no platform calls or injection."""
    def write_key(self, key, is_down):
        return True


def delivery_tick(capture, profile):
    """Map a nonnegative capture index to a delivery index or None (drop)."""
    if type(capture) is not int or not 0 <= capture < TICKS:
        raise TraceError("capture tick outside replay window")
    if profile == "immediate":
        delay = 0
    elif profile == "steady-delay":
        delay = 2
    elif profile == "jitter-in-order":
        delay = (1, 2, 1, 2)[capture % 4]
    elif profile == "short-dropout":
        if 20 <= capture <= 22:
            return None
        delay = 0
    elif profile == "long-dropout":
        if 20 <= capture <= 28:
            return None
        delay = 0
    elif profile == "out-of-order":
        delay = 3 if capture == 20 else 0
    elif profile == "stale-stream":
        delay = 6
    else:
        raise TraceError("unknown synthetic delivery profile")
    return capture + delay


def truth_frames(name, points, *, speed):
    """Generate a verified, fixed-duration prefix of an ideal synthetic route."""
    spec = {"routeId": name, "routeXYZ": [list(p) for p in points],
            "initialXYZ": [0., 0., .15], "initialYawDegrees": 5.}
    trace = _case_trace(spec, generator="taxi-observation-replay-20261126-v1")
    result = simulate_route(trace, dt=DT, speed=speed, max_yaw_rate=100.,
                            max_seconds=40., speed_policy="turn-limited-ordered")
    verify_synthetic_trajectory(result, trace)
    # Never manufacture samples after a terminated model. The fixture must
    # provide the entire requested observation window as actual frames.
    frames = result["frames"][:TICKS]
    if len(frames) != TICKS or any(f["t"] != i*DT for i, f in enumerate(frames)):
        raise TraceError("truth trajectory too short or not on replay grid")
    return trace.trace_sha256, frames


def replay(frames, profile):
    """Apply scheduled packets to the actual control gate using fake time.

    At every tick expiry is checked *before* packet delivery. Packets arriving
    together are processed in source order; packets arriving late across ticks
    retain their original sequence and capture timestamp. Even after STOP we
    deliver remaining packets to prove that the gate never automatically rearms.
    Source-to-truth errors measure transport staleness, not steering response.
    """
    if len(frames) != TICKS or any(f["t"] != i*DT for i, f in enumerate(frames)):
        raise TraceError("invalid observation replay frame grid")
    arrivals = {}
    dropped = 0
    pending_at_end = 0
    for capture in range(TICKS):
        arrival = delivery_tick(capture, profile)
        if arrival is None:
            dropped += 1
        elif arrival >= TICKS:
            pending_at_end += 1
        else:
            arrivals.setdefault(arrival, []).append(capture)

    clock = ReplayClock()
    packets = []
    states = []
    latest_delivered_capture = None
    last_accepted_capture = None
    with HeldInputController(SESSION, InertBackend(), clock=clock,
                             max_pose_age_s=MAX_POSE_AGE, max_hold_s=MAX_HOLD) as gate:
        for tick, actual in enumerate(frames):
            clock.now = tick * DT
            # Delivery age alone hides packet-loss gaps: a fresh packet may
            # follow a long interval with no observation. Record the age of
            # the last delivery before new packets and expiry are processed.
            pre_delivery_age = (None if latest_delivered_capture is None else
                                clock.now-frames[latest_delivered_capture]["t"])
            gate.check_expiry()
            for capture in arrivals.get(tick, []):
                latest_delivered_capture = capture
                source = frames[capture]
                pose = LivePose(SESSION, capture+1, source["t"],
                                tuple(source["xyz"]), source["yawDegrees"], True, True)
                before = gate.status
                try:
                    # Constant fictional demand isolates the gate from steering.
                    # A/D direction is not inferred from the synthetic trajectory.
                    gate.apply(("W", "A"), pose)
                    accepted = True
                    last_accepted_capture = capture
                except ControlRefused:
                    accepted = False
                after = gate.status
                packets.append({
                    "captureTick": capture, "deliveryTick": tick,
                    "sequence": capture+1, "sourceSeconds": source["t"],
                    "deliverySeconds": clock.now, "ageSeconds": clock.now-source["t"],
                    "positionErrorXZ": math.hypot(
                        source["xyz"][0]-actual["xyz"][0],
                        source["xyz"][2]-actual["xyz"][2]),
                    "yawErrorDegrees": abs((source["yawDegrees"]-
                                            actual["yawDegrees"]+180.) % 360.-180.),
                    "accepted": accepted, "stopAlreadyLatched": before.stop_latched,
                    "stopReason": after.stop_reason,
                })
            status = gate.status
            held_age = held_position_error = held_yaw_error = None
            if status.potentially_held_keys and last_accepted_capture is not None:
                accepted_source = frames[last_accepted_capture]
                held_age = clock.now-accepted_source["t"]
                held_position_error = math.hypot(
                    accepted_source["xyz"][0]-actual["xyz"][0],
                    accepted_source["xyz"][2]-actual["xyz"][2])
                held_yaw_error = abs((accepted_source["yawDegrees"]-
                                      actual["yawDegrees"]+180.) % 360.-180.)
            states.append({"tick": tick, "seconds": clock.now,
                           "preDeliveryObservationAgeSeconds": pre_delivery_age,
                           "heldPoseAgeSeconds": held_age,
                           "heldPosePositionErrorXZ": held_position_error,
                           "heldPoseYawErrorDegrees": held_yaw_error,
                           "stopLatched": status.stop_latched,
                           "stopReason": status.stop_reason,
                           "heldKeys": list(status.potentially_held_keys)})
        final = gate.status
        # Exclude context-manager cleanup so a normal completed stream isn't
        # mistaken for a fault stop. The context still releases its inert keys.
        edges = [asdict(edge) for edge in gate.events]

    first_stop = next((s for s in states if s["stopLatched"]), None)
    stopped = first_stop is not None
    # Verify the observed invariants before emitting the study. Any down edge
    # at/after fault STOP would contradict this no-rearm fixture contract.
    if stopped and (final.potentially_held_keys or any(
            e["is_down"] and e["at_monotonic_s"] >= first_stop["seconds"]
            for e in edges)):
        raise TraceError("inert gate failed latched STOP invariant")
    def observed_max(field):
        # Missing observations are null, not a fictional zero-error sample.
        return max((s[field] for s in states if s[field] is not None), default=None)
    return {
        "profile": profile, "captured": TICKS,
        "maxPreDeliveryObservationAgeSeconds": observed_max("preDeliveryObservationAgeSeconds"),
        "maxHeldPoseAgeSeconds": observed_max("heldPoseAgeSeconds"),
        "maxHeldPosePositionErrorXZ": observed_max("heldPosePositionErrorXZ"),
        "maxHeldPoseYawErrorDegrees": observed_max("heldPoseYawErrorDegrees"),
        "delivered": len(packets), "dropped": dropped,
        "pendingBeyondWindow": pending_at_end,
        "acceptedPackets": sum(p["accepted"] for p in packets),
        "refusedAfterStop": sum(p["stopAlreadyLatched"] and not p["accepted"] for p in packets),
        "maxDeliveryAgeSeconds": max((p["ageSeconds"] for p in packets), default=None),
        "maxDeliveryPositionErrorXZ": max((p["positionErrorXZ"] for p in packets), default=None),
        "maxDeliveryYawErrorDegrees": max((p["yawErrorDegrees"] for p in packets), default=None),
        "faultStop": stopped, "firstStop": first_stop,
        "finalHeldKeys": list(final.potentially_held_keys),
        "edges": edges, "packets": packets, "tickStates": states,
        "gameInputSent": False, "physicalQualification": False,
    }


def evaluate():
    """Compare seven fixed transport patterns on four verified truth prefixes."""
    rows = []
    for name, points in ROUTES:
        for speed in (2.5, 3.5):
            digest, frames = truth_frames(name, points, speed=speed)
            # Bind the actual truth prefix as well as the route specification;
            # model parameters such as speed alter this digest.
            truth_digest = hashlib.sha256(json.dumps(
                frames, sort_keys=True, separators=(",", ":"),
                allow_nan=False).encode("utf-8")).hexdigest()
            for profile in PROFILES:
                rows.append({"route": name, "speed": speed,
                             "scenarioSHA256": digest, "truthPrefixSHA256": truth_digest,
                             **replay(frames, profile)})
    summary = []
    for profile in PROFILES:
        group = [r for r in rows if r["profile"] == profile]
        def max_available(field):
            return max((r[field] for r in group if r[field] is not None), default=None)
        summary.append({
            "profile": profile, "cases": len(group),
            "maxPreDeliveryObservationAgeSeconds": max_available("maxPreDeliveryObservationAgeSeconds"),
            "maxHeldPoseAgeSeconds": max_available("maxHeldPoseAgeSeconds"),
            "maxHeldPosePositionErrorXZ": max_available("maxHeldPosePositionErrorXZ"),
            "maxHeldPoseYawErrorDegrees": max_available("maxHeldPoseYawErrorDegrees"),
            "faultStops": sum(r["faultStop"] for r in group),
            "stopReasons": dict(sorted(Counter(
                r["firstStop"]["stopReason"] for r in group if r["faultStop"]).items())),
            "maxDeliveryAgeSeconds": max(r["maxDeliveryAgeSeconds"] for r in group),
            "maxDeliveryPositionErrorXZ": max(r["maxDeliveryPositionErrorXZ"] for r in group),
            "maxDeliveryYawErrorDegrees": max(r["maxDeliveryYawErrorDegrees"] for r in group),
            "refusedAfterStop": sum(r["refusedAfterStop"] for r in group),
        })
    return {"schema": "taxi.synthetic-observation-replay/2",
            "classification": "SYNTHETIC_INERT_GATE_ONLY",
            "tickSeconds": DT, "ticksPerCase": TICKS,
            "poseAgeLimitSeconds": MAX_POSE_AGE, "holdLimitSeconds": MAX_HOLD,
            "caseCount": len(rows), "summary": summary, "rows": rows,
            "gameInputSent": False, "physicalQualification": False,
            "limitations": [
                "Truth trajectory remains unchanged after gate STOP; replay is not a closed-loop response.",
                "Deterministic sampled expiry checks and inert accepted edges; no wall-clock watchdog or physical release proof.",
                "Synthetic capture time is known exactly; real native source freshness is still unqualified.",
            ]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--out", type=Path, help="new JSON report, never overwrite")
    args = parser.parse_args(argv)
    try:
        if args.out is not None and args.out.exists():
            raise FileExistsError(args.out)
        report = evaluate()
        if args.out is not None:
            with args.out.open("x", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
        if args.summary or args.out is None:
            view = {k: v for k, v in report.items() if k != "rows"} if args.summary else report
            print(json.dumps(view, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (TraceError, OSError, ValueError) as exc:
        parser.exit(2, f"Synthetic observation replay refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
