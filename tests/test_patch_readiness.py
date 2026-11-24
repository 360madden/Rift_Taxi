"""Offline regressions for patch evidence admission; no game access or input.

Fixtures represent tiny, explicitly synthetic Update Helper snapshots. They
exercise the distinction between content changes and metadata-only changes,
and the refusal cases that would otherwise make an update receipt misleading.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.patch_readiness import assess, main


class PatchReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.before = self.snapshot("before", "before", 0)

    def snapshot(self, name, phase, minute, exe="a", asset="b", **overrides):
        # Distinct, non-overlapping UTC intervals stand in for independent
        # captures. File mtime is intentionally not part of content identity.
        rows = [
            {"path": "rift_x64.exe", "size": 10, "sha256": exe * 64, "mtime_ns": minute},
            {"path": "assets/terrain.dat", "size": 20, "sha256": asset * 64, "mtime_ns": minute},
        ]
        doc = dict(schema="update-helper.game-files.v1", phase=phase, host="LEGION",
                   root=r"C:\\Glyph\\RIFT", started_utc=f"2026-11-24T10:{minute:02}:00+00:00",
                   finished_utc=f"2026-11-24T10:{minute:02}:20+00:00", complete=True,
                   files=rows, file_count=2, bytes=30)
        doc.update(overrides)
        path = self.folder / (name + ".json")
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def run_assess(self, a=None, b=None, pin=None):
        return assess(self.before, "LEGION",
                      pin if pin is not None else hashlib.sha256(self.before.read_bytes()).hexdigest(),
                      a, b)

    def test_baseline_cannot_authorize_input(self):
        report = self.run_assess()
        self.assertEqual(report["status"], "baseline-only")
        self.assertIs(report["production_input_authorized"], False)
        self.assertIs(report["fresh_live_qualification_required"], True)

    def test_stable_metadata_only_change(self):
        report = self.run_assess(self.snapshot("a", "after", 1),
                                 self.snapshot("b", "after", 2))
        self.assertEqual(report["status"], "no-content-change")
        self.assertEqual(report["modified"], [])
        self.assertFalse(report["production_input_authorized"])

    def test_executable_and_assets_classified_separately(self):
        for exe, asset, status in (("c", "b", "executable-changed"),
                                   ("a", "d", "other-files-changed")):
            with self.subTest(status=status):
                report = self.run_assess(self.snapshot("a", "after", 1, exe, asset),
                                         self.snapshot("b", "after", 2, exe, asset))
                self.assertEqual(report["status"], status)
                self.assertTrue(report["fresh_live_qualification_required"])
                self.assertFalse(report["production_input_authorized"])

    def test_disagreeing_post_captures_refused(self):
        with self.assertRaisesRegex(ValueError, "disagree"):
            self.run_assess(self.snapshot("a", "after", 1),
                            self.snapshot("b", "after", 2, exe="c"))

    def test_missing_duplicate_and_overlapping_captures_refused(self):
        a = self.snapshot("a", "after", 1)
        with self.assertRaisesRegex(ValueError, "two separate"):
            self.run_assess(a)
        with self.assertRaisesRegex(ValueError, "duplicated"):
            self.run_assess(a, a)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            self.run_assess(a, self.snapshot("b", "after", 1, finished_utc="2026-11-24T10:01:40+00:00"))

    def test_wrong_host_root_and_baseline_pin_refused(self):
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.run_assess(pin="f" * 64)
        a = self.snapshot("a", "after", 1)
        with self.assertRaisesRegex(ValueError, "host mismatch"):
            self.run_assess(a, self.snapshot("b", "after", 2, host="AMD-DESKTOP"))
        with self.assertRaisesRegex(ValueError, "another root"):
            self.run_assess(a, self.snapshot("b", "after", 2, root=r"D:\\RIFT"))

    def test_invalid_inventory_and_duplicate_json_refused(self):
        a = self.snapshot("a", "after", 1)
        for overrides in ({"complete": False}, {"file_count": 3}, {"bytes": True},
                          {"started_utc": "2026-11-24T10:02:00"}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    self.run_assess(a, self.snapshot("b", "after", 2, **overrides))
        bad = self.snapshot("b", "after", 2)
        bad.write_text('{"host":"LEGION","host":"AMD-DESKTOP"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.run_assess(a, bad)

    def test_cli_exit_two_for_wrong_pin(self):
        self.assertEqual(main(["--before", str(self.before), "--expected-host", "LEGION",
                               "--expected-before-sha", "f" * 64]), 2)
