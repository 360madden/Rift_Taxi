"""Reproducible end-to-end comparison on the frozen November 24 smoke design.

This offline CLI evaluates the existing journey engine, including its FIFO
drain and final correction, with identical inputs for each eligible policy.
The geometry has already been observed during development; it is NOT an
unseen holdout, a physical route, or grounds for enabling game input.
No game or sibling repository is accessed. Output is deterministic JSON.
"""
import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
from statistics import fmean

from .contracts import TraceError
from .simulation_holdout import _case_trace
from .synthetic_journey_demo import compact_report, journey

GENERATOR = "taxi-near-stall-fixed-smoke-20261124"
# Historical provenance, not a claim that the archive was authenticated by
# running this module. The original report contained approach-only results.
SOURCE_SHA256 = "7f25b693911db7c824f48a8996eda8de2e7e4727e4f5450062f54fe85d6bc90e"
# Preserve exact integer/float representation: _case_trace hashes canonical
# JSON, so 0 versus 0.0 changes the original scenario digest.
ROUTES = (
    ("staggered-finish", ((0,0,0),(3,0,0),(4,0,2),(7,0,2),(7.4,0,2.4))),
    ("return-offset", ((0,0,0),(5,0,0),(6,0,1),(2,0,2),(2,0,4))),
    ("oblique-ladder", ((0,0,0),(3,0,1),(3.5,0,3),(7,0,4),(7.5,0,6),(10,0,7))),
    ("short-final-z", ((0,0,0),(4,0,0),(4,0,3),(8,0,3),(8,0,3.35))),
)
PROFILES = ((.08,2.8,80.), (.12,3.6,125.))
HEADINGS = (-50., 20.)
DELAYS = (0, 1, 3)
CANDIDATES = ("zero-delay-rejoin", "predict-near-goal", "predict-near-stall")
BOUNDS = {"approach_budget": 40., "terminal_budget": 5., "lookahead": 1.5}


def cases():
    """Yield fresh trace specs and model parameters for all 48 fixed cases.

    Delay is measured in whole model steps, not milliseconds; eligibility
    follows the journey API. A trace digest identifies geometry and initial
    conditions, while the complete case identity also includes its profile
    and delay, because the same trace is used in multiple model runs.
    """
    for (name, points), heading, (dt, speed, rate), delay in product(
            ROUTES, HEADINGS, PROFILES, DELAYS):
        spec = {"routeId": name, "routeXYZ": [list(p) for p in points],
                "initialXYZ": [0., 0., .35], "initialYawDegrees": heading}
        yield spec, dt, speed, rate, delay


def paired_metrics(rows, mode):
    """Compare only cases eligible for this candidate against their baseline.

    Gains/losses count all matched cases. Mean duration and forward duty
    are computed only on common settled successes to avoid comparing
    a timeout with an arrival or selecting different success populations.
    Empty common-success groups are represented by null, never zero.
    """
    matched = [(row["results"]["baseline"]["summary"],
                row["results"][mode]["summary"])
               for row in rows if mode in row["results"]]
    common = [(a, b) for a, b in matched
              if a["finalModelSettled"] and b["finalModelSettled"]]
    def means(index):
        if not common:
            return None
        return {
            "meanTotalElapsedSeconds": fmean(pair[index]["totalElapsedSeconds"] for pair in common),
            "meanTotalForwardDutyRatio": fmean(pair[index]["totalForwardDutyRatio"] for pair in common),
        }
    return {
        "matchedCases": len(matched),
        "baselineSettled": sum(a["finalModelSettled"] for a, _ in matched),
        "candidateSettled": sum(b["finalModelSettled"] for _, b in matched),
        "settledGains": sum(not a["finalModelSettled"] and b["finalModelSettled"] for a, b in matched),
        "settledLosses": sum(a["finalModelSettled"] and not b["finalModelSettled"] for a, b in matched),
        "commonSettled": len(common),
        "baselineCommonSettledMeans": means(0),
        "candidateCommonSettledMeans": means(1),
    }


def compare():
    """Run the frozen design using the existing engine; keep every failure."""
    rows = []
    for spec, dt, speed, rate, delay in cases():
        trace = _case_trace(spec, generator=GENERATOR)
        modes = ("baseline", "zero-delay-rejoin") if delay == 0 else (
            "baseline", "predict-near-goal", "predict-near-stall")
        identity = {"scenarioSHA256": trace.trace_sha256, "dt": dt,
                    "speed": speed, "yawRate": rate, "delaySteps": delay}
        case_hash = hashlib.sha256(json.dumps(
            identity, sort_keys=True, separators=(",", ":"),
            allow_nan=False).encode("utf-8")).hexdigest()
        results = {}
        for mode in modes:
            results[mode] = compact_report(journey(
                trace, dt=dt, speed=speed, yaw_rate=rate,
                delay_steps=delay, approach_mode=mode, **BOUNDS))
        rows.append({"caseSHA256": case_hash, "route": spec["routeId"],
                     "heading": spec["initialYawDegrees"], **identity,
                     "results": results})
    return {
        "schema": "taxi.synthetic-journey-batch/1",
        "classification": "SYNTHETIC_ONLY",
        "design": GENERATOR,
        "historicalSourceSHA256": SOURCE_SHA256,
        "bounds": BOUNDS.copy(),
        "caseCount": len(rows),
        "executionCount": sum(len(row["results"]) for row in rows),
        "comparisons": {mode: paired_metrics(rows, mode) for mode in CANDIDATES},
        "rows": rows,
        "physicalQualification": False,
        "gameInputSent": False,
        "limitations": "Previously observed authored development design; ideal synthetic actuator, not independent holdout or live evidence.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="new full JSON report; never overwrite")
    parser.add_argument("--summary", action="store_true", help="omit rows on stdout only")
    args = parser.parse_args(argv)
    try:
        # Avoid expensive simulation when an existing destination is known;
        # exclusive creation below is still the authoritative race-safe check.
        if args.out is not None and args.out.exists():
            raise FileExistsError(args.out)
        result = compare()
        if args.out is not None:
            with args.out.open("x", encoding="utf-8", newline="\n") as writer:
                writer.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
        if args.summary:
            print(json.dumps({k: v for k, v in result.items() if k != "rows"},
                             indent=2, sort_keys=True, allow_nan=False))
        elif args.out is None:
            print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (TraceError, ValueError, OSError) as error:
        parser.exit(2, f"Synthetic batch refused: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
