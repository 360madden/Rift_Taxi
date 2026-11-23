"""Source-aware movement timing diagnostics from an already verified offline trace.

The event stream records command/key insertion claims, not independently
verified key state or RIFT consumption. Observed pose changes, input lags and
after-release displacement are temporal *proxies*, not causal or live proofs.
No current game process, AI service, sibling executable, or native input is used.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
import math
from statistics import median
from typing import Any

from .contracts import MovementTrace, TraceError


def _distance_xz(a: tuple[float, float, float],
                 b: tuple[float, float, float]) -> float:
    return math.hypot(a[0] - b[0], a[2] - b[2])


def _distribution(speeds: list[float]) -> dict[str, int | float | None]:
    if not speeds:
        return {"intervalCount": 0, "medianSourceUnitsPerSecond": None,
                "p90SourceUnitsPerSecond": None, "maxSourceUnitsPerSecond": None}
    sorted_speeds = sorted(speeds)
    p90_index = min(len(sorted_speeds) - 1,
                    math.ceil(len(sorted_speeds) * .90) - 1)
    return {
        "intervalCount": len(speeds),
        "medianSourceUnitsPerSecond": median(sorted_speeds),
        "p90SourceUnitsPerSecond": sorted_speeds[p90_index],
        "maxSourceUnitsPerSecond": sorted_speeds[-1],
    }


def analyze_motion_timing(
    trace: MovementTrace, *, movement_threshold_xz: float = .02,
    max_interval_s: float = .25, response_horizon_s: float = 1.0,
    coast_window_s: float = .5,
) -> dict[str, Any]:
    """Compare offline pose segments with supplied key edges.

    Only full pose intervals inside the movement window with zero key edges
    are admitted to held/idle rate buckets. Edges landing on interval end
    are conservatively treated as transitions, never assumed synchronized.
    """
    if not isinstance(trace, MovementTrace):
        raise TraceError("verified MovementTrace required")
    for name, value, lower, upper in (
        ("movement_threshold_xz", movement_threshold_xz, .0001, 1.),
        ("max_interval_s", max_interval_s, .02, 2.),
        ("response_horizon_s", response_horizon_s, .05, 5.),
        ("coast_window_s", coast_window_s, .05, 3.),
    ):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not lower <= value <= upper):
            raise TraceError(f"{name} outside supported finite range")

    poses = trace.poses
    events = trace.events
    sample_times = [p.t for p in poses]
    window_start, window_end = trace.window_start, trace.window_end
    held: set[str] = set()
    cursor = 0
    forward: list[float] = []
    idle: list[float] = []
    turning: list[float] = []
    boundary_count = 0
    oversized_gaps = 0
    accepted_time = 0.0
    unchanged_time = 0.0
    changed_intervals = 0
    max_gap = 0.0
    yaw_rates: list[float] = []

    for a, b in zip(poses, poses[1:]):
        if a.t < window_start or b.t > window_end:
            continue
        dt = b.t - a.t
        max_gap = max(max_gap, dt)
        while cursor < len(events) and events[cursor].t <= a.t:
            e = events[cursor]
            if e.edge == "down":
                held.add(e.key)
            else:
                held.discard(e.key)
            cursor += 1
        # Conservative: an edge coinciding with b.t makes this interval
        # transitional, since the event/pose order is not established.
        crossing = cursor < len(events) and events[cursor].t <= b.t
        if crossing:
            boundary_count += 1
            continue
        if dt > max_interval_s:
            oversized_gaps += 1
            continue
        distance = _distance_xz(a.xyz, b.xyz)
        if not math.isfinite(distance):
            raise TraceError("observed XZ displacement overflow")
        speed = distance / dt
        if not math.isfinite(speed):
            raise TraceError("observed interval speed overflow")
        accepted_time += dt
        if distance < movement_threshold_xz:
            unchanged_time += dt
        else:
            changed_intervals += 1
        if "W" in held:
            forward.append(speed)
        else:
            idle.append(speed)
        if "W" in held and ("A" in held or "D" in held):
            turning.append(speed)
        if a.actor_yaw_deg is not None and b.actor_yaw_deg is not None:
            delta = ((b.actor_yaw_deg - a.actor_yaw_deg + 180.) % 360.) - 180.
            rate = delta / dt
            if not math.isfinite(rate):
                raise TraceError("observed actor yaw rate overflow")
            yaw_rates.append(rate)

    # First XZ change seen after each W-down relative to latest sampled base.
    # This is not a causal latency proof, especially with unsynchronized UTC.
    response_windows: list[dict[str, Any]] = []
    for event_index, event in enumerate(events):
        if event.key != "W" or event.edge != "down" \
                or not window_start <= event.t <= window_end:
            continue
        next_input_edge = (events[event_index + 1].t
                           if event_index + 1 < len(events) else None)
        base_idx = max(0, bisect_right(sample_times, event.t) - 1)
        base_pose = poses[base_idx]
        first = None
        limit = min(window_end, event.t + response_horizon_s)
        censored = next_input_edge is not None and next_input_edge <= limit
        if censored:
            limit = next_input_edge
        final_index = (bisect_left(sample_times, limit) if censored
                       else bisect_right(sample_times, limit))
        # Never scan or copy unbounded timelines for one input edge.
        stop_index = min(final_index, base_idx + 1 + 512)
        for index in range(base_idx + 1, stop_index):
            sample = poses[index]
            if sample.t > event.t and (
                    _distance_xz(base_pose.xyz, sample.xyz) >= movement_threshold_xz):
                first = sample
                break
        response_windows.append({
            "keyDownAtSourceSeconds": event.t,
            "sampledBaseAtSeconds": base_pose.t,
            "firstChangedPoseAtSeconds": None if first is None else first.t,
            "firstChangedPoseDelayUpperBoundSeconds": (
                None if first is None else first.t - event.t
            ),
            "firstChangedPoseRequiresCausalVerification": True,
            "responseSearchSampleLimitReached": (first is None and stop_index < final_index),
            "censoredAtNextInputEdge": censored,
            "gameInputConsumptionVerified": False,
        })

    release_proxies: list[dict[str, Any]] = []
    for event_index, event in enumerate(events):
        if event.key != "W" or event.edge != "up" \
                or not window_start <= event.t <= window_end:
            continue
        next_input_edge = (events[event_index + 1].t
                           if event_index + 1 < len(events) else None)
        idx = max(0, bisect_right(sample_times, event.t) - 1)
        base = poses[idx]
        limit = min(window_end, event.t + coast_window_s)
        censored = next_input_edge is not None and next_input_edge <= limit
        if censored:
            limit = next_input_edge
        final_index = ((bisect_left(sample_times, limit) if censored
                        else bisect_right(sample_times, limit)) - 1)
        end_pose = (poses[final_index] if final_index > idx
                    and poses[final_index].t > event.t else None)
        distance = None if end_pose is None else _distance_xz(base.xyz, end_pose.xyz)
        release_proxies.append({
            "keyUpAtSourceSeconds": event.t,
            "lastBaseSampleAtSeconds": base.t,
            "lastPostReleaseSampleAtSeconds": (
                None if end_pose is None else end_pose.t
            ),
            "postReleaseDisplacementProxyXZ": distance,
            "censoredAtNextInputEdge": censored,
            "gameKeyReleasedVerified": False,
            "physicalCoastingVerified": False,
        })

    return {
        "schema": "taxi.motion-timing-evidence/1",
        "classification": "OFFLINE_TEMPORAL_ASSOCIATION_ONLY",
        "source": {
            "traceSha256": trace.trace_sha256,
            "sourceType": trace.source_type,
            "sourceRepository": (
                trace.source.get("repository") if trace.source_type == "historical"
                else None
            ),
            "originalSourceSha256": trace.verified_source_sha256,
            "clock": (
                trace.source.get("timeBasis") if trace.source_type == "historical"
                else "synthetic-seconds"
            ),
            "historicalAuthenticityEstablished": False,
        },
        "sampling": {
            "poseCount": len(poses),
            "inputEdgeCount": len(events),
            "maxPoseGapInWindowSeconds": max_gap,
            "acceptedStableIntervals": len(forward) + len(idle),
            "acceptedStableSeconds": accepted_time,
            "unchangedStableSecondsUnderThreshold": unchanged_time,
            "changedStableIntervalsAboveThreshold": changed_intervals,
            "excludedInputTransitionIntervals": boundary_count,
            "excludedExcessiveGapIntervals": oversized_gaps,
            "maxIntervalSeconds": max_interval_s,
            "movementThresholdSourceUnitsXZ": movement_threshold_xz,
        },
        "observedIntervalSpeed": {
            "forwardKeyHeldIntervals": _distribution(forward),
            "forwardKeyNotHeldIntervals": _distribution(idle),
            "turnAndForwardHeldIntervals": _distribution(turning),
            "units": "declared source-world-unit/s",
            "verifiedCharacterSpeed": False,
        },
        "yawRate": {
            "rateSampleCount": len(yaw_rates),
            "medianDegreesPerSecondCandidate": (
                median(yaw_rates) if yaw_rates else None
            ),
            "bodyHeadingQualified": False,
        },
        "firstChangedPoseAfterWDown": response_windows,
        "postWUpDisplacementProxies": release_proxies,
        "qualifications": {
            "keySendEventsObservedInGame": False,
            "movementCausedByWVerified": False,
            "coastingAfterReleaseVerified": False,
            "turnDirectionCalibrated": False,
            "suitableForLiveSteeringCalibration": False,
        },
        "limitations": [
            "Sampled source XYZ and command edges can share a clock but lack causal proof.",
            "Input transitions and too-large sampling gaps are excluded from speed buckets.",
            "W-down response windows end at the next input edge, but prior/latent controls may still affect pose.",
            "First-change search is bounded to 512 pose samples per W-down and reports truncation.",
            "W-up displacement ends at the next input edge and may include motion started before release.",
            "Historical same-host UTC can jump; sample interval rates remain candidates.",
            "Do not use unqualified candidate yaw to calibrate RIFT A/D turn response.",
            "This offline report never proves a current Taxi journey or game arrival.",
        ],
    }
