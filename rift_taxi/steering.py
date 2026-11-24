"""Pure Pursuit geometry preview for synthetic routes only.

This is not a live movement controller. Actual A/D direction, yaw source,
actuator rate, obstacle clearance and STOP behavior remain M1/M3 work.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
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


def _project(
    points: tuple[Point, ...], cumulative: list[float],
    position: tuple[float, float, float], low: float, high: float,
) -> tuple[float, float]:
    """Return (arc progress, XZ error) on a clipped synthetic route interval.

    Shared by preview and feedback simulation; cumulative distances must be
    nondecreasing and aligned to the route vertices. Bounds are distances in
    synthetic units, not time or indices. Both endpoints are inclusive.
    A later crossing cannot teleport progress ahead of the movement budget.
    Ties favor the earlier arc position. This is not obstacle/corridor proof.
    """
    candidates = []
    # The original full scan tested each segment's start/end arc against
    # low/high. Binary search those same sorted vertex arcs first, retaining
    # both segments touching an exact boundary (including zero-width windows).
    # This preserves the arithmetic and lexicographic tie break of the frozen
    # simulator while avoiding a full route scan at every observation.
    first = bisect_left(cumulative, low, lo=1) - 1
    stop = bisect_right(cumulative, high, hi=len(points) - 1)
    for i in range(first, stop):
        a, b = points[i], points[i + 1]
        length = cumulative[i+1] - cumulative[i]
        if length <= 1e-12 or cumulative[i+1] < low or cumulative[i] > high:
            continue
        # Clip this segment to the allowed arc-length interval before
        # projecting onto it. A globally nearest later leg would otherwise
        # permit a jump at a crossing or closely spaced parallel section.
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
    # Apply the same ordered, displacement-limited arc projection as the
    # offline feedback model. Starting at a crossing must not advance the
    # route, and a stationary sample cannot accumulate progress. The factor
    # of two is a synthetic allowance for cutting corners, not live motion
    # or collision evidence. Cross-track error uses the eligible arc, never
    # a different (possibly already passed or not yet reached) route leg.
    for xyz in (*(p.xyz for p in trace.points), *(p.xyz for p in trace.poses)):
        if len(xyz) != 3 or any(not math.isfinite(v) or abs(v) > 1e6 for v in xyz):
            raise TraceError("synthetic coordinates invalid or unbounded")
    cumulative, total_length = _segments(trace.points)
    if any(b-a <= 1e-9 for a,b in zip(cumulative, cumulative[1:])):
        raise TraceError("duplicate horizontal route points")
    if (not math.isfinite(trace.arrival_tolerance_xz)
            or not 0 < trace.arrival_tolerance_xz < total_length):
        raise TraceError("route length must exceed positive arrival tolerance")
    progress = 0.0
    previous_xyz = None
    frames = []
    for pose in trace.poses:
        budget = 0.0 if previous_xyz is None else 2.0 * _xz_distance(previous_xyz, pose.xyz)
        progress, cross_track = _project(
            trace.points, cumulative, pose.xyz, progress,
            min(total_length, progress + budget),
        )
        previous_xyz = pose.xyz
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
        "progressPolicy": "ordered-displacement-bounded/1",
        "routeId": trace.route_id,
        "lookahead": lookahead,
        "deadbandDegrees": deadband_degrees,
        "frames": frames,
        "gameInputSent": False,
        "liveNavigabilityVerified": False,
        "notes": [
            "This preview does not run the feedback simulator or a physical actuator.",
            "Progress starts at zero; each sample permits at most twice its observed XZ displacement.",
            "Yaw convention and positive/negative turn intents are synthetic, not RIFT key bindings.",
            "No obstacle/corridor clearance or final game arrival is certified.",
        ],
    }
