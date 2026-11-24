"""Regression coverage for the offline patch-check receipt workflow.

Synthetic manifests and mocked command results deliberately avoid invoking a
nested unittest suite or touching a real game. The actual LEGION preflight is a
separate operational check. Failure cases protect receipt and provenance gates.
"""
import hashlib
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from rift_taxi import patch_check as p


class PatchCheckTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.host = socket.gethostname().upper()
        self.before = self.snapshot("before", "before", 0)
        self.pin = hashlib.sha256(self.before.read_bytes()).hexdigest()
        self.doctor = {"schema": "taxi.doctor/1", "status": "offline-replay-ready",
                       "runtime": "stdlib", "python": "3.14.10"}
        for key in ("gameInputEnabled", "nativeReaderImplemented",
                    "publicZoneIdAndWorldInstanceQualified", "nativeCandidateQualifiedForMovement",
                    "nativeZoneCandidateQualifiedForPublicApi", "siblingRepositoryRequired"):
            self.doctor[key] = False

    def snapshot(self, name, phase, minute, exe="a"):
        # Different capture intervals and file identities model saved evidence,
        # not actual scans. Unchanged content can still have different mtimes.
        data = {"schema": "update-helper.game-files.v1", "phase": phase,
                "host": self.host, "root": r"C:\Glyph\RIFT",
                "started_utc": f"2026-11-24T10:{minute:02}:00+00:00",
                "finished_utc": f"2026-11-24T10:{minute:02}:20+00:00",
                "complete": True, "file_count": 1, "bytes": 10,
                "files": [{"path": "rift_x64.exe", "size": 10, "sha256": exe * 64,
                           "mtime_ns": minute}]}
        path = self.repo / (name + ".json")
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def fake_command(self, repo, folder, name, argv, timeout=30):
        # Simulate only known diagnostic commands; unexpected dispatch is a bug.
        if name == "doctor":
            return json.dumps(self.doctor), "", {"exit_code": 0}
        if name == "tests":
            return "", "Ran 457 tests in 55.0s\n\nOK\n", {"exit_code": 0}
        raise AssertionError(f"unexpected command: {name}")

    def run_mocked(self, run_id, after_a=None, after_b=None, heads=None,
                   runner=None, minimum=457):
        with mock.patch.object(p, "git_identity", side_effect=heads or ["a" * 40] * 2), \
                mock.patch.object(p, "command", side_effect=runner or self.fake_command) as cmd:
            result, folder = p.run(self.repo, run_id, self.host, self.before,
                                   self.pin, minimum, after_a, after_b)
        return result, folder, cmd

    def test_preflight_preserves_original_bytes_and_disarm(self):
        result, folder, cmd = self.run_mocked("before")
        self.assertEqual(result["status"], "offline-preflight-passed")
        self.assertFalse(result["production_input_authorized"])
        self.assertFalse(result["live_compatibility_verified"])
        self.assertEqual(result["test_count"], 457)
        self.assertEqual((folder / "before.json").read_bytes(), self.before.read_bytes())
        self.assertEqual(json.loads((folder / "receipt.json").read_bytes()), result)
        self.assertEqual(cmd.call_count, 2)

    def test_postcheck_reports_changed_executable_without_live_claim(self):
        a, b = self.snapshot("a", "after", 1, "b"), self.snapshot("b", "after", 2, "b")
        result, folder, _ = self.run_mocked("post", a, b)
        self.assertEqual(result["status"], "offline-postcheck-passed")
        self.assertEqual(result["evidence_status"], "executable-changed")
        self.assertFalse(result["live_compatibility_verified"])
        self.assertEqual((folder / "after-a.json").read_bytes(), a.read_bytes())
        self.assertEqual((folder / "after-b.json").read_bytes(), b.read_bytes())

    def test_unstable_evidence_blocks_before_doctor(self):
        a, b = self.snapshot("a", "after", 1), self.snapshot("b", "after", 2, "b")
        result, folder, cmd = self.run_mocked("unstable", a, b)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "evidence")
        self.assertTrue((folder / "receipt.json").is_file())
        cmd.assert_not_called()

    def test_changed_head_and_changed_source_block_final_receipt(self):
        result, _, _ = self.run_mocked("head-drift", heads=["a" * 40, "b" * 40])
        self.assertEqual(result["stage"], "final-recheck")
        self.assertEqual(result["status"], "blocked")
        def modify_source(repo, folder, name, argv, timeout=30):
            if name == "tests":
                self.before.write_bytes(self.before.read_bytes() + b" ")
            return self.fake_command(repo, folder, name, argv, timeout)
        result, folder, _ = self.run_mocked("source-drift", runner=modify_source)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "final-recheck")
        self.assertEqual(hashlib.sha256((folder / "before.json").read_bytes()).hexdigest(),
                         self.pin)

    def test_doctor_true_missing_or_numeric_flag_refused(self):
        for value in (True, None, 0):
            with self.subTest(value=value):
                self.doctor["gameInputEnabled"] = value
                with self.assertRaisesRegex(ValueError, "disarm"):
                    p.check_doctor(json.dumps(self.doctor))
        self.doctor.pop("gameInputEnabled")
        result, _, cmd = self.run_mocked("doctor-fail")
        self.assertEqual(result["stage"], "doctor")
        self.assertEqual(cmd.call_count, 1)

    def test_incomplete_skipped_and_shrunken_suites_refused(self):
        for log in ("", "Ran 0 tests in 0.0s\n\nOK\n",
                    "Ran 457 tests in 1.0s\n\nOK (skipped=1)\n",
                    "Ran 457 tests in 1.0s\n\nFAILED\n"):
            with self.subTest(log=log):
                with self.assertRaises(ValueError):
                    p.check_tests(log, 457)
        result, _, _ = self.run_mocked("minimum", minimum=458)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "tests")

    def test_duplicate_run_and_wrong_host_refused_without_overwrite(self):
        result, folder, _ = self.run_mocked("duplicate")
        original = (folder / "receipt.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.run_mocked("duplicate")
        self.assertEqual((folder / "receipt.json").read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "wrong execution host"):
            p.run(self.repo, "wrong-host", self.host + "-OTHER", self.before, self.pin, 457)
        self.assertFalse((self.repo / "artifacts" / "patch-check-wrong-host").exists())

    def test_atomic_publication_never_overwrites_prior_receipt(self):
        path = self.repo / "receipt.json"
        p.publish(path, b"first")
        with self.assertRaises(FileExistsError):
            p.publish(path, b"second")
        self.assertEqual(path.read_bytes(), b"first")

    def test_git_identity_dirty_tree_refused(self):
        root = str(self.repo)
        replies = [(root, "", {}), ("a" * 40, "", {}), (" M modified.py\n", "", {})]
        with mock.patch.object(p, "command", side_effect=replies):
            with self.assertRaisesRegex(ValueError, "dirty"):
                p.git_identity(self.repo, self.repo, "start")
