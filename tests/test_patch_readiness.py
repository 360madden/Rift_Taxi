"""Offline regressions for patch evidence admission; no game access or input.

Fixtures represent tiny, explicitly synthetic Update Helper snapshots. They
exercise the distinction between content changes and metadata-only changes,
and the refusal cases that would otherwise make an update receipt misleading.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from rift_taxi import patch_readiness
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
                   root=r"C:\Glyph\RIFT", started_utc=f"2026-11-24T10:{minute:02}:00+00:00",
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
            self.run_assess(a, self.snapshot("b", "after", 2, root=r"D:\RIFT"))

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

    def modify_inventory(self, path, change):
        """Rewrite a synthetic fixture, recomputing totals to isolate invariants."""
        doc = json.loads(path.read_text(encoding="utf-8"))
        change(doc["files"])
        doc["file_count"] = len(doc["files"])
        doc["bytes"] = sum(row["size"] for row in doc["files"])
        path.write_text(json.dumps(doc), encoding="utf-8")

    def test_windows_aliases_and_non_file_names_refused(self):
        # These are invalid even when two independently saved manifests agree.
        for name in ("rift_x64.exe.", "assets/NUL.txt", "assets/COM¹.log",
                     "assets/trailing ", "assets/bad\\x00file", "assets/a?b",
                     "assets/../terrain.dat", "assets/terrain.dat:stream",
                     "assets/\\ud800", "assets//terrain.dat", "/absolute"):
            with self.subTest(name=repr(name)):
                a = self.snapshot("a", "after", 1)
                b = self.snapshot("b", "after", 2)
                for path in (a, b):
                    self.modify_inventory(path, lambda rows: rows.append(
                        dict(path=name, size=1, sha256="c" * 64, mtime_ns=0)))
                with self.assertRaisesRegex(ValueError, "invalid relative file path"):
                    self.run_assess(a, b)

    def test_file_directory_conflict_refused_in_either_order(self):
        # A file cannot be a directory containing another file. Include a
        # lexically intervening sibling to guard against adjacent-only checks.
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                a = self.snapshot("a", "after", 1)
                def change(rows):
                    rows.extend([
                        dict(path="rift_x64.exe-extra", size=1, sha256="c" * 64, mtime_ns=0),
                        dict(path="RIFT_X64.EXE/sub/file", size=1, sha256="c" * 64, mtime_ns=0),
                    ])
                    if reverse:
                        rows.reverse()
                self.modify_inventory(a, change)
                with self.assertRaisesRegex(ValueError, "file-directory"):
                    self.run_assess(a, self.snapshot("b", "after", 2))

    def test_canonical_root_and_nonzero_capture_interval(self):
        a = self.snapshot("a", "after", 1)
        for root in (r"C:\\Glyph\\.\\RIFT", r"C:\\Glyph\\RIFT.",
                     r"C:/Glyph/RIFT", r"C:\\Glyph\\..\\RIFT",
                     r"\\\\server\\share\\RIFT"):
            with self.subTest(root=root):
                with self.assertRaisesRegex(ValueError, "canonical local"):
                    self.run_assess(a, self.snapshot("b", "after", 2, root=root))
        with self.assertRaisesRegex(ValueError, "positive duration"):
            self.run_assess(a, self.snapshot("b", "after", 2,
                            finished_utc="2026-11-24T10:02:00+00:00"))

    def test_zero_byte_executable_and_conflicting_hash_lengths(self):
        # A zero-length executable cannot represent the expected installation.
        a = self.snapshot("a", "after", 1)
        self.modify_inventory(a, lambda rows: rows[0].update(size=0))
        with self.assertRaisesRegex(ValueError, "executable identity"):
            self.run_assess(a, self.snapshot("b", "after", 2))
        # Same content hash with a different length is inconsistent across
        # snapshots, even if each independently declares matching totals.
        a, b = self.snapshot("a", "after", 1), self.snapshot("b", "after", 2)
        for path in (a, b):
            self.modify_inventory(path, lambda rows: rows[0].update(size=11))
        with self.assertRaisesRegex(ValueError, "conflicting file lengths"):
            self.run_assess(a, b)
        self.modify_inventory(self.before, lambda rows: rows[1].update(sha256="a" * 64))
        with self.assertRaisesRegex(ValueError, "conflicting file lengths"):
            self.run_assess()

    def test_file_identity_detects_reused_hardlink(self):
        # Simulate a caller overwriting a captured file between reads via a
        # hardlink. Both reads return different valid bytes and time intervals,
        # but the same underlying file identity cannot be independent evidence.
        a = self.snapshot("a", "after", 1)
        fresh = self.snapshot("fresh", "after", 2).read_bytes()
        b = self.folder / "alias.json"
        try:
            os.link(a, b)
        except OSError as exc:
            self.skipTest(f"filesystem does not support hardlinks: {exc}")
        real_read = patch_readiness.read_manifest
        def reuse(path, host, phase):
            result = real_read(path, host, phase)
            if path == a:
                b.write_bytes(fresh)
            return result
        with mock.patch.object(patch_readiness, "read_manifest", side_effect=reuse):
            with self.assertRaisesRegex(ValueError, "duplicated"):
                self.run_assess(a, b)

    def test_observable_manifest_replacement_refused(self):
        # An actual replacement between opening and post-read stat must fail
        # even when the replacement contains byte-identical JSON.
        path = self.before
        replacement = self.folder / "replacement.json"
        replacement.write_bytes(path.read_bytes())
        original_stat = patch_readiness._path_stat
        calls = 0
        def swap_on_second_stat(p):
            nonlocal calls
            calls += 1
            if calls == 2:
                os.replace(replacement, p)
            return original_stat(p)
        with mock.patch.object(patch_readiness, "_path_stat", side_effect=swap_on_second_stat):
            with self.assertRaisesRegex(ValueError, "changed while reading"):
                self.run_assess()

    def test_non_regular_and_oversized_evidence_refused(self):
        with self.assertRaisesRegex(ValueError, "regular"):
            patch_readiness.read_manifest(self.folder, "LEGION", "before")
        with mock.patch.object(patch_readiness, "MAX_MANIFEST_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "bounded evidence size"):
                self.run_assess()

    def test_cli_exit_two_for_wrong_pin(self):
        self.assertEqual(main(["--before", str(self.before), "--expected-host", "LEGION",
                               "--expected-before-sha", "f" * 64]), 2)
