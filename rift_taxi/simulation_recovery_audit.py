"""Offline phase timing for the published synthetic recovery variant.

Entry point: audit_recovery_efficiency(), exposed via the offline CLI.
Reuses the v1 holdout scenario definitions and the existing synthetic plant.
No OS/game access, real movement, input mapping, or file writes occur here.
The additional near-zero-speed metric is diagnostic only; never redefine
the historical forward-duty denominator or hide a stop to meet a target.
"""
from __future__ import annotations

import math
from statistics import mean

from .contracts import TraceError
from .simulation import simulate_route
from .simulation_holdout import _case_trace, evaluate_holdout

_SPEC_KEYS = ("routeId", "routeXYZ", "initialXYZ", "initialYawDegrees",
              "lateralOffset", "headingOffsetDegrees", "speed", "maxYawRate", "dt")
_PHASES = ("startup-alignment", "lookahead", "local-projection-rejoin")
# Absolute synthetic units/s. A tiny positive velocity is still positive for
# the old duty metric, but may not represent useful progress. Keep separately.
_NEAR_ZERO_SPEED = .05


def measure_recovery_phases(report: dict) -> dict:
    """Partition actual simulated step durations without double counting.

    Startup alignment is the initial contiguous stopped interval only.
    After the first moving step, every step is assigned by its target mode.
    Stop time uses exactly zero modeled speed; near-zero is strictly positive
    speed below the diagnostic threshold. Terminal zero-duration frames do
    not contribute. Invalid timelines are rejected rather than normalized.
    """
    phases = {p: {"seconds":0., "stationarySeconds":0., "nearZeroSeconds":0.,
                  "movingSeconds":0.} for p in _PHASES}
    if (report.get("classification") != "SYNTHETIC_CLOSED_LOOP_ONLY"
            or report.get("model", {}).get("speedPolicy") != "turn-limited-rejoin"):
        raise TraceError("recovery audit requires synthetic rejoin report")
    frames = report["frames"]
    if not frames:
        raise TraceError("empty synthetic frame timeline")
    started = False
    elapsed = 0.
    stopped_runs = 0
    stopped = False
    for i, frame in enumerate(frames):
        dt, speed, t = (frame[k] for k in ("stepSeconds", "speed", "t"))
        if any(type(v) not in (int,float) or not math.isfinite(v) or v < 0
               for v in (dt,speed,t)) or not math.isclose(t, elapsed, abs_tol=1e-8, rel_tol=0.):
            raise TraceError("invalid synthetic step timing or speed")
        if i == len(frames)-1:
            if dt != 0. or speed != 0.:
                raise TraceError("synthetic terminal frame must be stationary")
            continue
        mode = frame.get("targetMode")
        if dt <= 0. or mode not in ("lookahead", "local-projection-rejoin"):
            raise TraceError("invalid synthetic step mode or duration")
        # A startup stop is not recovery. Once motion begins, all later
        # intervals count as the current target mode, including later turns.
        phase = "startup-alignment" if not started and speed == 0. else mode
        bucket = phases[phase]
        bucket["seconds"] += dt
        if speed == 0.:
            bucket["stationarySeconds"] += dt
            if not stopped:
                stopped_runs += 1
            stopped = True
        else:
            bucket["movingSeconds"] += dt
            if speed < _NEAR_ZERO_SPEED:
                bucket["nearZeroSeconds"] += dt
            started = True
            stopped = False
        elapsed += dt
    moving = sum(p["movingSeconds"] for p in phases.values())
    stationary = sum(p["stationarySeconds"] for p in phases.values())
    near_zero = sum(p["nearZeroSeconds"] for p in phases.values())
    metrics = report["metrics"]
    if not (math.isclose(elapsed, metrics["elapsedSeconds"], abs_tol=1e-8, rel_tol=0.)
            and math.isclose(moving, metrics["forwardSeconds"], abs_tol=1e-8, rel_tol=0.)):
        raise TraceError("phase totals disagree with original simulation metrics")
    return {"elapsedSeconds":elapsed, "movingSeconds":moving,
            "stationarySeconds":stationary, "nearZeroMovingSeconds":near_zero,
            "stationaryRuns":stopped_runs, "phases":phases,
            "positiveVelocityDutyRatio": moving/elapsed if elapsed else 0.,
            "atLeastThresholdDutyRatio":(moving-near_zero)/elapsed if elapsed else 0.}


def audit_recovery_efficiency() -> dict:
    """Retain per-case timing diagnostics and group summaries for all 162 cases.

    The existing holdout evaluator establishes the scenario set and baseline
    metrics. Rerun the unchanged recovery model to obtain full step frames;
    compare its metrics before using the detailed time partition.
    """
    baseline = evaluate_holdout(include_rejoin=True)
    rows = []
    for case in baseline["cases"]:
        trace = _case_trace({k:case[k] for k in _SPEC_KEYS})
        result = simulate_route(trace, speed=case["speed"], max_yaw_rate=case["maxYawRate"],
                                dt=case["dt"], max_seconds=40., speed_policy="turn-limited-rejoin")
        expected = case["turn-limited-rejoin"]
        if result["metrics"] != expected["metrics"] or result["status"] != expected["status"]:
            raise TraceError("recovery rerun differs from baseline case")
        rows.append({"case":case["case"], "routeId":case["routeId"],
                     "scenarioSHA256":trace.trace_sha256, "status":result["status"],
                     "metrics":result["metrics"], **measure_recovery_phases(result)})
    def summarize(group):
        """Use the full group, not just successful or fast trajectories."""
        return {"cases":len(group),
                "meanStationarySeconds":mean(r["stationarySeconds"] for r in group),
                "meanNearZeroMovingSeconds":mean(r["nearZeroMovingSeconds"] for r in group),
                "meanPositiveVelocityDutyRatio":mean(r["positiveVelocityDutyRatio"] for r in group),
                "meanAtLeastThresholdDutyRatio":mean(r["atLeastThresholdDutyRatio"] for r in group),
                "meanStationarySecondsByPhase":{
                    p:mean(r["phases"][p]["stationarySeconds"] for r in group) for p in _PHASES},
                "meanElapsedSeconds":mean(r["elapsedSeconds"] for r in group)}
    return {"schema":"taxi.synthetic-recovery-phase-audit/1",
            "classification":"SYNTHETIC_CLOSED_LOOP_ONLY",
            "scenarioSet":baseline["scenarioSet"], "speedPolicy":"turn-limited-rejoin",
            "nearZeroSpeedThresholdSyntheticUnitsPerSecond":_NEAR_ZERO_SPEED,
            "summary":summarize(rows),
            "byRoute":[{"routeId":r["routeId"], **summarize(
                [x for x in rows if x["routeId"]==r["routeId"]])} for r in baseline["byRoute"]],
            "cases":rows, "gameInputSent":False, "liveArrivalVerified":False,
            "liveNavigabilityVerified":False,
            "limitations":[
                "Only ideal model step durations and velocities are measured.",
                "The separate near-zero threshold is not a measured RIFT motion threshold.",
                "These scenarios have already been used to tune recovery, not independent validation.",
            ]}
