"""Opt-in V4 synthetic parameter sensitivity study; no physical controller.

See docs/V4_OFFLINE_COMPARISON_PROTOCOL.md for the frozen research screen.
The unchanged simulator receives identical traces, plant parameters and
bounds; only its lookahead parameter varies. This is not a queued-pose
predictor or a physical latency compensation model.
"""
import json
from collections import Counter

from .simulation import simulate_route
from .simulation_holdout import _case_trace
from .simulation_holdout_v4_design import scenarios, GENERATOR, DELAYS_SECONDS
from .simulation_integrity import verify_synthetic_trajectory
from .simulation_settling import drain_after_arrival

BASE_LOOKAHEAD = 1.5
MAX_LOOKAHEAD = 3.
OUTCOMES = ("geometricArrival", "settledWithinTolerance", "arrivalAndDutyTarget")


def candidate_lookahead(speed, delay):
    """Prespecified sensitivity only; not a calibrated actuator policy."""
    return min(MAX_LOOKAHEAD, BASE_LOOKAHEAD + speed * delay)


def _run(trace, spec, steps, lookahead):
    result = simulate_route(trace, speed=spec["speed"], max_yaw_rate=spec["maxYawRate"],
                            dt=spec["dt"], lookahead=lookahead, max_seconds=40.,
                            max_cross_track=2., speed_policy="turn-limited-ordered",
                            delay_steps=steps)
    verify_synthetic_trajectory(result, trace)
    drain = drain_after_arrival(result, trace)
    m = result["metrics"]
    return dict(status=result["status"], geometricArrival=m["syntheticArrival"],
                settledWithinTolerance=drain["settledWithinTolerance"],
                arrivalAndDutyTarget=m["syntheticArrival"] and m["forwardDutyRatio"] >= .95,
                elapsedSeconds=m["elapsedSeconds"], forwardDutyRatio=m["forwardDutyRatio"],
                finalErrorXZ=m["finalXZError"], settledErrorXZ=drain.get("settledErrorXZ"))


def summarize(rows):
    """Pair outcomes directly; retain losses even when marginal totals improve."""
    summaries = []
    for delay in DELAYS_SECONDS:
        group = [r for r in rows if r["delaySeconds"] == delay]
        effects = {}
        for name in OUTCOMES:
            counts = Counter()
            for row in group:
                a, b = row["baseline"][name], row["candidate"][name]
                counts["both" if a and b else "lost" if a else "gained" if b else "neither"] += 1
            effects[name] = {k: counts[k] for k in ("both", "lost", "gained", "neither")}
        summaries.append(dict(delaySeconds=delay, pairs=len(group), outcomes=effects))
    zero_equal = all(r["baseline"] == r["candidate"] for r in rows if r["delaySeconds"] == 0.)
    no_losses = all(s["outcomes"][name]["lost"] == 0 for s in summaries for name in OUTCOMES)
    settled_gain = sum(s["outcomes"]["settledWithinTolerance"]["gained"]
                       for s in summaries if s["delaySeconds"] != 0.) > 0
    return summaries, dict(zeroDelayExactMatch=zero_equal, noBaselineSuccessLosses=no_losses,
                           nonzeroDelaySettledGain=settled_gain,
                           meritsFurtherOfflineInvestigation=zero_equal and no_losses and settled_gain)


def evaluate():
    """Run all 216 pairs including failures, without mutating any frozen inputs."""
    rows = []
    for item in scenarios():
        spec = item["scenario"]
        trace = _case_trace(spec, generator=GENERATOR)
        if trace.trace_sha256 != item["scenarioSHA256"]:
            raise ValueError("scenario identity mismatch")
        for delay, steps in zip(DELAYS_SECONDS, item["delaySteps"]):
            candidate = candidate_lookahead(spec["speed"], delay)
            rows.append(dict(scenarioSHA256=trace.trace_sha256, routeId=spec["routeId"],
                             delaySeconds=delay, delaySteps=steps,
                             baselineLookahead=BASE_LOOKAHEAD, candidateLookahead=candidate,
                             baseline=_run(trace, spec, steps, BASE_LOOKAHEAD),
                             candidate=_run(trace, spec, steps, candidate)))
    if len(rows) != 216 or len({(r["scenarioSHA256"], r["delaySeconds"]) for r in rows}) != 216:
        raise ValueError("incomplete or duplicate V4 comparison")
    summaries, gate = summarize(rows)
    return dict(schema="taxi.synthetic-v4-lookahead-comparison/1", scenarioSet=GENERATOR,
                pairs=len(rows), simulations=2*len(rows), rows=rows, summaries=summaries,
                researchScreen=gate, physicalQualification=False, gameInputSent=False)


if __name__ == "__main__":
    print(json.dumps(evaluate(), sort_keys=True, allow_nan=False))
