"""Synthetic cloud fixture verification: real committed samples plus corruption tests."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.cloud_fixture_library import (
    FixtureLibraryError, MANIFEST, ROOT, verify_library,
)


class CloudFixtureLibraryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "samples").mkdir()
        self.manifest = self.root / MANIFEST
        shutil.copyfile(ROOT / MANIFEST, self.manifest)
        self.doc = json.loads(self.manifest.read_bytes())
        for row in self.doc["fixtures"]:
            target = self.root / row["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / row["path"], target)

    def save(self):
        self.manifest.write_text(json.dumps(self.doc), encoding="utf-8")

    def rewrite_fixture(self, update):
        row = self.doc["fixtures"][0]
        path = self.root / row["path"]
        doc = json.loads(path.read_bytes())
        update(doc)
        raw = json.dumps(doc).encode("utf-8")
        path.write_bytes(raw)
        row["sha256"] = hashlib.sha256(raw).hexdigest()
        row["sizeBytes"] = len(raw)
        self.save()

    def test_real_committed_library_and_repeatability(self):
        actual = verify_library()
        self.assertEqual(actual, verify_library(self.root))
        self.assertEqual(actual["fixtureCount"], 2)
        self.assertEqual(actual["classification"], "SYNTHETIC_ONLY")
        self.assertFalse(actual["physicalQualification"])
        self.assertFalse(actual["gameInputSent"])

    def test_corrupted_fixture_bytes_refused(self):
        path = self.root / self.doc["fixtures"][0]["path"]
        path.write_bytes(path.read_bytes()+b" ")
        with self.assertRaises(FixtureLibraryError):
            verify_library(self.root)

    def test_missing_fixture_refused(self):
        (self.root / self.doc["fixtures"][0]["path"]).unlink()
        with self.assertRaises(FixtureLibraryError):
            verify_library(self.root)

    def test_historical_source_refused_even_when_rehashed(self):
        self.rewrite_fixture(lambda doc: doc.update(sourceType="historical"))
        with self.assertRaises(FixtureLibraryError):
            verify_library(self.root)

    def test_route_projection_mismatch_refused_even_when_rehashed(self):
        self.rewrite_fixture(lambda doc: doc["route"].update(id="wrong-route"))
        with self.assertRaises(FixtureLibraryError):
            verify_library(self.root)

    def test_semantically_invalid_trace_refused_even_when_rehashed(self):
        self.rewrite_fixture(lambda doc: doc["poses"][1].update(t=-1))
        with self.assertRaises(FixtureLibraryError):
            verify_library(self.root)

    def test_path_traversal_and_bool_size_rejected(self):
        row = self.doc["fixtures"][0]
        original = dict(row)
        for key, value in (("path", "samples/../outside.json"),
                           ("path", "C:\\private.json"), ("sizeBytes", True),
                           ("sourceType", "historical"), ("sha256", "xyz")):
            with self.subTest(key=key, value=value):
                row.clear()
                row.update(original)
                row[key] = value
                self.save()
                with self.assertRaises(FixtureLibraryError):
                    verify_library(self.root)

    def test_duplicate_fixture_and_duplicate_json_key_refused(self):
        self.doc["fixtures"].append(dict(self.doc["fixtures"][0]))
        self.save()
        with self.assertRaises(FixtureLibraryError):
            verify_library(self.root)
        self.manifest.write_text('{"schema":1,"schema":2}', encoding="utf-8")
        with self.assertRaises(FixtureLibraryError):
            verify_library(self.root)
