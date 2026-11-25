"""Audit saved synthetic factorial reports without importing the simulator.

Usage: python -m rift_taxi.delay_factorial_audit REPORT --sha256 EXPECTED
The expected hash must come from an independently trusted receipt. This
checks archive identity and internal consistency, not physical performance.
"""
import argparse
from collections import Counter
import hashlib
from itertools import product
import json
import math
from pathlib import Path

FACTORS = {"speed": (2.2, 3.4), "maxYawRate": (65., 140.), "dt": (.055, .11)}
DELAYS = (0., .11, .33)
OUTCOMES = ("geometricArrival", "settledWithinTolerance", "arrivalAndDutyTarget")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def key(row):
    return (row["geometryCase"], *(row[f] for f in FACTORS), row["nominalDelaySeconds"])


def summary(rows):
    """Recount from individual observations, never trust saved aggregates."""
    return {"runs": len(rows), "geometricArrivals": sum(r[OUTCOMES[0]] for r in rows),
            "settledWithinTolerance": sum(r[OUTCOMES[1]] for r in rows),
            "arrivalAndDutyTarget": sum(r[OUTCOMES[2]] for r in rows),
            "settledOutside": sum(r[OUTCOMES[0]] and not r[OUTCOMES[1]] for r in rows),
            "statusCounts": dict(Counter(r["status"] for r in rows))}


def audit(report):
    """Check complete fixed design, case invariants and independent pair counts."""
    require(report["schema"] == "taxi.synthetic-delay-factorial/1" and
            report["classification"] == "SYNTHETIC_CLOSED_LOOP_ONLY" and
            report["speedPolicy"] == "turn-limited-ordered" and
            report["gameInputSent"] is False and report["liveArrivalVerified"] is False,
            "unexpected report identity or authority")
    require((report["geometryCount"], report["profileCount"], report["simulationCount"]) == (36, 24, 864),
            "incorrect design counts")
    geometry = {r["geometryCase"]: r["routeId"] for r in report["geometry"]}
    require(len(report["geometry"]) == 36 and set(geometry) == set(range(1, 37)), "geometry coverage")
    rows = report["cases"]
    # Python bools compare equal to 0/1 and can otherwise masquerade as
    # integer design identifiers or numeric measurement values.
    require(all(type(r["geometryCase"]) is int for r in report["geometry"]), "noninteger geometry ID")
    for row in rows:
        require(type(row["geometryCase"]) is int, "noninteger case ID")
        require(all(type(row[n]) in (int, float) and math.isfinite(row[n])
                    for n in (*FACTORS, "nominalDelaySeconds", "forwardDutyRatio")),
                "invalid numeric factor or duty")
        require(all(row[n] is None or (type(row[n]) in (int, float) and math.isfinite(row[n]))
                    for n in ("settledErrorXZ", "postArrivalDistanceXZ")), "invalid terminal measurement")
    indexed = {key(r): r for r in rows}
    expected = set(product(range(1, 37), *FACTORS.values(), DELAYS))
    require(len(rows) == len(indexed) == 864 and set(indexed) == expected, "missing or duplicate case")
    hashes = {}
    for k, row in indexed.items():
        require(row["routeId"] == geometry[k[0]], "route mismatch")
        digest = row["scenarioSHA256"]
        require(isinstance(digest, str) and len(digest) == 64 and
                all(c in "0123456789abcdef" for c in digest), "invalid scenario hash")
        require(hashes.setdefault(k[:-1], digest) == digest, "scenario changed with delay")
        steps = row["delaySteps"]
        require(type(steps) is int and 0 <= steps <= 10 and
                math.isclose(steps * k[3], k[4], abs_tol=1e-12, rel_tol=0), "delay mismatch")
        require(all(type(row[n]) is bool for n in OUTCOMES), "nonboolean outcome")
        arrived, settled, duty = (row[n] for n in OUTCOMES)
        ratio = row["forwardDutyRatio"]
        require(0 <= ratio <= 1 and duty == (arrived and ratio >= .95), "duty mismatch")
        error = row["settledErrorXZ"]
        distance = row["postArrivalDistanceXZ"]
        # Failed approaches must not silently acquire a terminal observation.
        require((arrived and error is not None and distance is not None and
                 math.isfinite(error) and math.isfinite(distance) and error >= 0 and distance >= 0 and
                 settled == (error <= .30)) or
                (not arrived and not settled and error is None and distance is None), "settling mismatch")
    require(len(set(hashes.values())) == 288, "nonunique scenario identity")
    profiles = [{**dict(zip((*FACTORS, "nominalDelaySeconds"), p)),
                 **summary([indexed[(g, *p)] for g in range(1, 37)])}
                for p in product(*FACTORS.values(), DELAYS)]
    require(report["profiles"] == profiles, "profile summary mismatch")
    require(report["byDelay"] == [{"nominalDelaySeconds": d, **summary([r for r in rows if key(r)[-1] == d])}
                                  for d in DELAYS], "delay summary mismatch")
    # Generate each low/high pair from the complete Cartesian design rather
    # than grouping whatever rows happen to be present in the archive.
    effects = []
    for i, (factor, (low, high)) in enumerate(FACTORS.items(), 1):
        for delay in DELAYS:
            counts = {n: dict.fromkeys(("gained", "lost", "both", "neither"), 0) for n in OUTCOMES}
            for k in sorted(expected):
                if k[i] != low or k[-1] != delay:
                    continue
                b = indexed[k[:i] + (high,) + k[i+1:]]
                a = indexed[k]
                for n in OUTCOMES:
                    counts[n][("neither", "gained", "lost", "both")[2*a[n]+b[n]]] += 1
            effects.append({"factor": factor, "low": low, "high": high,
                            "nominalDelaySeconds": delay, "pairs": 144, "outcomes": counts})
    require(report["matchedEffects"] == effects, "matched effect mismatch")
    return {"cases": 864, "profiles": 24, "matchedEffects": 9, "physicalQualification": False}


def _unique_object(pairs):
    """Reject ambiguous JSON: Python otherwise keeps only the final duplicate key."""
    result = {}
    for name, value in pairs:
        require(name not in result, f"duplicate JSON key: {name}")
        result[name] = value
    return result


def _finite_float(token):
    """Reject both explicit non-finite literals and overflowing exponents."""
    value = float(token)
    require(math.isfinite(value), "non-finite JSON number")
    return value


def audit_bytes(raw, expected_sha256):
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, "archive SHA-256 mismatch")
    return audit(json.loads(raw, object_pairs_hook=_unique_object,
                            parse_float=_finite_float, parse_constant=_finite_float))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(audit_bytes(args.report.read_bytes(), args.sha256), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        parser.exit(2, f"Audit failed: {exc}\n")


if __name__ == "__main__":
    main()
