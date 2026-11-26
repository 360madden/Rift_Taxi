"""Combined sampled-telemetry, delay and actuator-response mismatch study.

This offline experiment uses the existing sampled closed-loop simulator.
The predictor's nominal delay and gains are fixed before observing results;
a matched exact-model reference provides a best-information comparator.
No game access, physical calibration, production promotion or input.
"""
import argparse
from itertools import product
import json
from pathlib import Path

from .contracts import TraceError
from .simulation_holdout import _case_trace
from .synthetic_sampled_steering import run, DT
from .synthetic_journey_batch import paired_metrics

GENERATOR = "taxi-combined-uncertainty-20261126-v1"
# Fixed authored geometry and crossed factors. They are intentionally
# distinct from the prior sampled-study routes, not a random sample.
ROUTES = (
    ("offset-corners", ((0,0,0),(4,0,2),(8,0,1),(10,0,5),(15,0,6))),
    ("reversal-exit", ((0,0,0),(6,0,1),(2,0,3),(7,0,7),(12,0,7))),
)
SPEEDS = (2.5, 3.5)
DELAYS = (1, 3, 5)
GAINS = (("unit", 1., 1.), ("slow-response", .85, .75),
         ("fast-response", 1.15, 1.25))
PROFILES = ("steady-delay", "jitter-in-order", "short-dropout", "long-dropout")
POLICIES = ("baseline", "nominal-prediction", "exact-model-reference")
NOMINAL_DELAY = 3


def cases():
    """144 matched conditions with identical physical-model parameters."""
    for (name, points), speed, delay, (gain_name, vg, yg), profile in product(
            ROUTES, SPEEDS, DELAYS, GAINS, PROFILES):
        trace = _case_trace({"routeId": name, "routeXYZ": [list(p) for p in points],
                             "initialXYZ": [0.,0.,.2], "initialYawDegrees": -15.},
                            generator=GENERATOR)
        yield trace, speed, delay, gain_name, vg, yg, profile


def _compact(report, estimated_delay, estimated_gains):
    """Retain adverse outcomes and declared estimator, not just success counts."""
    return {"summary": report["summary"], "stop": report["stop"],
            "admittedSamples": len(report["admissions"]),
            "assumedDelaySteps": estimated_delay,
            "assumedGains": estimated_gains}


def evaluate():
    """Run all fixed conditions: 432 journeys, paired on actual plant and transport.

    Baseline has no prediction. Nominal predictor always assumes three
    command steps and unit gains, independent of the actual plant. Exact
    model predictor is a diagnostic reference, not a feasible live oracle.
    Both predictors use the same steering rules; only information differs.
    """
    rows = []
    for trace,speed,delay,gain_name,vg,yg,profile in cases():
        args = dict(speed=speed,delay=delay,profile=profile,
                    actual_speed_gain=vg,actual_yaw_gain=yg)
        baseline = run(trace,mode="held-pose",**args)
        nominal = run(trace,mode="predict-application",assumed_delay=NOMINAL_DELAY,**args)
        exact = run(trace,mode="predict-application",assumed_delay=delay,
                    assumed_speed_gain=vg,assumed_yaw_gain=yg,**args)
        rows.append({"route": trace.route_id, "scenarioSHA256": trace.trace_sha256,
                     "speed": speed, "actualDelaySteps": delay,
                     "gainProfile": gain_name, "actualGains": [vg,yg], "profile": profile,
                     "results": {"baseline": _compact(baseline,None,None),
                                 "nominal-prediction": _compact(nominal,NOMINAL_DELAY,[1.,1.]),
                                 "exact-model-reference": _compact(exact,delay,[vg,yg])}})
    groups = []
    for delay,(gain_name,_,_),profile in product(DELAYS,GAINS,PROFILES):
        group = [r for r in rows if r["actualDelaySteps"] == delay
                 and r["gainProfile"] == gain_name and r["profile"] == profile]
        # All four route/speed conditions stay matched; no success-only
        # censoring of the arrival counts. paired_metrics separately limits
        # time and duty means to common successes.
        groups.append({"actualDelaySteps": delay, "gainProfile": gain_name,
                       "profile": profile, "comparisons": {
                           m: paired_metrics(group,m) for m in POLICIES[1:]}})
    usable = [r for r in rows if r["profile"] != "long-dropout"]
    return {"schema": "taxi.synthetic-combined-uncertainty/1",
            "classification": "SYNTHETIC_ONLY", "design": GENERATOR,
            "dtSeconds": DT, "caseCount": len(rows), "executionCount": len(rows)*len(POLICIES),
            "nominalAssumption": {"delaySteps": NOMINAL_DELAY,"gains":[1.,1.]},
            "usableTelemetryComparisons": {m: paired_metrics(usable,m) for m in POLICIES[1:]},
            "groups": groups, "rows": rows, "gameInputSent": False, "physicalQualification": False,
            "limitations": ["Constant whole-step delay and fixed multiplicative actuator gains.",
                            "No inertia, collision, noise or physical calibration.",
                            "Exact-model reference has privileged plant parameters.",
                            "Authored geometry and deterministic transport, not statistical validation."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--out", type=Path, help="new JSON output; never overwrite")
    args = parser.parse_args(argv)
    try:
        if args.out is not None and args.out.exists():
            raise FileExistsError(args.out)
        result = evaluate()
        if args.out is not None:
            with args.out.open("x",encoding="utf-8",newline="\n") as f:
                f.write(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
        if args.summary or args.out is None:
            view = {k:v for k,v in result.items() if k not in ("rows","groups")} if args.summary else result
            print(json.dumps(view,sort_keys=True,indent=2,allow_nan=False))
        return 0
    except (TraceError,ValueError,OSError) as exc:
        parser.exit(2,f"Combined uncertainty study refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
