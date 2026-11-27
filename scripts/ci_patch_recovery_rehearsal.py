"""Exercise the actual recovery CLIs on a Windows runner, with fake manifests.

Invocation from the repository root:
    python -B scripts/ci_patch_recovery_rehearsal.py --minimum-tests 556

This is a development-only synthetic workflow rehearsal. It runs the real
clean-checkout, doctor, full unskipped unittest and receipt-verification
commands. It never scans an installation, opens RIFT, or uses LEGION data.
The fictional inventory is generated outside the checkout; the recovery
bundle and clearly classified summary live in ignored artifacts/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "hosted-synthetic-rehearsal"
# Historical floor verified on Windows at acfd567; update only with explicit
# review when tests are intentionally added or retired. The dynamic inventory
# also catches a reduced execution even when it exceeds this floor.
VERIFIED_MINIMUM_TESTS = 694


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def manifest(path, *, host, phase, minute, executable):
    """Write one distinct synthetic capture, not a real scanner observation.

    Each invented file has the size and digest of literal test bytes. The
    fictional Windows root and synthetic marker make the scope explicit.
    """
    files = []
    for name, raw in (("rift_x64.exe", executable),
                      ("assets/fixture.dat", b"synthetic fixture asset")):
        files.append({"path": name, "size": len(raw),
                      "sha256": digest(raw), "mtime_ns": minute})
    data = {
        "schema": "update-helper.game-files.v1",
        "classification": "SYNTHETIC_CI_REHEARSAL_ONLY",
        "phase": phase, "host": host,
        "root": r"C:\TaxiSyntheticFixture\RIFT",
        "started_utc": f"2026-01-01T00:{minute:02}:00+00:00",
        "finished_utc": f"2026-01-01T00:{minute:02}:10+00:00",
        "complete": True, "file_count": len(files),
        "bytes": sum(row["size"] for row in files), "files": files,
    }
    raw = (json.dumps(data, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(raw)
    return digest(raw)


def invoke(module, args):
    """Invoke the public CLI, preserving failures and avoiding shell expansion."""
    cmd = [sys.executable, "-E", "-B", "-X", "utf8", "-m", module, *map(str, args)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", timeout=360)
    print(result.stdout, end="", flush=True)
    print(result.stderr, end="", file=sys.stderr, flush=True)
    result.check_returncode()
    return json.loads(result.stdout)


def admit_inventory(plan, minimum_tests):
    """Admit a single-shard, complete Windows discovery before execution.

    This reuses the exact checkout discovery tool rather than importing test
    modules into the rehearsal coordinator. The ordinary patch-check CLI
    still runs its unchanged serial unittest suite and retains its original
    evidence format. A discovered count is not proof of executed test IDs;
    the final exact count and independent receipt checks remain mandatory.
    """
    if type(minimum_tests) is not int or minimum_tests < 1:
        raise ValueError("positive minimum test count required")
    if not isinstance(plan, dict):
        raise ValueError("missing test inventory")
    claimed = plan.get("planSHA256")
    body = {k: v for k, v in plan.items() if k != "planSHA256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    identity = plan.get("identity")
    if (plan.get("schema") != "taxi.cloud-test-plan/1"
            or not isinstance(claimed, str) or claimed != digest(canonical)
            or not isinstance(identity, dict) or identity.get("cleanCheckout") is not True
            or identity.get("platform") != "Windows"
            or not isinstance(identity.get("commit"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", identity["commit"])
            or type(plan.get("shardCount")) is not int or plan["shardCount"] != 1):
        raise ValueError("invalid Windows discovery identity")
    count = plan.get("testCount")
    rows = plan.get("assignment")
    if (type(count) is not int or count < minimum_tests
            or not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict)):
        raise ValueError("reduced or invalid discovery inventory")
    row = rows[0]
    ids, groups = row.get("testIds"), row.get("moduleTestIds")
    if (type(row.get("index")) is not int or row["index"] != 0
            or row.get("declaredSkipIds") != [] or not isinstance(ids, list)
            or any(not isinstance(t, str) or not t for t in ids)
            or ids != sorted(set(ids)) or len(ids) != count
            or not isinstance(groups, dict) or not groups
            or type(plan.get("moduleCount")) is not int
            or plan["moduleCount"] != len(groups)
            or row.get("modules") != sorted(groups)):
        raise ValueError("incomplete or skipped Windows inventory")
    all_ids = []
    for group in groups.values():
        if (not isinstance(group, list) or not group
                or any(not isinstance(t, str) or not t for t in group)
                or group != sorted(set(group))):
            raise ValueError("malformed module inventory")
        all_ids.extend(group)
    if sorted(all_ids) != ids:
        raise ValueError("module inventory coverage mismatch")
    return {"testCount": count, "moduleCount": len(groups),
            "planSHA256": claimed, "commit": identity["commit"]}


def require_exact_result(inventory, produced, verified):
    """Refuse a run below OR above the exact discovery count, or a changed HEAD."""
    count, head = inventory["testCount"], inventory["commit"]
    for label, receipt in (("producer", produced), ("verifier", verified)):
        if (type(receipt.get("test_count")) is not int
                or receipt["test_count"] != count or receipt.get("git_head") != head):
            raise ValueError(f"{label} test count or checkout differs from discovery")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum-tests", required=True, type=int)
    args = parser.parse_args()
    # The existing recovery contract requires a full unskipped suite, which
    # is intentionally not available on Linux. Never weaken that contract.
    if sys.platform != "win32" or args.minimum_tests < 1:
        parser.error("Windows runner and positive minimum test count required")
    host = socket.gethostname().upper()
    bundle = ROOT / "artifacts" / ("patch-check-" + RUN_ID)
    floor = max(args.minimum_tests, VERIFIED_MINIMUM_TESTS)
    started = time.monotonic()
    phase_seconds = {}
    with tempfile.TemporaryDirectory(prefix="taxi-synthetic-patch-") as folder:
        folder = Path(folder)
        # Recompute inventory at the actual checked-out merge SHA. No test
        # execution here; the separate recovery subprocess runs the full suite.
        phase_start = time.monotonic()
        plan_path = folder / "test-plan.json"
        invoke("scripts.cloud_test_runner", [
            "plan", "--shards", 1, "--out", plan_path,
        ])
        inventory = admit_inventory(json.loads(plan_path.read_bytes()), floor)
        phase_seconds["discovery"] = round(time.monotonic() - phase_start, 6)
        exact_count = inventory["testCount"]
        before, a, b = [folder / (name + ".json") for name in ("before", "after-a", "after-b")]
        pin = manifest(before, host=host, phase="before", minute=0,
                       executable=b"synthetic pre-update executable")
        manifest(a, host=host, phase="after", minute=1,
                 executable=b"synthetic post-update executable")
        manifest(b, host=host, phase="after", minute=2,
                 executable=b"synthetic post-update executable")
        phase_start = time.monotonic()
        receipt = invoke("rift_taxi.patch_check", [
            "--run-id", RUN_ID, "--expected-host", host,
            "--before", before, "--expected-before-sha", pin,
            "--after-a", a, "--after-b", b, "--minimum-tests", exact_count,
        ])
        phase_seconds["recovery"] = round(time.monotonic() - phase_start, 6)
    # Pin the newly produced receipt before running a separate verifier.
    # This same-run pin checks producer/consumer integration, NOT external
    # historical provenance or authentication of the fake capture producer.
    receipt_pin = digest((bundle / "receipt.json").read_bytes())
    phase_start = time.monotonic()
    verified = invoke("rift_taxi.verify_patch_check", [
        "--bundle", bundle, "--expected-receipt-sha", receipt_pin,
        "--expected-host", host, "--expected-before-sha", pin,
        "--minimum-tests", exact_count,
    ])
    phase_seconds["independentVerification"] = round(time.monotonic() - phase_start, 6)
    require_exact_result(inventory, receipt, verified)
    if (receipt["status"] != "offline-postcheck-passed"
            or verified["status"] != "verified-stored-offline-receipt"
            or verified["evidence_status"] != "executable-changed"
            or verified["verified_file_count"] != 29
            or verified["test_count"] != receipt["test_count"]
            or verified["production_input_authorized"] is not False
            or verified["live_compatibility_verified"] is not False):
        raise RuntimeError("unexpected synthetic rehearsal result")
    summary = {"classification": "SYNTHETIC_CI_REHEARSAL_ONLY",
               "host": host, "git_head": verified["git_head"],
               "test_count": verified["test_count"], "receipt_sha256": receipt_pin,
               "discovered_test_count": exact_count, "discovered_module_count": inventory["moduleCount"],
               "test_plan_sha256": inventory["planSHA256"], "historical_test_floor": floor,
               "phase_seconds": phase_seconds,
               "elapsed_before_summary_seconds": round(time.monotonic()-started, 6),
               "verified_file_count": verified["verified_file_count"],
               "simulated_evidence_status": verified["evidence_status"],
               "production_input_authorized": False, "live_compatibility_verified": False}
    # Keep the summary adjacent to the original bundle, not inside its
    # immutable evidence file set. All files remain ignored by Git.
    path = bundle.parent / "hosted-synthetic-rehearsal-summary.json"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print((bundle / "tests.stderr.txt").read_text(encoding="utf-8"), end="")
    print("SYNTHETIC_RECOVERY_REHEARSAL", json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
