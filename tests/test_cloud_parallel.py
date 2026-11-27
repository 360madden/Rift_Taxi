"""Real subprocess/Git integration for portable cloud validation.

Each test uses a tiny disposable synthetic checkout, not the real full test
suite recursively, not a RIFT client, and not a physical keyboard. The
fixture launches the same runner/orchestrator code used by real developers.
This exercises both Linux and Windows hosted PR checks without a new workflow.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts import cloud_test_runner

SOURCE_ROOT = Path(__file__).resolve().parents[1]


class PortableBatchIntegration(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        (self.repo / "scripts").mkdir()
        (self.repo / "tests").mkdir()
        for name in ("cloud_test_runner.py", "cloud_parallel.py"):
            shutil.copyfile(SOURCE_ROOT / "scripts" / name, self.repo / "scripts" / name)
        (self.repo / "tests" / "test_alpha.py").write_text(
            "import unittest\nclass Alpha(unittest.TestCase):\n"
            "    def test_first(self): self.assertEqual(2 + 3, 5)\n"
            "    @unittest.skip('declared synthetic skip')\n"
            "    def test_skip(self): pass\n", encoding="utf-8")
        (self.repo / "tests" / "test_beta.py").write_text(
            "import unittest\nclass Beta(unittest.TestCase):\n"
            "    def test_first(self): self.assertTrue(True)\n"
            "    def test_second(self): self.assertEqual(7, 7)\n", encoding="utf-8")
        # Do not inherit the outer hosted checkout identity into this
        # independent fixture. No credentials or remote operations needed.
        self.env = dict(os.environ)
        for key in list(self.env):
            if key.startswith("GIT_") or key.startswith("GITHUB_") or key in (
                    "PYTHONPATH", "RIFT_TAXI_CLOUD_BATCH_ID"):
                self.env.pop(key, None)
        self.env["GIT_CONFIG_NOSYSTEM"] = "1"
        self.env["GIT_CONFIG_GLOBAL"] = str(self.base / "empty.gitconfig")
        (self.base / "empty.gitconfig").touch()
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "synthetic fixture")
        self.sha = self.git("rev-parse", "HEAD").stdout.strip()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env=self.env,
                              capture_output=True, text=True, check=True, timeout=15)

    def batch(self, name, *, env=None, extra=()):
        return subprocess.run(
            [sys.executable, "-B", "-m", "scripts.cloud_parallel",
             "--out-dir", str(self.base / name), "--shards", "2", "--workers", "2",
             "--timeout-seconds", "30", *extra],
            cwd=self.repo, env=self.env if env is None else env,
            capture_output=True, text=True, timeout=90)

    def read(self, name, file="batch.json"):
        return json.loads((self.base / name / file).read_text(encoding="utf-8"))

    def test_complete_two_process_batch_and_exclusive_output(self):
        run = self.batch("good")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        r = self.read("good")
        self.assertEqual(r["status"], "passed")
        self.assertEqual(r["commit"], self.sha)
        self.assertEqual(r["aggregate"]["testsDiscovered"], 4)
        self.assertEqual(r["aggregate"]["testsPassed"], 3)
        self.assertEqual(r["aggregate"]["testsSkipped"], 1)
        self.assertEqual([m["module"] for m in r["aggregate"]["moduleTimings"]],
                         ["test_alpha", "test_beta"])
        self.assertFalse(r["physicalQualification"])
        self.assertEqual([s["index"] for s in r["shards"]], [0, 1])
        for i in (0, 1):
            shard = self.read("good", f"shard-{i}.json")
            self.assertEqual(shard["identity"]["batchId"], r["batchId"])
            self.assertEqual(shard["planSHA256"], r["planSHA256"])
            self.assertTrue((self.base / "good" / f"shard-{i}.log").is_file())
        before = (self.base / "good" / "batch.json").read_bytes()
        refused = self.batch("good")
        self.assertEqual(refused.returncode, 2)
        self.assertEqual((self.base / "good" / "batch.json").read_bytes(), before)
        second = self.batch("second", extra=("--workers", "1"))
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertNotEqual(self.read("second")["batchId"], r["batchId"])
        self.assertEqual(self.read("second")["aggregate"]["testsDiscovered"], 4)

    def test_failed_shard_retained_without_successful_merge(self):
        (self.repo / "tests" / "test_beta.py").write_text(
            "import unittest\nclass Beta(unittest.TestCase):\n"
            "    def test_fail(self): self.fail('synthetic refusal')\n", encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "deliberate failure")
        run = self.batch("bad")
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        r = self.read("bad")
        self.assertEqual(r["status"], "failed")
        self.assertIsNone(r["aggregate"])
        self.assertIsNone(r["merge"])
        self.assertEqual(len(r["shards"]), 2)
        self.assertTrue(any(s["status"] == "failed" for s in r["shards"]))
        self.assertFalse((self.base / "bad" / "merged.json").exists())

    def test_dirty_checkout_refused_before_output(self):
        (self.repo / "untracked.txt").write_text("dirty", encoding="utf-8")
        run = self.batch("dirty")
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertFalse((self.base / "dirty").exists())

    def test_hosted_run_attempt_identity_is_carried_and_required(self):
        env = {**self.env, "GITHUB_ACTIONS": "true", "GITHUB_SHA": self.sha,
               "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "2",
               "GITHUB_REPOSITORY": "fixture/repo"}
        run = self.batch("hosted", env=env)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(self.read("hosted")["identity"]["hostedRun"],
                         {"repository": "fixture/repo", "runId": "12345", "attempt": "2"})
        del env["GITHUB_RUN_ATTEMPT"]
        refused = self.batch("missing", env=env)
        self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)
        self.assertFalse((self.base / "missing").exists())

    def test_checkout_mutation_during_shard_prevents_pass_receipt(self):
        # A passing assertion must not authorize a receipt if a test leaves
        # observable source drift. This uses a disposable fixture repo.
        (self.repo / "tests" / "test_beta.py").write_text(
            "import unittest\nfrom pathlib import Path\nclass Beta(unittest.TestCase):\n"
            "    def test_mutate(self): Path('untracked-drift.txt').write_text('changed')\n",
            encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "checkout drift fixture")
        run = self.batch("drift", extra=("--workers", "1"))
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        r = self.read("drift")
        self.assertEqual(r["status"], "failed")
        self.assertIsNone(r["aggregate"])
        self.assertFalse((self.base / "drift" / "merged.json").exists())
        self.assertTrue((self.repo / "untracked-drift.txt").exists())
        logs = "\n".join((self.base / "drift" / f"shard-{i}.log").read_text(
            encoding="utf-8") for i in (0,1))
        self.assertIn("checkout identity changed during validation", logs)

    def test_invalid_worker_and_timeout_limits_refused(self):
        for name, extra in (("workers", ("--workers", "3")),
                            ("timeout", ("--timeout-seconds", "0"))):
            with self.subTest(name=name):
                run = self.batch(name, extra=extra)
                self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
                self.assertFalse((self.base / name).exists())


class RunIdentityMergeTests(unittest.TestCase):
    def test_same_commit_different_batch_or_attempt_is_refused(self):
        identity = {"commit": "a"*40, "cleanCheckout": True, "platform": "Linux",
                    "python": "3.14.10", "batchId": "1"*32,
                    "hostedRun": {"repository": "fixture/repo", "runId": "12", "attempt": "1"}}
        plan = cloud_test_runner.make_plan(["test_a.C.test_one"], [], 1, identity)
        receipt = {"schema": "taxi.cloud-test-shard/1", "identity": dict(identity),
                   "planSHA256": plan["planSHA256"], "index": 0, "status": "passed",
                   "startedTestIds": ["test_a.C.test_one"], "skippedTestIds": [],
                   "testsRun": 1, "failures": 0, "errors": 0, "unexpectedSuccesses": 0,
                   "expectedFailures": 0, "elapsedSeconds": .1, "physicalQualification": False,
                   "moduleTimings": [{"module": "test_a", "testsRun": 1, "elapsedSeconds": .05}]}
        self.assertEqual(cloud_test_runner.merge(plan, [receipt])["testsPassed"], 1)
        for changed in ({**identity, "batchId": "2"*32},
                        {**identity, "hostedRun": {**identity["hostedRun"], "attempt": "2"}}):
            with self.assertRaises(cloud_test_runner.CloudValidationError):
                cloud_test_runner.merge(plan, [{**receipt, "identity": changed}])
