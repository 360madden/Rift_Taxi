"""Portable, read-only verification of a saved Taxi patch-check/1 or /2 bundle.

This development command requires independently retained SHA-256 pins for the
receipt and baseline, plus the original host and a minimum test count. It
recomputes admission from copied manifests and verifies the original diagnostic
logs; it never executes recorded argv, opens the game, or runs Git or tests.
A matching pinned receipt is evidence of saved-byte consistency, not proof that
the original commands ran honestly or that the current game is compatible.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat
import sys

from .patch_check import HEAD, RUN_ID, MAX_LOG_READ, check_doctor, check_tests, digest, json_bytes
from .patch_readiness import SHA, _read_saved_bytes, _unique_object, _reject_constant, _time, assess


def _object(raw):
    """Decode one strict UTF-8 JSON object; duplicates are evidence ambiguity."""
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant)
    except RecursionError as exc:
        raise ValueError("excessive JSON nesting") from exc
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _directory(path):
    """Reject symlinks and Windows reparse-point bundle directories."""
    info = path.lstat()
    _require(stat.S_ISDIR(info.st_mode)
             and not getattr(info, "st_file_attributes", 0) & 0x400,
             "bundle must be an ordinary directory")
    return info.st_dev, info.st_ino


def _hash_pin(pin):
    return isinstance(pin, str) and SHA.fullmatch(pin) is not None


def verify(folder, expected_receipt_sha, expected_host, expected_before_sha,
           minimum_tests):
    """Revalidate one completed v1 or v2 bundle on any host, using external pins.

    Fixed filenames only; no path or command from an untrusted receipt is
    executed or followed. The pinned final receipt binds the evidence, doctor,
    and test logs. V1 Git command records are only internally consistent, not
    individually bound by that receipt. V2 binds every required artifact.
    Rechecks detect observable file drift;
    they do not provide an atomic snapshot or authenticate the producer.
    """
    folder = Path(folder)
    _require(_hash_pin(expected_receipt_sha) and _hash_pin(expected_before_sha),
             "independent receipt and baseline SHA-256 pins required")
    _require(isinstance(expected_host, str) and bool(expected_host.strip())
             and expected_host == expected_host.strip(), "expected host required")
    _require(type(minimum_tests) is int and minimum_tests > 0,
             "positive minimum test count required")
    folder_identity = _directory(folder)
    observed = {}

    def read(name, limit=MAX_LOG_READ):
        # Shared bounded stable-byte reader rejects regular-file substitution
        # and reparse files. Remember each digest and identity for a final
        # recheck after assess() independently rereads the manifest copies.
        raw, identity = _read_saved_bytes(folder / name)
        _require(len(raw) <= limit, f"{name}: size limit exceeded")
        observed[name] = (digest(raw), identity)
        return raw

    raw = read("receipt.json")
    _require(digest(raw) == expected_receipt_sha, "receipt SHA-256 mismatch")
    receipt = _object(raw)
    mode = receipt.get("mode")
    _require(mode in ("preflight", "postcheck"), "invalid receipt mode")
    schema = receipt.get("schema")
    _require(schema in ("taxi.patch-check/1", "taxi.patch-check/2")
             and receipt.get("stage") == "complete"
             and receipt.get("status") == ("offline-preflight-passed" if mode == "preflight"
                                           else "offline-postcheck-passed")
             and "error" not in receipt, "receipt is not a completed successful check")
    run_id = receipt.get("run_id")
    _require(isinstance(run_id, str) and RUN_ID.fullmatch(run_id), "invalid run ID")
    _require(receipt.get("host") == expected_host
             and receipt.get("expected_before_sha256") == expected_before_sha,
             "receipt host or baseline pin mismatch")
    _require(receipt.get("production_input_authorized") is False
             and receipt.get("live_compatibility_verified") is False,
             "receipt improperly claims live qualification")
    head = receipt.get("git_head")
    _require(isinstance(head, str) and HEAD.fullmatch(head), "invalid Git HEAD")
    _require(_time(receipt.get("started_utc")) < _time(receipt.get("finished_utc")),
             "invalid receipt time interval")
    recorded_min = receipt.get("minimum_tests")
    _require(type(recorded_min) is int and recorded_min > 0, "invalid recorded test minimum")

    # Compare exact copied bytes, then independently recompute the admission.
    names = ("before",) if mode == "preflight" else ("before", "after-a", "after-b")
    hashes = {name: digest(read(name + ".json", 8 * 1024 * 1024)) for name in names}
    _require(hashes == receipt.get("manifest_sha256")
             and hashes["before"] == expected_before_sha, "manifest pin mismatch")
    evidence = assess(folder / "before.json", expected_host, expected_before_sha,
                      folder / "after-a.json" if mode == "postcheck" else None,
                      folder / "after-b.json" if mode == "postcheck" else None)
    # assess() may have seen different bytes; require its independently
    # computed manifest hashes to agree with our stable reads as well.
    computed = {"before": evidence["baseline_manifest_sha256"]}
    if mode == "postcheck":
        computed.update(zip(("after-a", "after-b"), evidence["after_manifest_sha256"]))
    _require(computed == hashes, "admission manifest mismatch")
    evidence_raw = read("evidence.json")
    _require(digest(evidence_raw) == receipt.get("evidence_report_sha256")
             and evidence_raw == json_bytes(evidence)
             and evidence["status"] == receipt.get("evidence_status"),
             "saved evidence report mismatch")

    def command(name, expected_argv, pinned=None):
        """Check the saved command record and both log hashes, never execute."""
        meta = _object(read(name + ".json"))
        _require(set(meta) == {"argv", "exit_code", "stdout_sha256", "stderr_sha256"}
                 and type(meta["exit_code"]) is int and meta["exit_code"] == 0
                 and meta["argv"] == expected_argv, f"{name}: command metadata mismatch")
        if pinned is not None:
            # Canonical JSON comparison distinguishes bool from int.
            _require(json_bytes(meta) == json_bytes(pinned), f"{name}: receipt command mismatch")
        logs = []
        for stream in ("stdout", "stderr"):
            data = read(f"{name}.{stream}.txt")
            _require(digest(data) == meta[stream + "_sha256"], f"{name}: {stream} hash mismatch")
            logs.append(data.decode("utf-8"))
        return tuple(logs)

    doctor_meta = receipt.get("doctor_command")
    _require(isinstance(doctor_meta, dict), "missing doctor command")
    argv = doctor_meta.get("argv")
    _require(isinstance(argv, list) and len(argv) == 8 and isinstance(argv[0], str)
             and bool(argv[0]), "invalid doctor argv")
    python = [argv[0], "-E", "-B", "-X", "utf8"]
    doctor_out, _ = command("doctor", python + ["-m", "rift_taxi", "doctor"], doctor_meta)
    _object(doctor_out.encode("utf-8"))
    doctor = check_doctor(doctor_out)
    _require(isinstance(doctor.get("python"), str) and bool(doctor["python"])
             and doctor["python"] == receipt.get("python"), "Python version mismatch")

    tests_meta = receipt.get("test_command")
    _require(isinstance(tests_meta, dict), "missing tests command")
    _, tests_err = command("tests", python + ["-m", "unittest", "discover", "-s", "tests", "-q"],
                           tests_meta)
    count = check_tests(tests_err, max(recorded_min, minimum_tests))
    _require(type(receipt.get("test_count")) is int and receipt["test_count"] == count,
             "test count mismatch")

    # Original checkout paths are text observations, not current-host paths.
    # Do not resolve or open them. V1 records support a consistency check only.
    roots = []
    for stage in ("start", "finish"):
        git = ["git", "--no-optional-locks"]
        root, _ = command(stage + "-root", git + ["rev-parse", "--show-toplevel"])
        git_head, _ = command(stage + "-head", git + ["rev-parse", "HEAD"])
        status, _ = command(stage + "-status", git + ["status", "--porcelain=v1", "--untracked-files=all"])
        roots.append(root.strip())
        _require(git_head.strip() == head and not status.strip(), f"{stage}: Git identity mismatch")
    _require(bool(roots[0]) and roots[0] == roots[1], "Git root mismatch")

    # New receipts explicitly bind every required file except receipt.json
    # itself (which is independently pinned). Match the exact filename set:
    # never accept omitted hashes or open arbitrary receipt-supplied paths.
    if schema == "taxi.patch-check/2":
        expected_files = {name: value[0] for name, value in observed.items()
                          if name != "receipt.json"}
        _require(receipt.get("file_sha256") == expected_files,
                 "V2 bound artifact hash or filename set mismatch")

    # Detect evidence replacement or mutation during verification. This does
    # not protect against an adversary restoring all bytes/metadata in between.
    for name, expected in observed.items():
        data, identity = _read_saved_bytes(folder / name)
        _require((digest(data), identity) == expected, f"{name}: changed during verification")
    _require(_directory(folder) == folder_identity, "bundle directory changed")
    return {"schema": "taxi.patch-check-verification/1",
            "status": "verified-stored-offline-receipt", "host": expected_host,
            "run_id": run_id, "mode": mode, "git_head": head, "test_count": count,
            "evidence_status": evidence["status"], "receipt_sha256": expected_receipt_sha,
            "manifest_sha256": hashes, "verified_file_count": len(observed),
            "receipt_schema": schema,
            "git_logs_internally_consistent_only": schema == "taxi.patch-check/1",
            "production_input_authorized": False, "live_compatibility_verified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--expected-receipt-sha", required=True)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--expected-before-sha", required=True)
    parser.add_argument("--minimum-tests", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        report = verify(args.bundle, args.expected_receipt_sha, args.expected_host,
                        args.expected_before_sha, args.minimum_tests)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        print(f"PATCH RECEIPT BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
