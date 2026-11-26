"""Cloud development test inventory, module-preserving sharding, and merge.

Development tool only: Python stdlib, unittest, Git metadata. No RIFT client,
sibling repository, game input, secrets, or production runtime dependency.
Every shard discovers the complete suite and recomputes the same deterministic
plan. The merge independently rediscovers it, refusing missing/extra receipts,
wrong commits, overlapping tests, unexpected skips, and incomplete executions.

Run from the repository root:
  python -B -m scripts.cloud_test_runner plan --shards 4 --out cloud-results/plan.json
  python -B -m scripts.cloud_test_runner run --shards 4 --index 0 --out cloud-results/shard-0.json
  python -B -m scripts.cloud_test_runner merge --shards 4 --dir cloud-results --out cloud-results/merged.json

Plan complete modules using an explicit recorded timing profile when it
matches the runner platform/Python minor, otherwise use test counts. All
module durations include fixtures. Timing is observational, not a coverage gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAX_RECEIPT = 2 * 1024 * 1024
MAX_SHARDS = 8
COST_PROFILE = ROOT / "cloud" / "test_module_costs.json"


class CloudValidationError(ValueError):
    """Invalid inventory, inconsistent source identity, or incomplete evidence."""


def require(condition, message):
    if not condition:
        raise CloudValidationError(message)


def exact_int(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def checkout_identity():
    """Record actual checkout, not a PR head label; cloud checkout must be clean."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, check=True,
                              capture_output=True, text=True, timeout=15).stdout.strip()
    sha = git("rev-parse", "HEAD")
    require(re.fullmatch(r"[0-9a-f]{40}", sha) is not None, "invalid checkout SHA")
    clean = not bool(git("status", "--porcelain", "--untracked-files=normal"))
    identity = {"commit": sha, "cleanCheckout": clean,
                "platform": platform.system(), "python": platform.python_version()}
    if os.environ.get("GITHUB_ACTIONS") == "true":
        require(clean and os.environ.get("GITHUB_SHA") == sha,
                "hosted checkout is dirty or differs from workflow SHA")
        # Keep retries/other runs of the same commit from mixing receipts.
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        require(re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is not None
                and re.fullmatch(r"[1-9][0-9]{0,9}", attempt) is not None
                and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is not None,
                "hosted run/attempt/repository identity missing or invalid")
        identity["hostedRun"] = {"repository": repo, "runId": run_id,
                                 "attempt": attempt}
    # Portable single-runner orchestration adds a unique batch ID to every
    # child process. Plain plan/run/merge remains available for manual use.
    batch_id = os.environ.get("RIFT_TAXI_CLOUD_BATCH_ID")
    if batch_id is not None:
        require(re.fullmatch(r"[0-9a-f]{32}", batch_id) is not None,
                "invalid cloud batch identity")
        identity["batchId"] = batch_id
    return identity


def flatten(suite):
    """Flatten discovered leaf tests without importing any other test source."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def discover():
    loader = unittest.TestLoader()
    tests = list(flatten(loader.discover(str(ROOT / "tests"))))
    require(not loader.errors, "test discovery/import failed: " + "; ".join(loader.errors))
    require(bool(tests), "empty test suite")
    return tests


def declared_skip(test):
    cls = type(test)
    method = getattr(test, test._testMethodName, None)
    return bool(getattr(cls, "__unittest_skip__", False)
                or getattr(method, "__unittest_skip__", False))


def profile_weights(modules, profile, identity):
    """Return integer microsecond estimates, or None for a different platform.

    Historical runtime estimates never determine which tests are eligible.
    Scale known costs for current test counts and use the median measured
    per-test cost for new modules. A single profile is only a planning input;
    runner variability and fixture costs can invalidate a speed prediction.
    """
    require(isinstance(profile, dict) and set(profile) ==
            {"schema", "platform", "pythonMinor", "source", "modules"}
            and profile["schema"] == "taxi.cloud-module-cost-profile/1"
            and profile["platform"] in ("Linux", "Windows", "Darwin")
            and isinstance(profile["pythonMinor"], str)
            and re.fullmatch(r"[0-9]+\.[0-9]+", profile["pythonMinor"]),
            "invalid module cost profile")
    source = profile["source"]
    require(isinstance(source, dict) and set(source) == {"commit", "runId", "attempt", "planSHA256"}
            and isinstance(source["commit"], str) and re.fullmatch(r"[0-9a-f]{40}", source["commit"])
            and isinstance(source["planSHA256"], str) and re.fullmatch(r"[0-9a-f]{64}", source["planSHA256"])
            and isinstance(source["runId"], str) and re.fullmatch(r"[1-9][0-9]{0,19}", source["runId"])
            and isinstance(source["attempt"], str) and re.fullmatch(r"[1-9][0-9]{0,9}", source["attempt"]),
            "invalid module cost provenance")
    rows = profile["modules"]
    require(isinstance(rows, list) and 0 < len(rows) <= 1000, "module cost inventory")
    history, per_test = {}, []
    for row in rows:
        require(isinstance(row, dict) and set(row) ==
                {"module", "testsRun", "elapsedMicroseconds"}, "module cost row")
        name, count, micros = row["module"], row["testsRun"], row["elapsedMicroseconds"]
        require(isinstance(name, str) and 0 < len(name) <= 200 and name not in history
                and exact_int(count, 1, 100000)
                and exact_int(micros, 0, 3600000000), "invalid or duplicate module cost")
        # Floor tiny measurements at 100 microseconds so a skipped module
        # never has zero weight and integer tie-breaking stays deterministic.
        cost = max(100, micros)
        history[name] = (count, cost)
        per_test.append(max(100, (cost+count-1)//count))
    require(list(history) == sorted(history), "unordered module cost inventory")
    if (identity.get("platform") != profile["platform"]
            or ".".join(identity.get("python", "").split(".")[:2]) != profile["pythonMinor"]):
        return None
    per_test.sort()
    fallback = per_test[len(per_test)//2]
    weights = {}
    for name, ids in modules.items():
        count = len(ids)
        if name in history:
            old_count, cost = history[name]
            weights[name] = max(100, (cost*count+old_count-1)//old_count)
        else:
            weights[name] = fallback*count
    return weights


def make_plan(test_ids, skips, shards, identity, *, module_by_id=None, cost_profile=None):
    """Stable longest-estimated-module-first balancing; preserve coverage."""
    require(exact_int(shards, 1, MAX_SHARDS), "shard count outside 1..8")
    require(isinstance(test_ids, list) and bool(test_ids)
            and all(isinstance(i, str) and i.count(".") >= 2 for i in test_ids)
            and len(set(test_ids)) == len(test_ids), "invalid or duplicate test IDs")
    require(isinstance(skips, list) and len(set(skips)) == len(skips)
            and set(skips) <= set(test_ids), "invalid declared skip inventory")
    # Real discovery supplies the actual Python module, not a guess based
    # on dotted IDs (nested TestCase names may contain extra dots). The
    # default remains convenient for pure planner fixtures.
    if module_by_id is None:
        module_by_id = {name: name.rsplit(".", 2)[0] for name in test_ids}
    require(isinstance(module_by_id, dict) and set(module_by_id) == set(test_ids)
            and all(isinstance(m, str) and bool(m) for m in module_by_id.values()),
            "invalid module inventory")
    modules = {}
    for name in test_ids:
        modules.setdefault(module_by_id[name], []).append(name)
    require(len(modules) >= shards, "more shards than test modules")
    estimated = None if cost_profile is None else profile_weights(modules, cost_profile, identity)
    weights = estimated if estimated is not None else {m: len(ids) for m, ids in modules.items()}
    groups = [[] for _ in range(shards)]
    loads = [0] * shards
    test_loads = [0] * shards
    for name in sorted(modules, key=lambda m: (-weights[m], -len(modules[m]), m)):
        i = min(range(shards), key=lambda i: (loads[i], test_loads[i], i))
        groups[i].append(name)
        loads[i] += weights[name]
        test_loads[i] += len(modules[name])
    assignment = []
    for i, names in enumerate(groups):
        ids = sorted(t for m in names for t in modules[m])
        assignment.append({"index": i, "modules": sorted(names), "testIds": ids,
                           "moduleTestIds": {m: sorted(modules[m]) for m in sorted(names)},
                           "declaredSkipIds": sorted(set(ids) & set(skips))})
    body = {"schema": "taxi.cloud-test-plan/1", "identity": identity,
            "testCount": len(test_ids), "moduleCount": len(modules),
            "shardCount": shards, "assignment": assignment,
            "balancingMode": "measured-module-cost" if estimated is not None else "test-count"}
    if estimated is not None:
        body["costProfileSHA256"] = digest(cost_profile)
        body["costProfileSource"] = dict(cost_profile["source"])
        body["estimatedShardMicroseconds"] = loads
    return {**body, "planSHA256": digest(body)}


def current_plan(shards):
    tests = discover()
    profile = read(COST_PROFILE) if COST_PROFILE.exists() else None
    return make_plan([t.id() for t in tests], [t.id() for t in tests if declared_skip(t)],
                     shards, checkout_identity(),
                     module_by_id={t.id(): type(t).__module__ for t in tests},
                     cost_profile=profile), tests


class RecordingResult(unittest.TextTestResult):
    """Record actual started tests; a fixture failure cannot masquerade as coverage."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started_ids = []

    def startTest(self, test):
        self.started_ids.append(test.id())
        super().startTest(test)


def execute_shard(plan, tests, index, *, stream=None):
    """Execute whole modules in discovery order and measure complete fixtures.

    One ordinary unittest runner per module ensures module and class setup
    and teardown are included in its measurement. The exact original test
    inventory, skip and outcome checks remain the authority, not timing.
    No per-test split, repeated class fixture, or parallel test within a module.
    """
    require(exact_int(index, 0, plan["shardCount"] - 1), "invalid shard index")
    expected = plan["assignment"][index]
    owner = {t: module for module, ids in expected["moduleTestIds"].items() for t in ids}
    groups = {}
    for test in tests:
        name = owner.get(test.id())
        if name is not None:
            groups.setdefault(name, []).append(test)
    start = time.monotonic()
    started, skips, timings = [], [], []
    counts = dict(testsRun=0, failures=0, errors=0,
                  unexpectedSuccesses=0, expectedFailures=0)
    successful = True
    for name, cases in groups.items():
        module_start = time.monotonic()
        result = unittest.TextTestRunner(
            stream=stream, verbosity=1, resultclass=RecordingResult
        ).run(unittest.TestSuite(cases))
        elapsed = round(time.monotonic()-module_start, 6)
        started.extend(result.started_ids)
        skips.extend(t.id() for t, _ in result.skipped)
        counts["testsRun"] += result.testsRun
        counts["failures"] += len(result.failures)
        counts["errors"] += len(result.errors)
        counts["unexpectedSuccesses"] += len(result.unexpectedSuccesses)
        counts["expectedFailures"] += len(result.expectedFailures)
        successful = successful and result.wasSuccessful()
        timings.append({"module": name, "testsRun": result.testsRun,
                        "elapsedSeconds": elapsed})
    started.sort()
    skips.sort()
    timings.sort(key=lambda r: r["module"])
    full_coverage = (started == expected["testIds"]
                     and counts["testsRun"] == len(expected["testIds"]))
    expected_skips = skips == expected["declaredSkipIds"]
    ok = successful and full_coverage and expected_skips and not counts["expectedFailures"]
    return {"schema": "taxi.cloud-test-shard/1", "identity": plan["identity"],
            "planSHA256": plan["planSHA256"], "index": index,
            "status": "passed" if ok else "failed",
            "startedTestIds": started, "skippedTestIds": skips,
            **counts, "moduleTimings": timings,
            "elapsedSeconds": round(time.monotonic()-start, 6),
            "physicalQualification": False}


def verify_module_timings(receipt, assignment):
    """Check exact module coverage and bounded durations before profiling."""
    rows = receipt.get("moduleTimings")
    expected = assignment["moduleTestIds"]
    require(isinstance(rows, list) and len(rows) == len(expected),
            "module timing inventory incomplete")
    names = []
    for row in rows:
        require(isinstance(row, dict) and set(row) == {"module", "testsRun", "elapsedSeconds"},
                "invalid module timing row")
        name = row["module"]
        require(isinstance(name, str) and name in expected, "unexpected timed module")
        require(exact_int(row["testsRun"], len(expected[name]), len(expected[name])),
                "module timing coverage mismatch")
        elapsed = row["elapsedSeconds"]
        require(type(elapsed) in (int, float) and 0 <= elapsed <= 3600,
                "invalid module elapsed duration")
        names.append(name)
    require(names == sorted(expected), "duplicate or unordered timed modules")
    # Rounding each module to microseconds can exceed the rounded enclosing
    # duration by a few microseconds. Allow only that numerical slack.
    require(sum(r["elapsedSeconds"] for r in rows) <=
            receipt["elapsedSeconds"] + (len(rows)+1)*0.000001,
            "module timing exceeds enclosing shard")
    return rows


def merge(plan, receipts):
    """Require complete exact coverage and successful receipt for every shard.

    This establishes consistency of test results from the pinned checkout,
    not cryptographic authentication of a runner or physical game validation.
    """
    require(len(receipts) == plan["shardCount"], "missing or extra shard receipts")
    by_index = {}
    for r in receipts:
        require(isinstance(r, dict) and r.get("schema") == "taxi.cloud-test-shard/1"
                and r.get("identity") == plan["identity"]
                and r.get("planSHA256") == plan["planSHA256"]
                and r.get("physicalQualification") is False, "receipt identity mismatch")
        i = r.get("index")
        require(exact_int(i, 0, plan["shardCount"]-1) and i not in by_index,
                "duplicate or invalid shard index")
        e = plan["assignment"][i]
        require(r.get("status") == "passed" and r.get("startedTestIds") == e["testIds"]
                and r.get("skippedTestIds") == e["declaredSkipIds"]
                and exact_int(r.get("testsRun"), len(e["testIds"]), len(e["testIds"])),
                "shard failed, lost coverage, or changed skip inventory")
        require(all(exact_int(r.get(k), 0, 0) for k in
                    ("failures", "errors", "unexpectedSuccesses", "expectedFailures")),
                "shard contains nonpassing outcomes")
        elapsed = r.get("elapsedSeconds")
        require(type(elapsed) in (int,float) and 0 <= elapsed <= 3600,
                "invalid elapsed duration")
        verify_module_timings(r, e)
        by_index[i] = r
    ordered = [by_index[i] for i in range(plan["shardCount"])]
    tests = sum(r["testsRun"] for r in ordered)
    skipped = sum(len(r["skippedTestIds"]) for r in ordered)
    require(tests == plan["testCount"], "aggregate coverage mismatch")
    return {"schema": "taxi.cloud-test-merge/1", "status": "passed",
            "identity": plan["identity"], "planSHA256": plan["planSHA256"],
            "shardCount": plan["shardCount"], "testsDiscovered": tests,
            "balancingMode": plan["balancingMode"],
            "costProfileSHA256": plan.get("costProfileSHA256"),
            "costProfileSource": plan.get("costProfileSource"),
            "estimatedShardMicroseconds": plan.get("estimatedShardMicroseconds"),
            "testsPassed": tests-skipped, "testsSkipped": skipped,
            "allDiscoveredTestsAccountedFor": True,
            "sumShardSeconds": round(sum(r["elapsedSeconds"] for r in ordered), 6),
            "maxShardSeconds": max(r["elapsedSeconds"] for r in ordered),
            "moduleTimings": sorted((dict(m, shardIndex=r["index"]) for r in ordered
                                     for m in r["moduleTimings"]), key=lambda m: m["module"]),
            "shards": [{"index": r["index"], "testsRun": r["testsRun"],
                        "skips": len(r["skippedTestIds"]),
                        "elapsedSeconds": r["elapsedSeconds"]} for r in ordered],
            "physicalQualification": False}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")


def read(path):
    with path.open("rb") as f:
        raw = f.read(MAX_RECEIPT+1)
    require(len(raw)<=MAX_RECEIPT, "shard receipt too large")
    def unique(pairs):
        result = {}
        for k,v in pairs:
            require(k not in result, "duplicate receipt key")
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=unique)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for name in ("plan", "run", "merge"):
        p = sub.add_parser(name)
        p.add_argument("--shards", type=int, default=4)
        p.add_argument("--out", type=Path, required=True)
        if name == "run":
            p.add_argument("--index", type=int, required=True)
        if name == "merge":
            p.add_argument("--dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        require(not args.out.exists(), "output already exists")
        plan, tests = current_plan(args.shards)
        if args.operation == "plan":
            report = plan
        elif args.operation == "run":
            report = execute_shard(plan, tests, args.index)
        else:
            # Use a fixed inventory, not recursive arbitrary JSON discovery.
            paths = sorted(args.dir.glob("shard-*.json"))
            require({p.name for p in paths} ==
                    {f"shard-{i}.json" for i in range(args.shards)}, "shard receipt inventory mismatch")
            report = merge(plan, [read(p) for p in paths])
        write(args.out, report)
        print(json.dumps({k: v for k, v in report.items()
                          if k not in ("assignment", "startedTestIds", "skippedTestIds")},
                         sort_keys=True, allow_nan=False))
        return 0 if report.get("status", "passed") == "passed" else 1
    except (CloudValidationError, OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Cloud test validation refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
