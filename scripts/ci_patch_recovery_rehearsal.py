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
import socket
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "hosted-synthetic-rehearsal"


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
    with tempfile.TemporaryDirectory(prefix="taxi-synthetic-patch-") as folder:
        folder = Path(folder)
        before, a, b = [folder / (name + ".json") for name in ("before", "after-a", "after-b")]
        pin = manifest(before, host=host, phase="before", minute=0,
                       executable=b"synthetic pre-update executable")
        manifest(a, host=host, phase="after", minute=1,
                 executable=b"synthetic post-update executable")
        manifest(b, host=host, phase="after", minute=2,
                 executable=b"synthetic post-update executable")
        receipt = invoke("rift_taxi.patch_check", [
            "--run-id", RUN_ID, "--expected-host", host,
            "--before", before, "--expected-before-sha", pin,
            "--after-a", a, "--after-b", b, "--minimum-tests", args.minimum_tests,
        ])
    # Pin the newly produced receipt before running a separate verifier.
    # This same-run pin checks producer/consumer integration, NOT external
    # historical provenance or authentication of the fake capture producer.
    receipt_pin = digest((bundle / "receipt.json").read_bytes())
    verified = invoke("rift_taxi.verify_patch_check", [
        "--bundle", bundle, "--expected-receipt-sha", receipt_pin,
        "--expected-host", host, "--expected-before-sha", pin,
        "--minimum-tests", args.minimum_tests,
    ])
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
