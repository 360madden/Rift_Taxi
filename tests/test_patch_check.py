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
        # Simulate the actual producer's command artifacts, without running Git,
        # invoking a nested suite, or reading the game. The real tracking logic
        # must verify these bytes rather than treating mocks as trusted metadata.
        out, err = "", ""
        if name == "doctor":
            out = json.dumps(self.doctor)
        elif name == "tests":
            err = "Ran 457 tests in 55.0s\n\nOK\n"
        elif name in ("start-root", "finish-root"):
            out = str(repo) + "\n"
        elif name in ("start-head", "finish-head"):
            out = self.heads[0 if name.startswith("start") else 1] + "\n"
        elif name not in ("start-status", "finish-status"):
            raise AssertionError(f"unexpected command: {name}")
        meta = {"exit_code": 0, "argv": argv,
                "stdout_sha256": p.digest(out.encode("utf-8")),
                "stderr_sha256": p.digest(err.encode("utf-8"))}
        p.publish(folder / (name + ".stdout.txt"), out.encode("utf-8"))
        p.publish(folder / (name + ".stderr.txt"), err.encode("utf-8"))
        p.publish(folder / (name + ".json"), p.json_bytes(meta))
        return out, err, meta

    def run_mocked(self, run_id, after_a=None, after_b=None, heads=None,
                   runner=None, minimum=457):
        self.heads = heads or ["a" * 40] * 2
        with mock.patch.object(p, "command", side_effect=runner or self.fake_command) as cmd:
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
        self.assertEqual(cmd.call_count, 8)
        self.assertEqual(result["schema"], "taxi.patch-check/2")
        self.assertEqual(len(result["file_sha256"]), 26)
        for name, expected in result["file_sha256"].items():
            self.assertEqual(p.digest((folder / name).read_bytes()), expected)

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
        self.assertEqual(cmd.call_count, 3)  # Start Git identity only.

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
        self.assertEqual(cmd.call_count, 4)  # Start Git identity plus doctor.

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

    def test_mutated_earlier_command_log_blocks_publication(self):
        def modify_log(repo, folder, name, argv, timeout=30):
            if name == "tests":
                (folder / "start-status.stdout.txt").write_bytes(b"modified")
            return self.fake_command(repo, folder, name, argv, timeout)
        result, folder, _ = self.run_mocked("log-drift", runner=modify_log)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["stage"], "final-recheck")
        self.assertIn("saved evidence changed", result["error"])
        self.assertNotIn("file_sha256", result)

    def test_mutated_evidence_report_blocks_publication(self):
        def modify_report(repo, folder, name, argv, timeout=30):
            if name == "tests":
                (folder / "evidence.json").write_bytes(b"{}")
            return self.fake_command(repo, folder, name, argv, timeout)
        result, _, _ = self.run_mocked("report-drift", runner=modify_report)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("saved evidence changed", result["error"])

    def test_strict_doctor_and_unittest_footer(self):
        raw = json.dumps(self.doctor)
        ambiguous = raw[:-1] + ', "gameInputEnabled": false}'
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            p.check_doctor(ambiguous)
        self.doctor["python"] = ""
        with self.assertRaisesRegex(ValueError, "Python version missing"):
            p.check_doctor(json.dumps(self.doctor))
        with self.assertRaisesRegex(ValueError, "complete unskipped OK"):
            p.check_tests("Ran 457 tests in 1.0s\n\nFAILED\nOK\n", 457)

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
