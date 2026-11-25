"""Independent offline verification of the observed V4 terminal receipts.

No simulator imports. Recompute midpoint integration from saved synthetic
queue commands, not from a live process. This checks the archived model
observations, not the validity of the plant or a real actuator.
"""
import argparse
import hashlib
import json
import math
from itertools import product
from statistics import mean
from pathlib import Path
import zipfile

from .delay_factorial_audit import require, parse_report

LIMIT = 8 * 1024 * 1024
MEMBER = "v4-terminal-observation.json"
# Independent frozen design: hashes alone do not establish that the
# archived scenarios belong to this particular study.
ROUTE = [[0., 0., 0.], [7., 0., 1.], [7.2, 0., 2.],
         [1., 0., 3.], [1.2, 0., 4.2], [8., 0., 5.]]
PROFILES = ((2.8, 85., .06), (3.1, 115., .12))
OFFSETS = (-.45, .85)
HEADINGS = (-55., 70., 155.)


def close(a, b):
    require(type(a) in (int, float) and type(b) in (int, float)
            and math.isclose(a, b, abs_tol=1e-9, rel_tol=0.),
            "numeric observation mismatch")


def verify_zip(path, expected_sha256):
    """Read only the single expected member and bound compressed/uncompressed bytes."""
    with Path(path).open("rb") as f:
        raw = f.read(LIMIT + 1)
    require(len(raw) <= LIMIT, "oversized ZIP")
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, "ZIP SHA-256 mismatch")
    from io import BytesIO
    with zipfile.ZipFile(BytesIO(raw)) as z:
        entries = z.infolist()
        require(len(entries) == 1 and entries[0].filename == MEMBER
                and entries[0].file_size <= LIMIT, "unexpected ZIP member")
        with z.open(entries[0]) as f:
            member = f.read(LIMIT + 1)
    digest = hashlib.sha256(member).hexdigest()
    report = parse_report(member, digest)
    receipt = verify(report)
    return dict(receipt, zipSHA256=expected_sha256, jsonSHA256=digest)


def verify(report):
    """Check each saved observation against the ideal midpoint model."""
    require(report["schema"] == "taxi.synthetic-v4-terminal-observation/1"
            and report["physicalQualification"] is False
            and report["gameInputSent"] is False, "unexpected report identity")
    rows = report["rows"]
    require(len(rows) == report["pairs"] == 12
            and len({r["scenarioSHA256"] for r in rows}) == 12, "pair coverage")
    # Reconcile the complete design before accepting any measurements.
    design = set()
    for row in rows:
        spec = row["scenario"]
        require(spec["routeXYZ"] == ROUTE, "unexpected geometry")
        key = (spec["lateralOffset"], spec["headingOffsetDegrees"],
               (spec["speed"], spec["maxYawRate"], spec["dt"]))
        design.add(key)
        offset, heading, _ = key
        length = math.hypot(7., 1.)
        for value, expected in zip(spec["initialXYZ"], (-offset/length, 0., 7.*offset/length)):
            close(value, expected)
        require(len(spec["initialXYZ"]) == 3, "initial pose dimension")
        close(spec["initialYawDegrees"], math.degrees(math.atan2(1., 7.)) + heading)
    require(design == set(product(OFFSETS, HEADINGS, PROFILES)), "frozen design coverage")
    intervals = 0
    counts = {}
    for side in ("baseline", "candidate"):
        settled = 0
        travels, changes = [], []
        exits = 0
        for row in rows:
            spec = row["scenario"]
            require(spec["routeId"] == "long-short-ladder", "unexpected route")
            canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"), allow_nan=False)
            require(hashlib.sha256(canonical.encode()).hexdigest() == row["scenarioSHA256"],
                    "scenario digest mismatch")
            dt = spec["dt"]
            require(dt in (.06, .12) and row["delaySeconds"] == .36, "unexpected delay")
            outcome = row[side]
            require(outcome["arrived"] is True and type(outcome["settled"]) is bool,
                    "unexpected observed outcome")
            t = outcome["terminal"]
            q, observations = t["queue"], t["observations"]
            require(len(q) == round(.36 / dt) and len(observations) == len(q) + 2,
                    "queue coverage")
            goal = spec["routeXYZ"][-1]
            for i, obs in enumerate(observations):
                close(obs["elapsedAfterArrivalSeconds"], i * dt)
                close(obs["destinationErrorXZ"],
                      math.hypot(obs["xyz"][0]-goal[0], obs["xyz"][2]-goal[2]))
                if i == 0:
                    continue
                # The last extra sample is the stationary model witness.
                command = q[i-1] if i <= len(q) else {
                    "speed": 0., "yawRateDegreesPerSecond": 0.}
                v, rate = command["speed"], command["yawRateDegreesPerSecond"]
                require(type(v) in (int, float) and type(rate) in (int, float)
                        and 0 <= v <= spec["speed"] and abs(rate) <= spec["maxYawRate"],
                        "queue outside model bounds")
                close(v, obs["appliedSpeed"])
                close(rate, obs["appliedYawRateDegreesPerSecond"])
                prev = observations[i-1]
                mid = math.radians(prev["yawDegrees"] + rate*dt/2)
                close(obs["xyz"][0], prev["xyz"][0] + v*dt*math.cos(mid))
                close(obs["xyz"][2], prev["xyz"][2] + v*dt*math.sin(mid))
                close(obs["xyz"][1], prev["xyz"][1])
                close((obs["yawDegrees"]-prev["yawDegrees"]-rate*dt+180)%360-180, 0.)
                intervals += 1
            close(t["queuedTravel"], sum(c["speed"]*dt for c in q))
            close(t["drainSeconds"], len(q)*dt)
            close(t["firstError"], observations[0]["destinationErrorXZ"])
            close(t["finalError"], observations[-1]["destinationErrorXZ"])
            close(t["maxError"], max(o["destinationErrorXZ"] for o in observations))
            close(t["errorChange"], t["finalError"]-t["firstError"])
            require(t["leftTolerance"] is (t["maxError"] > .30)
                    and outcome["settled"] is (t["finalError"] <= .30),
                    "tolerance outcome mismatch")
            require(t["firstError"] <= .30, "initial arrival outside tolerance")
            settled += outcome["settled"]
            exits += t["leftTolerance"]
            travels.append(t["queuedTravel"])
            changes.append(t["errorChange"])
        # A report may have valid individual observations but corrupted
        # aggregate statistics. Independently derive every summary field.
        summary = report["summary"][side]
        for field, expected in (("arrivals", 12), ("settled", settled), ("sampledExits", exits)):
            require(type(summary[field]) is int and summary[field] == expected,
                    "terminal summary count mismatch")
        close(summary["meanQueuedTravel"], mean(travels))
        close(summary["meanErrorChange"], mean(changes))
        counts[side] = settled
    require(intervals == 132 and counts == {"baseline": 11, "candidate": 0},
            "observed V4 terminal counts disagree")
    return dict(pairs=12, intervals=intervals, settled=counts, physicalQualification=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify_zip(args.archive, args.sha256), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, OverflowError, zipfile.BadZipFile, IndexError, RuntimeError) as exc:
        parser.exit(2, f"Terminal audit failed: {exc}\n")


if __name__ == "__main__":
    main()
