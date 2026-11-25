"""Descriptive stratification of the existing synthetic factorial archive.

This module never changes the simulator, its inputs, or its frozen reports.
Each route is analysed with complete matched pairs. Terminal distributions
are conditional on geometric arrival, with the missing denominator explicit.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import median

from .delay_factorial_audit import FACTORS, DELAYS, OUTCOMES, audit, parse_report, read_report


def stratify(report):
    """Return independently counted route/factor strata and delay patterns."""
    audit(report)
    routes = defaultdict(list)
    for row in report["cases"]:
        routes[row["routeId"]].append(row)
    results = []
    for route, rows in sorted(routes.items()):
        effects = []
        for factor, (low, high) in FACTORS.items():
            others = tuple(f for f in FACTORS if f != factor)
            for delay in DELAYS:
                pairs = defaultdict(dict)
                for row in rows:
                    if row["nominalDelaySeconds"] == delay:
                        key = (row["geometryCase"], *(row[f] for f in others))
                        pairs[key][row[factor]] = row
                counts = {}
                for outcome in OUTCOMES:
                    c = Counter()
                    for pair in pairs.values():
                        a, b = pair[low][outcome], pair[high][outcome]
                        c["both" if a and b else "lost" if a else "gained" if b else "neither"] += 1
                    counts[outcome] = {k: c[k] for k in ("both", "lost", "gained", "neither")}
                effects.append(dict(factor=factor, low=low, high=high,
                                    delaySeconds=delay, pairs=len(pairs), outcomes=counts))
        # Retain all eight possible three-delay binary histories, including
        # failures that later recover; a marginal total cannot reveal these.
        histories = defaultdict(dict)
        for row in rows:
            k = (row["geometryCase"], *(row[f] for f in FACTORS))
            histories[k][row["nominalDelaySeconds"]] = row
        patterns = {}
        for outcome in OUTCOMES:
            c = Counter("".join("1" if h[d][outcome] else "0" for d in DELAYS)
                        for h in histories.values())
            patterns[outcome] = dict(sorted(c.items()))
        terminal = []
        for delay in DELAYS:
            group = [r for r in rows if r["nominalDelaySeconds"] == delay]
            errors = sorted(r["settledErrorXZ"] for r in group if r["geometricArrival"])
            terminal.append(dict(delaySeconds=delay, total=len(group), arrivals=len(errors),
                                 failedApproaches=len(group)-len(errors),
                                 minError=min(errors, default=None),
                                 medianError=median(errors) if errors else None,
                                 maxError=max(errors, default=None),
                                 outsideTolerance=sum(e > .30 for e in errors)))
        results.append(dict(routeId=route, effects=effects, delayHistories=patterns,
                            terminalDistribution=terminal))
    return dict(schema="taxi.synthetic-delay-stratification/1",
                physicalQualification=False, routes=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        result = stratify(parse_report(read_report(args.report), args.sha256))
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        parser.exit(2, f"Stratification failed: {exc}\n")


if __name__ == "__main__":
    main()
