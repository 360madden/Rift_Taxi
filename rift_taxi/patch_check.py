"""Repeatable, evidence-preserving Taxi offline patch check (development only).

The Update Helper remains responsible for capturing/verifying game files. This
module only reads saved manifests and runs fixed local Git, doctor and unittest
commands. No process/game access, input, network, checkout, or sibling imports.
A successful receipt is offline readiness, NEVER live-client compatibility.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

from .patch_readiness import assess, _read_saved_bytes, _unique_object, _reject_constant

REPO = Path(__file__).resolve().parent.parent
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
HEAD = re.compile(r"[0-9a-f]{40}\Z")
MAX_LOG_READ = 4 * 1024 * 1024


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def publish(path, raw):
    """Publish complete bytes exclusively; never truncate an earlier receipt.

    The temporary file is on the same volume. Hard-link publication either
    creates the final name or fails if it already exists. If interrupted before
    publication, the temporary file alone is not an accepted receipt.
    """
    tmp = path.with_name(path.name + ".pending")
    with tmp.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(tmp, path)
    finally:
        tmp.unlink()


def json_bytes(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def new_run(repo, run_id):
    """Allocate only a new, ignored Taxi artifact directory; refuse reparse roots."""
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("invalid run ID")
    parent = repo / "artifacts"
    parent.mkdir(exist_ok=True)
    info = parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("artifacts directory must be an ordinary local directory")
    folder = parent / ("patch-check-" + run_id)
    folder.mkdir()  # Existing names, including failed attempts, are never reused.
    return folder


def command(repo, folder, name, argv, timeout=30):
    """Execute a fixed offline command with separate durable stdout/stderr logs.

    No shell. A timeout kills the direct child via subprocess.run; tests must
    remain bounded and not launch detached processes. Output streams go to disk
    rather than an unbounded in-memory pipe. Return small logs for validation.
    """
    out, err = folder / (name + ".stdout.txt"), folder / (name + ".stderr.txt")
    with out.open("xb") as stdout, err.open("xb") as stderr:
        process = subprocess.run(argv, cwd=repo, stdin=subprocess.DEVNULL,
                                 stdout=stdout, stderr=stderr, timeout=timeout,
                                 shell=False, check=False)
    if max(out.stat().st_size, err.stat().st_size) > MAX_LOG_READ:
        raise ValueError(f"{name}: output too large; inspect preserved logs")
    stdout_raw, _ = _read_saved_bytes(out)
    stderr_raw, _ = _read_saved_bytes(err)
    if max(len(stdout_raw), len(stderr_raw)) > MAX_LOG_READ:
        raise ValueError(f"{name}: output too large; inspect preserved logs")
    receipt = {"exit_code": process.returncode, "stdout_sha256": digest(stdout_raw),
               "stderr_sha256": digest(stderr_raw), "argv": argv}
    publish(folder / (name + ".json"), json_bytes(receipt))
    if process.returncode != 0:
        raise ValueError(f"{name}: exit {process.returncode}; inspect preserved logs")
    return stdout_raw.decode("utf-8"), stderr_raw.decode("utf-8"), receipt


def git_identity(repo, folder, stage, runner=None):
    """Require a clean working tree in the intended checkout; no Git writes."""
    runner = runner or command
    git = ["git", "--no-optional-locks"]
    root, _, _ = runner(repo, folder, stage + "-root", git + ["rev-parse", "--show-toplevel"])
    if Path(root.strip()).resolve() != repo.resolve():
        raise ValueError("unexpected Git checkout root")
    head, _, _ = runner(repo, folder, stage + "-head", git + ["rev-parse", "HEAD"])
    head = head.strip()
    if not HEAD.fullmatch(head):
        raise ValueError("invalid Git HEAD")
    status, _, _ = runner(repo, folder, stage + "-status",
                           git + ["status", "--porcelain=v1", "--untracked-files=all"])
    if status.strip():
        raise ValueError("Taxi checkout is dirty; commit reviewed changes first")
    return head


def check_doctor(stdout):
    """Require the current offline/disarmed contract, not merely exit code zero."""
    try:
        obj = json.loads(stdout, object_pairs_hook=_unique_object,
                         parse_constant=_reject_constant)
    except RecursionError as exc:
        raise ValueError("doctor JSON nesting exceeds decoder limits") from exc
    if (not isinstance(obj, dict) or obj.get("schema") != "taxi.doctor/1"
            or obj.get("status") != "offline-replay-ready" or obj.get("runtime") != "stdlib"):
        raise ValueError("unexpected doctor contract")
    for key in ("gameInputEnabled", "nativeReaderImplemented",
                "publicZoneIdAndWorldInstanceQualified", "nativeCandidateQualifiedForMovement",
                "nativeZoneCandidateQualifiedForPublicApi", "siblingRepositoryRequired"):
        if obj.get(key) is not False:
            raise ValueError(f"doctor disarm/standalone gate failed: {key}")
    if not isinstance(obj.get("python"), str) or not obj["python"].strip():
        raise ValueError("doctor Python version missing")
    return obj


def check_tests(stderr, minimum_tests):
    """Reject empty, reduced, skipped or unsuccessful suites despite exit zero."""
    # A bare trailing OK must not hide an intervening FAILED/skipped summary.
    # The normal unittest footer is three lines: count, blank line, OK.
    lines = stderr.rstrip().splitlines()
    pattern = r"Ran (\d+) tests? in [0-9]+(?:\.[0-9]+)?s"
    counts = [m for line in lines if (m := re.fullmatch(pattern, line))]
    if (len(counts) != 1 or len(lines) < 3 or lines[-2:] != ["", "OK"]
            or not re.fullmatch(pattern, lines[-3])):
        raise ValueError("unittest receipt missing a complete unskipped OK result")
    count = int(counts[0][1])
    if count < minimum_tests:
        raise ValueError(f"only {count} tests; expected at least {minimum_tests}")
    return count


def preserve_inputs(folder, paths, hashes):
    """Copy only already-admitted saved bytes, checking each recorded digest.

    Small manifest copies make the receipt independently inspectable if another
    repository is unavailable. These are not new game-file captures. Originals
    remain untouched, and a later source change cannot rewrite the copied bytes.
    """
    copies = {}
    for name, path in paths.items():
        raw, _ = _read_saved_bytes(path)
        if digest(raw) != hashes[name]:
            raise ValueError(f"source manifest changed: {name}")
        dest = folder / (name + ".json")
        publish(dest, raw)
        copies[name] = dest
    return copies


def run(repo, run_id, expected_host, before, expected_before_sha, minimum_tests,
        after_a=None, after_b=None):
    """Run the offline evidence/diagnostics/test ladder and preserve failures.

    The host check is actual local execution identity, unlike the portable
    saved-evidence gate. Check source HEAD and cleanliness before and after the
    tests; this detects observable drift, not an atomic filesystem snapshot.
    """
    if socket.gethostname().upper() != expected_host:
        raise ValueError("wrong execution host")
    if type(minimum_tests) is not int or minimum_tests < 1:
        raise ValueError("positive minimum test count required")
    folder = new_run(repo, run_id)
    result = {"schema": "taxi.patch-check/2", "run_id": run_id, "host": expected_host,
              "started_utc": utc(), "status": "blocked", "production_input_authorized": False,
              "live_compatibility_verified": False, "stage": "source",
              "mode": "preflight" if after_a is None and after_b is None else "postcheck",
              "expected_before_sha256": expected_before_sha, "minimum_tests": minimum_tests}
    # V2 binds every required saved byte, including the previously unbound Git
    # logs. Capture each digest at admission, not by trusting a final directory
    # listing after diagnostics have run. Keep identities for local rechecks;
    # the portable receipt stores only hashes.
    observed = {}

    def track(name, expected):
        raw, identity = _read_saved_bytes(folder / name)
        if name in observed or digest(raw) != expected:
            raise ValueError(f"saved evidence mismatch: {name}")
        observed[name] = (expected, identity)

    def tracked_command(repo, folder, name, argv, timeout=30):
        out, err, meta = command(repo, folder, name, argv, timeout)
        track(name + ".json", digest(json_bytes(meta)))
        for stream, value in (("stdout", out), ("stderr", err)):
            expected = meta[stream + "_sha256"]
            if digest(value.encode("utf-8")) != expected:
                raise ValueError(f"command output mismatch: {name}.{stream}")
            track(f"{name}.{stream}.txt", expected)
        return out, err, meta

    try:
        head = git_identity(repo, folder, "start", runner=tracked_command)
        result["git_head"] = head
        result["stage"] = "evidence"
        evidence = assess(before, expected_host, expected_before_sha, after_a, after_b)
        paths = {"before": before}
        hashes = {"before": evidence["baseline_manifest_sha256"]}
        if after_a is not None:
            paths.update({"after-a": after_a, "after-b": after_b})
            hashes.update(zip(("after-a", "after-b"), evidence["after_manifest_sha256"]))
        result["manifest_sha256"] = hashes
        copies = preserve_inputs(folder, paths, hashes)
        for name, expected in hashes.items():
            track(name + ".json", expected)
        # Confirm the portable copy produces exactly the same gate result.
        def assess_copies():
            return assess(copies["before"], expected_host, expected_before_sha,
                          copies.get("after-a"), copies.get("after-b"))
        if assess_copies() != evidence:
            raise ValueError("copied evidence does not reproduce admission")
        publish(folder / "evidence.json", json_bytes(evidence))
        result["evidence_status"] = evidence["status"]
        result["evidence_report_sha256"] = digest(json_bytes(evidence))
        track("evidence.json", result["evidence_report_sha256"])

        result["stage"] = "doctor"
        python = [sys.executable, "-E", "-B", "-X", "utf8"]
        stdout, _, result["doctor_command"] = tracked_command(
            repo, folder, "doctor", python + ["-m", "rift_taxi", "doctor"])
        doctor = check_doctor(stdout)
        result["python"] = doctor["python"]

        result["stage"] = "tests"
        _, stderr, result["test_command"] = tracked_command(
            repo, folder, "tests", python + ["-m", "unittest", "discover", "-s", "tests", "-q"],
            timeout=300)
        result["test_count"] = check_tests(stderr, minimum_tests)

        result["stage"] = "final-recheck"
        if git_identity(repo, folder, "finish", runner=tracked_command) != head:
            raise ValueError("Git HEAD changed during validation")
        if assess(before, expected_host, expected_before_sha, after_a, after_b) != evidence:
            raise ValueError("original evidence changed during validation")
        if assess_copies() != evidence:
            raise ValueError("preserved evidence changed during validation")
        # Re-read all admitted artifacts immediately before publishing success.
        # A mutated log or command record must not acquire a fresh trusted hash.
        for name, expected in observed.items():
            raw, identity = _read_saved_bytes(folder / name)
            if (digest(raw), identity) != expected:
                raise ValueError(f"saved evidence changed during validation: {name}")
        result["file_sha256"] = {name: value[0] for name, value in observed.items()}
        result["stage"] = "complete"
        result["status"] = ("offline-preflight-passed" if after_a is None
                            else "offline-postcheck-passed")
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            subprocess.SubprocessError) as exc:
        result["error"] = str(exc)
    result["finished_utc"] = utc()
    publish(folder / "receipt.json", json_bytes(result))
    return result, folder


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--expected-before-sha", required=True)
    parser.add_argument("--minimum-tests", required=True, type=int)
    parser.add_argument("--after-a", type=Path)
    parser.add_argument("--after-b", type=Path)
    args = parser.parse_args(argv)
    try:
        result, folder = run(REPO, args.run_id, args.expected_host, args.before,
                             args.expected_before_sha, args.minimum_tests,
                             args.after_a, args.after_b)
    except (OSError, ValueError) as exc:
        print(f"PATCH CHECK BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"receipt": str(folder / "receipt.json"), **result}, indent=2))
    return 0 if result["stage"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
