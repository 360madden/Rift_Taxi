"""Deterministic, read-only replay quality measurements for submitted traces."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .contracts import MovementTrace, PoseSample


@dataclass(frozen=True)
class Span:
    start: float
    end: float


def _clip(span: Span, start: float, end: float) -> float:
    return max(0.0, min(span.end, end) - max(span.start, start))


def _turn_overlap(forward: list[Span], turns: list[Span],
                  start: float, end: float) -> tuple[float, int]:
    """Linear sweep of ordered, disjoint spans; count each overlapping turn once."""
    seconds = 0.0
    intervals = 0
    w_index = 0
    for turn in turns:
        left, right = max(turn.start, start), min(turn.end, end)
        if right <= left:
            continue
        while w_index < len(forward) and forward[w_index].end <= left:
            w_index += 1
        cursor = w_index
        amount = 0.0
        while cursor < len(forward) and forward[cursor].start < right:
            w = forward[cursor]
            amount += max(0.0, min(right, w.end) - max(left, w.start))
            if w.end > right:
                break
            cursor += 1
        w_index = cursor
        if amount > 0:
            seconds += amount
            intervals += 1
    return seconds, intervals


def _spans(trace: MovementTrace) -> tuple[dict[str, list[Span]], set[str]]:
    starts: dict[str, float] = {}
    spans: dict[str, list[Span]] = {}
    for event in trace.events:
        if event.edge == "down":
            starts[event.key] = event.t
        else:
            start = starts.pop(event.key)
            spans.setdefault(event.key, []).append(Span(start, event.t))
    still_held = set(starts)
    # Count an unreleased hold up to last sampled time for analysis ONLY.
    # It is not release evidence.
    for key, start in starts.items():
        spans.setdefault(key, []).append(Span(start, trace.poses[-1].t))
    return spans, still_held


def _interpolated_xyz(poses: tuple[PoseSample, ...], t: float) -> tuple[float, float, float]:
    """Linear estimate for guide-release proximity. Not a measured position at t."""
    lo, hi = 0, len(poses) - 1
    if t <= poses[0].t:
        return poses[0].xyz
    if t >= poses[-1].t:
        return poses[-1].xyz
    while lo + 1 < hi:
        middle = (lo + hi) // 2
        if poses[middle].t <= t:
            lo = middle
        else:
            hi = middle
    a, b = poses[lo], poses[hi]
    part = (t - a.t) / (b.t - a.t)
    return tuple(x + (y - x) * part for x, y in zip(a.xyz, b.xyz))  # type: ignore[return-value]


def _distance_xz(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.hypot(a[0] - b[0], a[2] - b[2])


def analyze(trace: MovementTrace) -> dict[str, Any]:
    """Describe the supplied trace. Never certify game movement or live arrival."""
    spans, still_held = _spans(trace)
    start, end = trace.window_start, trace.window_end
    window_duration = end - start
    forward_seconds = sum(_clip(s, start, end) for s in spans.get("W", []))
    turning_seconds = 0.0
    overlap_intervals = 0
    for turn_key in ("A", "D"):
        amount, count = _turn_overlap(spans.get("W", []),
                                      spans.get(turn_key, []), start, end)
        turning_seconds += amount
        overlap_intervals += count

    releases = [e for e in trace.events
                if e.key == "W" and e.edge == "up" and start < e.t < end]
    guide_release_proxies = 0
    for release in releases:
        approx = _interpolated_xyz(trace.poses, release.t)
        if any(
            p.kind in {"guide", "optional"}
            and _distance_xz(approx, p.xyz) <= trace.arrival_tolerance_xz
            for p in trace.points[1:-1]
        ):
            guide_release_proxies += 1
    hard_stop_release_proxies = 0
    for point in trace.points:
        if point.kind != "hard_stop":
            continue
        if any(_distance_xz(_interpolated_xyz(trace.poses, e.t), point.xyz)
               <= trace.arrival_tolerance_xz for e in trace.events
               if e.key == "W" and e.edge == "up"):
            hard_stop_release_proxies += 1

    # Include a turn already held when the eligible window starts, but not
    # pre-window or post-window turn intervals with zero eligible duration.
    directions = [key for _, key in sorted(
        (span.start, key) for key in ("A", "D")
        for span in spans.get(key, []) if _clip(span, start, end) > 0
    )]
    direction_alternations = sum(a != b for a, b in zip(directions, directions[1:]))
    poses = trace.poses
    xz_distance = sum(_distance_xz(a.xyz, b.xyz) for a, b in zip(poses, poses[1:]))
    largest_gap = max(b.t - a.t for a, b in zip(poses, poses[1:]))
    end_point = trace.points[-1].xyz
    horizontal_error = _distance_xz(poses[-1].xyz, end_point)

    return {
        "schema": "taxi.replay-metrics/1",
        "trace": {
            "sha256": trace.trace_sha256,
            "sourceType": trace.source_type,
            "routeId": trace.route_id,
            "sourceIntegrity": ("submitted-source-sha256-match"
                                if trace.verified_source_sha256 else "synthetic-only"),
            "historicalAuthenticityEstablished": False,
            "clock": ("declared-" + trace.source["timeBasis"]
                      if trace.source_type == "historical" else "synthetic-seconds"),
        },
        "movement": {
            "eligibleSeconds": window_duration,
            "inputMetricScope": "declared-movement-window",
            "trajectoryMetricScope": "full-observed-pose-timeline",
            "forwardHeldSeconds": forward_seconds,
            "forwardDutyRatio": forward_seconds / window_duration,
            "intermediateForwardReleases": len(releases),
            "guideReleaseProxies": guide_release_proxies,
            "guideStopCountVerified": None,
            "turningWhileForwardSeconds": turning_seconds,
            "turningWhileForwardIntervals": overlap_intervals,
            "turnDirectionAlternations": direction_alternations,
            "observedPolylineDistanceXZ": xz_distance,
            "maxPoseSampleGapSeconds": largest_gap,
            "poseCount": len(poses),
            "actorYawAvailableSamples": sum(p.actor_yaw_deg is not None for p in poses),
        },
        "arrival": {
            "replayFinalXZError": horizontal_error,
            "replayFinalYError": abs(poses[-1].xyz[1] - end_point[1]),
            "withinDeclaredXZTolerance": horizontal_error <= trace.arrival_tolerance_xz,
            "inputKeysReleasedByTraceEnd": not still_held,
            "keysStillHeldAtTraceEnd": sorted(still_held),
            "hardStops": sum(p.kind == "hard_stop" for p in trace.points),
            "hardStopReleaseProxies": hard_stop_release_proxies,
            "liveArrivalVerified": False,
        },
        "classification": "OFFLINE_REPLAY_ONLY",
        "limitations": [
            "Input event timeline is supplied data, not independently observed OS/game key state.",
            "Duty, intermediate W releases, guide proxies and turn metrics use the declared eligible window; hard-stop proxies, trace-end release and trajectory metrics use the full trace.",
            "Guide release proximity is interpolated and is not proof of stationary game state.",
            "No source-world corridor/obstacle clearance is certified from a motion trace.",
            "Offline replay never proves a live RIFT journey or arrival.",
        ],
    }


def compare(left: MovementTrace, right: MovementTrace) -> dict[str, Any]:
    """Compare like-for-like submitted traces without claiming physical improvement."""
    if (left.route_id != right.route_id or left.points != right.points
            or left.frame != right.frame
            or left.arrival_tolerance_xz != right.arrival_tolerance_xz):
        raise ValueError("comparison requires identical route, frame and tolerance")
    a, b = analyze(left), analyze(right)
    am, bm = a["movement"], b["movement"]
    return {
        "schema": "taxi.replay-comparison/1",
        "classification": "OFFLINE_REPLAY_ONLY",
        "routeId": left.route_id,
        "left": a,
        "right": b,
        "rightMinusLeft": {
            "forwardDutyRatio": bm["forwardDutyRatio"] - am["forwardDutyRatio"],
            "intermediateForwardReleases": (
                bm["intermediateForwardReleases"] - am["intermediateForwardReleases"]
            ),
            "guideReleaseProxies": bm["guideReleaseProxies"] - am["guideReleaseProxies"],
            "turningWhileForwardSeconds": (
                bm["turningWhileForwardSeconds"] - am["turningWhileForwardSeconds"]
            ),
            "finalXZError": (
                b["arrival"]["replayFinalXZError"] - a["arrival"]["replayFinalXZError"]
            ),
        },
    }
