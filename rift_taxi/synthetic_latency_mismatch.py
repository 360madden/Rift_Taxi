"""Prespecified synthetic latency-estimation mismatch experiment.

Only the approach predictor receives an assumed command delay. Observations
are instantaneous, plant delay is fixed, and terminal correction knows actual
delay. No observation jitter, live input, physical calibration or map access.
Retain every case, including regressions, without changing production policy.
"""
import argparse
from itertools import product
import json
from pathlib import Path

from .contracts import TraceError
from .simulation_holdout import _case_trace
from .synthetic_journey_demo import journey, compact_report
from .synthetic_journey_batch import paired_metrics

# Freeze authored design before evaluating outcomes. These routes are distinct
# from the prior 48-case smoke design; not a random or blinded sample.
ROUTES = (
    ("asymmetric-s", ((0,0,0),(3,0,1),(4,0,4),(7,0,4),(9,0,6))),
    ("tight-return", ((0,0,0),(5,0,0),(6,0,2),(3,0,3),(4,0,6))),
    ("short-oblique-end", ((0,0,0),(3,0,2),(6,0,2),(7,0,4),(7.18,0,4.24))),
)
HEADINGS = (-40., 65.)
PROFILES = ((.07, 2.7, 95.), (.11, 3.3, 130.))
DELAYS = (1, 3, 5)
GENERATOR = "taxi-latency-mismatch-20261126-v1"


def cases():
    """Yield 36 fixed matched cases; dt seconds, speed units/s, yaw deg/s."""
    for (name, points), heading, (dt, speed, rate), actual in product(
            ROUTES, HEADINGS, PROFILES, DELAYS):
        spec = {"routeId": name, "routeXYZ": [list(p) for p in points],
                "initialXYZ": [0., 0., .3], "initialYawDegrees": heading}
        yield spec, dt, speed, rate, actual


def evaluate():
    """144 complete journeys; compare estimates to no prediction and exact prediction.

    Baseline is computed once per actual plant condition. Explicitly label
    oracle-like exact estimate as a reference, not a production assumption.
    Use matched common-success time and duty only, and report separate
    settled losses rather than hiding them in a net count.
    """
    rows = []
    for spec, dt, speed, rate, actual in cases():
        trace = _case_trace(spec, generator=GENERATOR)
        kwargs = dict(dt=dt, speed=speed, yaw_rate=rate, delay_steps=actual)
        results = {"baseline": compact_report(journey(trace, **kwargs))}
        for assumed in DELAYS:
            results[str(assumed)] = compact_report(journey(
                trace, **kwargs, approach_mode="predict-near-stall",
                prediction_delay_steps=assumed))
        rows.append({"route": spec["routeId"], "scenarioSHA256": trace.trace_sha256,
                     "heading": spec["initialYawDegrees"], "dt": dt, "speed": speed,
                     "yawRate": rate, "actualDelaySteps": actual, "results": results})
    groups = []
    for actual in DELAYS:
        group = [row for row in rows if row["actualDelaySteps"] == actual]
        for assumed in DELAYS:
            # paired_metrics expects baseline in each row. For the exact
            # reference comparison, create small views without mutating data.
            exact_views = [{"results": {"baseline": row["results"][str(actual)],
                                       "candidate": row["results"][str(assumed)]}}
                           for row in group]
            groups.append({"actualDelaySteps": actual, "assumedDelaySteps": assumed,
                           "versusNoPrediction": paired_metrics(group, str(assumed)),
                           "versusExactPrediction": paired_metrics(exact_views, "candidate")})
    return {"schema": "taxi.synthetic-latency-mismatch/1",
            "classification": "SYNTHETIC_ONLY", "design": GENERATOR,
            "caseCount": len(rows), "executionCount": 4 * len(rows),
            "groups": groups, "rows": rows, "gameInputSent": False,
            "physicalQualification": False,
            "limitations": ["Fixed whole-step plant delay; no sensor delay or jitter.",
                            "Only approach estimate varies; terminal correction uses actual delay.",
                            "Authored synthetic geometries, no real route qualification."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.out is not None and args.out.exists():
            raise FileExistsError(args.out)
        report = evaluate()
        if args.out is not None:
            with args.out.open("x", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
        if args.summary or args.out is None:
            view = {k: v for k, v in report.items() if k != "rows"} if args.summary else report
            print(json.dumps(view, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (TraceError, OSError, ValueError) as exc:
        parser.exit(2, f"Latency mismatch study refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
