"""Deterministic offline sensitivity grid for the existing synthetic plant."""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from itertools import product
import math

from .contracts import MovementTrace, TraceError
from .simulation import simulate_route

_OFFSETS = (-.5, 0., .5)
_HEADINGS = (-90., -45., 0., 45., 90.)
_SPEEDS = (2., 3.)
_RATES = (60., 120., 180.)
_STEPS = (.05, .10)


def stress_route(trace: MovementTrace) -> dict:
    """Run a fixed 180-case grid; retain failures and all parameter overrides.

    The grid is not a probability distribution or physical calibration.
    """
    if (trace.source_type != "synthetic"
            or trace.frame.get("frameId") != "synthetic-local-xyz"
            or len(trace.points) < 2 or not trace.poses):
        raise TraceError("synthetic-local-xyz route and initial pose required")
    initial = trace.poses[0]
    if initial.actor_yaw_deg is None or not math.isfinite(initial.actor_yaw_deg):
        raise TraceError("initial synthetic actor yaw required")
    a, b = trace.points[0].xyz, trace.points[1].xyz
    dx, dz = b[0]-a[0], b[2]-a[2]
    length = math.hypot(dx, dz)
    if not math.isfinite(length) or length <= 1e-9:
        raise TraceError("first route segment must have finite horizontal extent")
    # Offset in the perpendicular direction of the first route segment.
    nx, nz = -dz/length, dx/length
    cases = []
    for offset, heading, speed, rate, dt in product(
            _OFFSETS, _HEADINGS, _SPEEDS, _RATES, _STEPS):
        pose = replace(initial,
            xyz=(initial.xyz[0]+offset*nx, initial.xyz[1], initial.xyz[2]+offset*nz),
            actor_yaw_deg=initial.actor_yaw_deg+heading)
        result = simulate_route(replace(trace, poses=(pose,), events=()),
                                speed=speed, max_yaw_rate=rate, dt=dt)
        metrics = result["metrics"]
        cases.append({
            "case": len(cases)+1, "offsetXZ": offset, "headingOffsetDegrees": heading,
            "initialXYZ": list(pose.xyz), "initialYawDegrees": pose.actor_yaw_deg,
            "speed": speed, "maxYawRate": rate, "dt": dt,
            "status": result["status"], "metrics": metrics,
            "meetsArrivalAndDutyTarget": (
                metrics["syntheticArrival"] and metrics["forwardDutyRatio"] >= .95
            ),
        })

    def summarize(rows):
        arrived = sum(r["metrics"]["syntheticArrival"] for r in rows)
        return {
            "cases": len(rows), "arrived": arrived,
            "arrivalAndDutyTarget": sum(r["meetsArrivalAndDutyTarget"] for r in rows),
            "statusCounts": dict(sorted(Counter(r["status"] for r in rows).items())),
            "worstFinalXZError": max(r["metrics"]["finalXZError"] for r in rows),
            "worstCrossTrackErrorXZ": max(r["metrics"]["maxCrossTrackErrorXZ"] for r in rows),
        }

    return {
        "schema": "taxi.synthetic-feedback-stress/1",
        "classification": "SYNTHETIC_CLOSED_LOOP_ONLY",
        "routeId": trace.route_id, "baseTraceSHA256": trace.trace_sha256,
        "baseInitialXYZ": list(initial.xyz), "baseInitialYawDegrees": initial.actor_yaw_deg,
        "grid": {"offsetXZ": list(_OFFSETS), "headingOffsetDegrees": list(_HEADINGS),
                 "speed": list(_SPEEDS), "maxYawRate": list(_RATES), "dt": list(_STEPS)},
        "fixedModel": {"lookahead": 1.5, "maxSeconds": 30., "maxCrossTrack": 2.,
                       "arrivalToleranceXZ": trace.arrival_tolerance_xz, "dutyTarget": .95},
        "summary": summarize(cases),
        "byYawRate": [{"maxYawRate": rate, **summarize(
            [r for r in cases if r["maxYawRate"] == rate])} for rate in _RATES],
        "byHeadingOffset": [{"headingOffsetDegrees": heading, **summarize(
            [r for r in cases if r["headingOffsetDegrees"] == heading])}
            for heading in _HEADINGS],
        "cases": cases,
        "gameInputSent": False, "liveArrivalVerified": False,
        "liveNavigabilityVerified": False,
        "limitations": [
            "Fixed deterministic sensitivity grid, not a representative probability distribution.",
            "All speeds, yaw rates and initial offsets are synthetic assumptions.",
            "Arrival plus duty is not proof of three distinct bends, clearance or physical RIFT acceptance.",
            "No actuator lag, collision, coasting or independently measured source freshness.",
        ],
    }
