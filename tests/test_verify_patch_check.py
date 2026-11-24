"""Offline verifier tests using generated, disposable evidence bundles.

The synthetic files model the v1 producer format, not actual RIFT scans.
Mutation tests intentionally repin some altered receipts to exercise semantic
checks independently of the external SHA-256 check.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from rift_taxi import patch_check as p
from rift_taxi import patch_readiness as readiness
from rift_taxi import verify_patch_check as v


class VerifyPatchCheckTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name) / "bundle"
        self.folder.mkdir()
        self.host = "LEGION"
        self.head = "a" * 40
        self.python = [r"C:\Python\python.exe", "-E", "-B", "-X", "utf8"]

    def write(self, name, data):
        if isinstance(data, dict):
            data = p.json_bytes(data)
        elif isinstance(data, str):
            data = data.encode("utf-8")
        (self.folder / name).write_bytes(data)
        return p.digest(data)

    def manifest(self, name, phase, minute):
        return self.write(name + ".json", {
            "schema": readiness.SCHEMA, "host": self.host, "phase": phase,
            "root": r"C:\Glyph\RIFT", "complete": True,
            "started_utc": f"2026-11-24T10:{minute:02}:00+00:00",
            "finished_utc": f"2026-11-24T10:{minute:02}:20+00:00",
            "file_count": 1, "bytes": 10,
            "files": [{"path": "rift_x64.exe", "size": 10,
                       "sha256": "b" * 64, "mtime_ns": minute}],
        })

    def command(self, name, argv, out="", err=""):
        meta = {"argv": argv, "exit_code": 0,
                "stdout_sha256": self.write(name + ".stdout.txt", out),
                "stderr_sha256": self.write(name + ".stderr.txt", err)}
        self.write(name + ".json", meta)
        return meta

    def make_bundle(self, post=True):
        self.before = self.manifest("before", "before", 0)
        hashes = {"before": self.before}
        if post:
            hashes["after-a"] = self.manifest("after-a", "after", 1)
            hashes["after-b"] = self.manifest("after-b", "after", 2)
        evidence = readiness.assess(
            self.folder / "before.json", self.host, self.before,
            self.folder / "after-a.json" if post else None,
            self.folder / "after-b.json" if post else None)
        doctor = {"schema": "taxi.doctor/1", "status": "offline-replay-ready",
                  "runtime": "stdlib", "python": "3.14.10"}
        for key in ("gameInputEnabled", "nativeReaderImplemented",
                    "publicZoneIdAndWorldInstanceQualified", "nativeCandidateQualifiedForMovement",
                    "nativeZoneCandidateQualifiedForPublicApi", "siblingRepositoryRequired"):
            doctor[key] = False
        doctor_meta = self.command("doctor", self.python + ["-m", "rift_taxi", "doctor"],
                                   json.dumps(doctor))
        tests_meta = self.command("tests", self.python + ["-m", "unittest", "discover",
                                  "-s", "tests", "-q"], err="Ran 466 tests in 1.0s\n\nOK\n")
        for stage in ("start", "finish"):
            git = ["git", "--no-optional-locks"]
            self.command(stage + "-root", git + ["rev-parse", "--show-toplevel"],
                         "C:/work/Rift_Taxi\n")
            self.command(stage + "-head", git + ["rev-parse", "HEAD"], self.head + "\n")
            self.command(stage + "-status", git + ["status", "--porcelain=v1", "--untracked-files=all"])
        self.receipt = {
            "schema": "taxi.patch-check/1", "run_id": "synthetic-01", "host": self.host,
            "started_utc": "2026-11-24T11:00:00+00:00",
            "finished_utc": "2026-11-24T11:01:00+00:00",
            "stage": "complete", "mode": "postcheck" if post else "preflight",
            "status": "offline-postcheck-passed" if post else "offline-preflight-passed",
            "production_input_authorized": False, "live_compatibility_verified": False,
            "expected_before_sha256": self.before, "minimum_tests": 466, "git_head": self.head,
            "manifest_sha256": hashes, "evidence_status": evidence["status"],
            "evidence_report_sha256": self.write("evidence.json", evidence),
            "doctor_command": doctor_meta, "test_command": tests_meta,
            "python": "3.14.10", "test_count": 466}
        self.repin()

    def repin(self):
        self.pin = self.write("receipt.json", self.receipt)

    def verify(self, **kwargs):
        args = dict(expected_receipt_sha=self.pin, expected_host=self.host,
                    expected_before_sha=self.before, minimum_tests=466)
        args.update(kwargs)
        return v.verify(self.folder, **args)

    def test_postcheck_portable_and_no_command_execution(self):
        self.make_bundle()
        # Verifying historical Windows paths must not access the game or run
        # the recorded argv, even when the receipt is copied to another host.
        with mock.patch("subprocess.run", side_effect=AssertionError("no execution")):
            result = self.verify()
        self.assertEqual(result["verified_file_count"], 29)
        self.assertEqual(result["test_count"], 466)
        self.assertEqual(result["evidence_status"], "no-content-change")
        self.assertFalse(result["production_input_authorized"])
        self.assertFalse(result["live_compatibility_verified"])

    def make_v2(self):
        # Bind the required saved bytes, excluding the separately pinned receipt.
        self.receipt["schema"] = "taxi.patch-check/2"
        self.receipt["file_sha256"] = {
            path.name: p.digest(path.read_bytes()) for path in self.folder.iterdir()
            if path.name != "receipt.json"}
        self.repin()

    def test_v2_binds_all_artifacts(self):
        self.make_bundle()
        self.make_v2()
        report = self.verify()
        self.assertEqual(report["receipt_schema"], "taxi.patch-check/2")
        self.assertFalse(report["git_logs_internally_consistent_only"])
        self.assertEqual(len(self.receipt["file_sha256"]), 28)

    def test_v2_rejects_self_consistent_rewritten_git_logs(self):
        self.make_bundle()
        self.make_v2()
        # Both Git roots are internally consistent but do not match the pin.
        for stage in ("start", "finish"):
            self.command(stage + "-root", ["git", "--no-optional-locks",
                         "rev-parse", "--show-toplevel"], "C:/other/checkout\n")
        with self.assertRaisesRegex(ValueError, "V2 bound artifact"):
            self.verify()

    def test_v2_missing_or_extra_hash_keys_rejected(self):
        self.make_bundle()
        self.make_v2()
        original = dict(self.receipt["file_sha256"])
        for changed in ({k: v for k, v in original.items() if k != "start-head.json"},
                        {**original, "../outside": "a" * 64}):
            self.receipt["file_sha256"] = changed
            self.repin()
            with self.assertRaisesRegex(ValueError, "V2 bound artifact"):
                self.verify()

    def test_preflight_bundle(self):
        self.make_bundle(post=False)
        result = self.verify()
        self.assertEqual(result["verified_file_count"], 27)
        self.assertEqual(result["evidence_status"], "baseline-only")

    def test_receipt_pin_must_match(self):
        self.make_bundle()
        with self.assertRaisesRegex(ValueError, "receipt SHA-256 mismatch"):
            self.verify(expected_receipt_sha="f" * 64)

    def test_external_host_and_baseline_pins(self):
        self.make_bundle()
        for args in ({"expected_host": "AMD-DESKTOP"}, {"expected_before_sha": "c" * 64}):
            with self.subTest(args=args), self.assertRaisesRegex(ValueError, "host or baseline"):
                self.verify(**args)

    def test_external_minimum_cannot_be_lowered_by_receipt(self):
        self.make_bundle()
        with self.assertRaisesRegex(ValueError, "expected at least 467"):
            self.verify(minimum_tests=467)

    def test_changed_manifest_bytes_block(self):
        self.make_bundle()
        path = self.folder / "after-b.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "manifest pin mismatch"):
            self.verify()

    def test_recomputed_evidence_must_match_even_if_repinned(self):
        self.make_bundle()
        data = json.loads((self.folder / "evidence.json").read_bytes())
        data["status"] = "executable-changed"
        self.receipt["evidence_status"] = data["status"]
        self.receipt["evidence_report_sha256"] = self.write("evidence.json", data)
        self.repin()
        with self.assertRaisesRegex(ValueError, "saved evidence report mismatch"):
            self.verify()

    def test_tampered_log_blocks(self):
        self.make_bundle()
        self.write("tests.stderr.txt", "Ran 999 tests in 1.0s\n\nOK\n")
        with self.assertRaisesRegex(ValueError, "tests: stderr hash mismatch"):
            self.verify()

    def test_repinned_skipped_suite_still_blocks(self):
        self.make_bundle()
        self.receipt["test_command"] = self.command(
            "tests", self.receipt["test_command"]["argv"],
            err="Ran 466 tests in 1.0s\n\nOK (skipped=1)\n")
        self.repin()
        with self.assertRaisesRegex(ValueError, "complete unskipped OK"):
            self.verify()

    def test_rejected_command_substitution_even_if_repinned(self):
        self.make_bundle()
        self.receipt["doctor_command"] = self.command(
            "doctor", self.python + ["-m", "rift_taxi", "anything"])
        self.repin()
        with self.assertRaisesRegex(ValueError, "doctor: command metadata mismatch"):
            self.verify()

    def test_blocked_or_live_receipt_rejected(self):
        self.make_bundle()
        self.receipt["status"] = "blocked"
        self.repin()
        with self.assertRaisesRegex(ValueError, "not a completed"):
            self.verify()
        self.receipt["status"] = "offline-postcheck-passed"
        self.receipt["production_input_authorized"] = True
        self.repin()
        with self.assertRaisesRegex(ValueError, "improperly claims"):
            self.verify()

    def test_git_drift_blocks_even_with_consistent_local_log_hash(self):
        self.make_bundle()
        self.command("finish-head", ["git", "--no-optional-locks", "rev-parse", "HEAD"],
                     "c" * 40 + "\n")
        with self.assertRaisesRegex(ValueError, "finish: Git identity mismatch"):
            self.verify()

    def test_duplicate_receipt_key_rejected(self):
        self.make_bundle()
        raw = (self.folder / "receipt.json").read_bytes().rstrip()
        raw = raw[:-1] + b', "stage":"complete"}'
        self.pin = self.write("receipt.json", raw)
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.verify()

    def test_missing_log_cli_refuses_with_exit_two(self):
        self.make_bundle()
        (self.folder / "doctor.stdout.txt").unlink()
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = v.main(["--bundle", str(self.folder),
                           "--expected-receipt-sha", self.pin, "--expected-host", self.host,
                           "--expected-before-sha", self.before, "--minimum-tests", "466"])
        self.assertEqual(code, 2)
        self.assertIn("PATCH RECEIPT BLOCKED", err.getvalue())

    def test_replacement_during_verification_rejected(self):
        self.make_bundle()
        original = v.check_tests

        def change_log(stderr, minimum):
            # Mutation occurs after the doctor log was admitted. Its retained
            # digest must still be verified before returning any success.
            self.write("doctor.stdout.txt", "{}")
            return original(stderr, minimum)

        with mock.patch.object(v, "check_tests", side_effect=change_log):
            with self.assertRaisesRegex(ValueError, "changed during verification"):
                self.verify()
