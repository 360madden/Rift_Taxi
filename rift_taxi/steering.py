"""Pure Pursuit geometry preview for synthetic routes only.

This is not a live movement controller. Actual A/D direction, yaw source,
actuator rate, obstacle clearance and STOP behavior remain M1/M3 work.
"""

from __future__ import annotations

import math
from typing import Any

from .contracts import MovementTrace, Point, TraceError


def _xz_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.hypot(a[0] - b[0], a[2] - b[2])


def _segments(points: tuple[Point, ...]) -> tuple[list[float], float]:
    accum = [0.0]
    for a, b in zip(points, points[1:]):
        accum.append(accum[-1] + _xz_distance(a.xyz, b.xyz))
    if accum[-1] <= 0:
        raise TraceError("preview route has no horizontal extent")
    return accum, accum[-1]


def _closest_progress(
    points: tuple[Point, ...], cumulative: list[float],
    position: tuple[float, float, float], previous_progress: float,
) -> tuple[float, float]:
    """Return projected path progress and lateral deviation; no route admission."""
    candidates: list[tuple[float, float]] = []
    for i, (start, end) in enumerate(zip(points, points[1:])):
        seg = cumulative[i + 1] - cumulative[i]
        if seg <= 1e-12:
            continue
        vx, vz = end.xyz[0] - start.xyz[0], end.xyz[2] - start.xyz[2]
        along = ((position[0] - start.xyz[0]) * vx + (position[2] - start.xyz[2]) * vz) / (seg * seg)
        along = max(0.0, min(1.0, along))
        cx, cz = start.xyz[0] + along * vx, start.xyz[2] + along * vz
        progress = cumulative[i] + along * seg
        error = math.hypot(position[0] - cx, position[2] - cz)
        candidates.append((error, progress))
    candidates.sort(key=lambda candidate: (candidate[0], -candidate[1]))
    closest_error, closest_progress = candidates[0]
    return max(previous_progress, closest_progress), closest_error


def _lookahead_point(
    points: tuple[Point, ...], cumulative: list[float], along: float,
) -> tuple[float, float, float]:
    if along >= cumulative[-1]:
        return points[-1].xyz
    for i in range(len(points) - 1):
        if along > cumulative[i + 1]:
            continue
        distance = cumulative[i + 1] - cumulative[i]
        if distance <= 1e-12:
            continue
        portion = (along - cumulative[i]) / distance
        a, b = points[i].xyz, points[i + 1].xyz
        return tuple(start + portion * (finish - start)
                     for start, finish in zip(a, b))  # type: ignore[return-value]
    return points[-1].xyz


def _angle_delta(desired: float, current: float) -> float:
    """Synthetic convention: yaw 0 along +X, positive toward +Z."""
    return (desired - current + 180.0) % 360.0 - 180.0


def preview_steering(trace: MovementTrace, *, lookahead: float = 2.0,
                     deadband_degrees: float = 4.0) -> dict[str, Any]:
    """Produce heading/turn intents only; never synthesize key-down events.

    A/D direction in RIFT is not inferred from synthetic yaw; real actuator
    mapping must be physically calibrated and independently verified.
    """
    if (trace.source_type != "synthetic"
            or trace.frame["frameId"] != "synthetic-local-xyz"):
        raise TraceError("steering preview accepts only synthetic-local-xyz traces")
    if any(p.kind in {"mandatory_passage", "hard_stop"} for p in trace.points):
        raise TraceError("mandatory passages and hard stops need a later constraint controller")
    if any(p.actor_yaw_deg is None for p in trace.poses):
        raise TraceError("steering preview requires explicitly supplied synthetic actor yaw")
    if (not math.isfinite(lookahead) or lookahead <= 0 or lookahead > 50
            or not math.isfinite(deadband_degrees) or not 0 <= deadband_degrees < 90):
        raise TraceError("invalid lookahead/deadband for synthetic steering preview")
    cumulative, total_length = _segments(trace.points)
    progress = 0.0
    frames = []
    for pose in trace.poses:
        progress, cross_track = _closest_progress(trace.points, cumulative, pose.xyz, progress)
        goal = trace.points[-1].xyz
        distance_to_goal = _xz_distance(pose.xyz, goal)
        reached = distance_to_goal <= trace.arrival_tolerance_xz and progress >= total_length - trace.arrival_tolerance_xz
        if reached:
            frames.append({
                "t": pose.t, "progress": progress, "crossTrackErrorXZ": cross_track,
                "forwardIntent": False, "turnIntent": "none", "lookaheadXYZ": list(goal),
                "headingErrorDegrees": 0.0, "curvature": 0.0,
                "arrivalCondition": "synthetic-position-only",
            })
            continue
        target = _lookahead_point(trace.points, cumulative, min(total_length, progress + lookahead))
        dx, dz = target[0] - pose.xyz[0], target[2] - pose.xyz[2]
        if math.hypot(dx, dz) < 1e-9:
            # Position target coincides with pose (rejoin or last segment).
            # Do not invent a turn without a usable tracking vector.
            raise TraceError("lookahead target cannot determine desired heading")
        desired = math.degrees(math.atan2(dz, dx))
        error = _angle_delta(desired, pose.actor_yaw_deg)
        chord = math.hypot(dx, dz)
        curvature = 2.0 * math.sin(math.radians(error)) / chord
        direction = ("none" if abs(error) <= deadband_degrees else
                     "positive-yaw" if error > 0 else "negative-yaw")
        frames.append({
            "t": pose.t, "progress": progress, "crossTrackErrorXZ": cross_track,
            "forwardIntent": True, "turnIntent": direction,
            "lookaheadXYZ": list(target), "headingErrorDegrees": error,
            "curvature": curvature, "arrivalCondition": "not-arrived",
        })
    return {
        "schema": "taxi.steering-preview/1",
        "classification": "SYNTHETIC_GEOMETRY_ONLY",
        "algorithm": "pure-pursuit-lookahead-heading",
        "routeId": trace.route_id,
        "lookahead": lookahead,
        "deadbandDegrees": deadband_degrees,
        "frames": frames,
        "gameInputSent": False,
        "liveNavigabilityVerified": False,
        "notes": [
            "No closed-loop simulation or physical RIFT actuator has been tested.",
            "Yaw convention and positive/negative turn intents are synthetic, not RIFT key bindings.",
            "No obstacle/corridor clearance or final game arrival is certified.",
        ],
    }
