"""Opt-in ideal command-application pose experiment on observed scenarios.

Entry: compare_latency_prediction() and CLI compare-latency-prediction.
No game, hardware, OS input, memory, map or live pose. The predictor
knows the exact FIFO of previously issued synthetic commands. The
comparison reuses frozen V3 and factorial development sets, including
their overlap; never add their counts as independent evidence.
"""
from collections import Counter

from .contracts import TraceError
from .simulation import simulate_route
from .simulation_holdout import _case_trace
from .simulation_holdout_v3 import evaluate_holdout_v3
from .simulation_delay_factorial import evaluate_delay_factorial
from .simulation_settling import drain_after_arrival
from .simulation_integrity import verify_synthetic_trajectory

_KEYS = ("routeId", "routeXYZ", "initialXYZ", "initialYawDegrees",
         "lateralOffset", "headingOffsetDegrees", "speed", "maxYawRate", "dt")
_OUTCOMES = ("geometricArrival", "settledWithinTolerance", "arrivalAndDutyTarget")
_POLICY = "turn-limited-ordered"


def _run_candidate(spec, digest, delay):
    """Keep source identity and all model bounds matched to the baseline."""
    trace = _case_trace({k: spec[k] for k in _KEYS}, generator="taxi-holdout-v3")
    if trace.trace_sha256 != digest:
        raise TraceError("latency experiment scenario digest mismatch")
    result = simulate_route(trace, speed=spec["speed"], max_yaw_rate=spec["maxYawRate"],
                            dt=spec["dt"], max_seconds=40., speed_policy=_POLICY,
                            delay_steps=delay, predict_command_application=True)
    verify_synthetic_trajectory(result, trace)
    drain = drain_after_arrival(result, trace)  # Also verifies actual corner witnesses.
    metrics = result["metrics"]
    return {
        "status": result["status"],
        "geometricArrival": metrics["syntheticArrival"],
        "settledWithinTolerance": drain["settledWithinTolerance"],
        "arrivalAndDutyTarget": metrics["syntheticArrival"] and metrics["forwardDutyRatio"] >= .95,
        "elapsedSeconds": metrics["elapsedSeconds"],
        "forwardDutyRatio": metrics["forwardDutyRatio"],
        "finalXZError": metrics["finalXZError"],
        "settledErrorXZ": drain.get("settledErrorXZ"),
        "postArrivalDistanceXZ": drain.get("postArrivalDistanceXZ"),
    }


def _v3_outcome(original):
    metrics = original["metrics"]
    drain = original["terminalDrain"]
    return {"status": original["status"],
            "geometricArrival": metrics["syntheticArrival"],
            "settledWithinTolerance": drain["settledWithinTolerance"],
            "arrivalAndDutyTarget": original["arrivalAndDutyTarget"],
            "elapsedSeconds": metrics["elapsedSeconds"],
            "forwardDutyRatio": metrics["forwardDutyRatio"],
            "finalXZError": metrics["finalXZError"],
            "settledErrorXZ": drain.get("settledErrorXZ"),
            "postArrivalDistanceXZ": drain.get("postArrivalDistanceXZ")}


def _row(spec, case, digest, delay, baseline):
    candidate = _run_candidate(spec, digest, delay)
    if delay == 0 and candidate != baseline:
        raise TraceError("prediction changed zero-delay baseline")
    return {"case": case, "scenarioSHA256": digest, **{k: spec[k] for k in _KEYS},
            "delaySteps": delay, "nominalDelaySeconds": delay * spec["dt"],
            "baseline": baseline, "candidate": candidate}


def _summary(rows):
    """Separate gains/losses; don't hide adverse cases in net changes."""
    result = {"pairs": len(rows)}
    for key in _OUTCOMES:
        counts = Counter()
        for r in rows:
            a, b = r["baseline"][key], r["candidate"][key]
            counts["baseline"] += a
            counts["candidate"] += b
            counts["gained"] += b and not a
            counts["lost"] += a and not b
        result[key] = {k: counts[k] for k in ("baseline", "candidate", "gained", "lost")}
    result["candidateStatusCounts"] = dict(sorted(Counter(r["candidate"]["status"] for r in rows).items()))
    return result


def _group(rows, label, by):
    groups = sorted({r[by] for r in rows})
    return {"scenarioSet": label, "pairs": len(rows),
            "summary": _summary(rows),
            "byDelay": [{by: value, **_summary([r for r in rows if r[by] == value])}
                        for value in groups],
            "cases": rows}


def compare_latency_prediction():
    """Compare 216 V3 pairs and 864 factorial pairs; overlapping development sets.

    Existing policies and reports remain frozen. Each candidate is checked
    independently for integration/FIFO consistency and actual corner evidence.
    No parameter selection from these observed results is a fresh holdout.
    """
    v3 = []
    for case in evaluate_holdout_v3()["cases"]:
        for delay in (0, 1, 3):
            baseline = _v3_outcome(case["outcomes"][f"{_POLICY}:{delay}"])
            v3.append(_row(case, case["case"], case["scenarioSHA256"], delay, baseline))
    source = evaluate_delay_factorial()
    geometry = {r["geometryCase"]: r for r in source["geometry"]}
    factorial = []
    for case in source["cases"]:
        spec = {**geometry[case["geometryCase"]], **case}
        baseline = {k: case[k] for k in v3[0]["baseline"]}
        row = _row(spec, case["geometryCase"], case["scenarioSHA256"], case["delaySteps"], baseline)
        # Group on the declared matched nominal delay rather than floating
        # multiplication differences between dt profiles.
        row["nominalDelaySeconds"] = case["nominalDelaySeconds"]
        factorial.append(row)
    return {"schema": "taxi.synthetic-command-prediction-comparison/1",
            "classification": "SYNTHETIC_CLOSED_LOOP_ONLY",
            "candidate": "queued-pose-midpoint/1",
            "sets": [_group(v3, "observed-v3", "delaySteps"),
                     _group(factorial, "observed-v3-factorial", "nominalDelaySeconds")],
            "gameInputSent": False, "liveArrivalVerified": False,
            "limitations": [
                "Exact known deterministic FIFO and ideal midpoint plant; no physical prediction or calibration.",
                "Control pose prediction never advances observed progress or witnesses.",
                "Sets overlap and informed development; retain negative outcomes and test on new geometry.",
                "Positive modeled velocity duty is not physical key duty.",
            ]}
