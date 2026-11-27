"""Portable, single-host parallel offline regression orchestration.

Development-only Python stdlib wrapper around cloud_test_runner. Runs the
existing exact-coverage planner, whole-module shards, and merger in isolated
Python subprocesses, on a clean checkout. It needs neither GitHub Actions
workflow-write permission nor a physical game PC. It is suitable for a
temporary cloud VM, a container with a full checkout, or a developer PC.

Each run creates a NEW output directory, records a unique batch identity,
bounded process outcomes and individual logs, and preserves failed evidence.
No game input, native live read, cloud deployment, or sibling dependency.
A subprocess timeout is not a guarantee that every descendant has exited.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from scripts.cloud_test_runner import (
    ROOT, MAX_SHARDS, CloudValidationError, checkout_identity,
    exact_int, read, require, write,
)


def _command(args, log, env, timeout):
    """Run one bounded direct child, preserving its log even on failure.

    No shell, retries, or arbitrary executable selection. A timed-out direct
    child is handled by subprocess.run; descendants are not claimed settled.
    """
    started = time.monotonic()
    outcome = {"status": "failed", "exitCode": None}
    with log.open("xb") as stream:
        try:
            result = subprocess.run(
                [sys.executable, "-B", "-m", "scripts.cloud_test_runner", *args],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            )
            outcome["exitCode"] = result.returncode
            outcome["status"] = "passed" if result.returncode == 0 else "failed"
        except subprocess.TimeoutExpired:
            outcome["status"] = "timeout-direct-child"
        except OSError:
            outcome["status"] = "launch-failed"
    outcome["elapsedSeconds"] = round(time.monotonic() - started, 6)
    outcome["log"] = log.name
    return outcome


def run_batch(out_dir, *, shards=4, workers=4, timeout_seconds=300):
    """Run one bounded clean-checkout batch; never merge partial results.

    The unique batch ID, OS, Python, commit and optional GitHub run/attempt
    travel in every shard's plan identity. A separate merge subprocess
    recomputes discovery instead of trusting a list returned by workers.
    Worker concurrency and summed child durations are recorded separately
    from elapsed wall time; they are not CPU or billing measurements.
    """
    require(exact_int(shards, 1, MAX_SHARDS), "shards must be 1..8")
    require(exact_int(workers, 1, shards), "workers must be 1..shards")
    require(exact_int(timeout_seconds, 10, 3600), "timeout must be 10..3600 seconds")
    initial = checkout_identity()
    require(initial["cleanCheckout"] is True, "parallel batch requires a clean checkout")
    out_dir = Path(out_dir).absolute()
    require(not out_dir.exists() and not out_dir.is_symlink(), "output directory already exists")
    out_dir.mkdir(parents=True, exist_ok=False)

    env = os.environ.copy()
    batch_id = uuid.uuid4().hex
    env["RIFT_TAXI_CLOUD_BATCH_ID"] = batch_id
    common = ["--shards", str(shards)]
    started = time.monotonic()
    report = {"schema": "taxi.cloud-parallel-batch/1", "status": "failed",
              "batchId": batch_id, "commit": initial["commit"],
              "shardCount": shards, "maxWorkers": workers,
              "timeoutSecondsPerCommand": timeout_seconds, "plan": None,
              "shards": [], "merge": None, "aggregate": None,
              "physicalQualification": False, "gameInputSent": False}
    try:
        plan_path = out_dir / "plan.json"
        report["plan"] = _command(
            ["plan", *common, "--out", str(plan_path)],
            out_dir / "plan.log", env, min(timeout_seconds, 60),
        )
        if report["plan"]["status"] != "passed":
            return report
        plan = read(plan_path)
        expected = {**initial, "batchId": batch_id}
        require(plan.get("identity") == expected, "plan identity changed after batch admission")
        report["planSHA256"] = plan["planSHA256"]
        report["identity"] = expected

        def run_one(index):
            path = out_dir / f"shard-{index}.json"
            outcome = _command(
                ["run", *common, "--index", str(index), "--out", str(path)],
                out_dir / f"shard-{index}.log", env, timeout_seconds,
            )
            return {"index": index, **outcome}

        # Each module belongs to exactly one shard. No shared interpreter or
        # in-process test fixture state is used across workers.
        shard_started = time.monotonic()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            report["shards"] = list(pool.map(run_one, range(shards)))
        report["shardWallSeconds"] = round(time.monotonic() - shard_started, 6)
        if any(r["status"] != "passed" for r in report["shards"]):
            return report

        aggregate_path = out_dir / "merged.json"
        report["merge"] = _command(
            ["merge", *common, "--dir", str(out_dir), "--out", str(aggregate_path)],
            out_dir / "merge.log", env, min(timeout_seconds, 60),
        )
        if report["merge"]["status"] != "passed":
            return report
        aggregate = read(aggregate_path)
        require(aggregate.get("schema") == "taxi.cloud-test-merge/1"
                and aggregate.get("status") == "passed"
                and aggregate.get("identity") == expected
                and aggregate.get("planSHA256") == report["planSHA256"]
                and aggregate.get("physicalQualification") is False
                and aggregate.get("allDiscoveredTestsAccountedFor") is True,
                "aggregate identity or coverage mismatch")
        report["aggregate"] = aggregate
        report["status"] = "passed"
        return report
    except (CloudValidationError, OSError, ValueError, KeyError, TypeError) as exc:
        # Preserve the failed batch and its logs; do not fabricate successful
        # coverage from a child that died, timed out, or emitted bad data.
        report["failureType"] = type(exc).__name__
        return report
    finally:
        report["wallSeconds"] = round(time.monotonic() - started, 6)
        report["sumShardProcessSeconds"] = round(
            sum(r["elapsedSeconds"] for r in report["shards"]), 6)
        write(out_dir / "batch.json", report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--shards", type=int, default=4)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args(argv)
    try:
        workers = min(args.shards, 4) if args.workers is None else args.workers
        report = run_batch(args.out_dir, shards=args.shards, workers=workers,
                           timeout_seconds=args.timeout_seconds)
        # Logs are explicit local artifacts, not automatically uploaded.
        print(json.dumps({k: v for k, v in report.items()
                          if k != "aggregate"}, sort_keys=True, allow_nan=False))
        return 0 if report["status"] == "passed" else 1
    except (CloudValidationError, OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Portable cloud batch refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
