"""Regression coverage for the observed V4 terminal diagnostic."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
import zipfile
import math
import unittest

from rift_taxi.simulation_v4_terminal_observation import evaluate
from rift_taxi.v4_terminal_archive_audit import verify, verify_zip


class V4TerminalObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluate()

    def test_observed_outcomes_reproduce(self):
        r = self.report
        self.assertEqual(r["pairs"], 12)
        self.assertFalse(r["physicalQualification"])
        self.assertFalse(r["gameInputSent"])
        self.assertEqual(r["summary"]["baseline"]["arrivals"], 12)
        self.assertEqual(r["summary"]["candidate"]["arrivals"], 12)
        self.assertEqual(r["summary"]["baseline"]["settled"], 11)
        self.assertEqual(r["summary"]["candidate"]["settled"], 0)

    def test_terminal_observations_reconcile(self):
        for row in self.report["rows"]:
            for side in ("baseline", "candidate"):
                outcome = row[side]
                self.assertTrue(outcome["arrived"])
                terminal = outcome["terminal"]
                dt = row["scenario"]["dt"]
                self.assertAlmostEqual(terminal["drainSeconds"], .36)
                self.assertAlmostEqual(terminal["queuedTravel"],
                                       sum(c["speed"] * dt for c in terminal["queue"]))
                self.assertEqual(len(terminal["observations"]), len(terminal["queue"]) + 2)
                first, last = terminal["observations"][0], terminal["observations"][-1]
                self.assertEqual(first["destinationErrorXZ"], terminal["firstError"])
                self.assertEqual(last["destinationErrorXZ"], terminal["finalError"])
                self.assertEqual(last["appliedSpeed"], 0.)
                self.assertEqual(last["appliedYawRateDegreesPerSecond"], 0.)
                self.assertEqual(outcome["settled"], terminal["finalError"] <= .30)
                self.assertTrue(math.isfinite(terminal["queuedTravel"]))
        print("V4_TERMINAL_SUMMARY " + json.dumps(self.report["summary"],
                                                  sort_keys=True, allow_nan=False))

    def test_independent_terminal_archive_audit(self):
        """Use the actual observed report without rerunning the simulation."""
        receipt = verify(self.report)
        self.assertEqual(receipt["intervals"], 132)
        self.assertEqual(receipt["settled"], {"baseline": 11, "candidate": 0})
        self.assertFalse(receipt["physicalQualification"])

    def test_terminal_archive_rejects_corruption(self):
        """Changing recorded geometry, observations, or authority must fail."""
        for change in (
            lambda r: r["rows"][0]["scenario"].__setitem__("speed", 9.),
            lambda r: r["rows"][0]["baseline"]["terminal"]["observations"][1]["xyz"].__setitem__(0, 99.),
            lambda r: r["rows"][0]["candidate"]["terminal"].__setitem__("leftTolerance", False),
            lambda r: r.__setitem__("physicalQualification", True),
        ):
            r = copy.deepcopy(self.report)
            change(r)
            with self.assertRaises(ValueError):
                verify(r)

    def test_zip_digest_and_member_admission(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.zip"
            def write(name):
                with zipfile.ZipFile(path, "w") as z:
                    z.writestr(name, json.dumps(self.report, allow_nan=False))
                return hashlib.sha256(path.read_bytes()).hexdigest()
            digest = write("v4-terminal-observation.json")
            self.assertEqual(verify_zip(path, digest)["pairs"], 12)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verify_zip(path, "0" * 64)
            digest = write("unexpected.json")
            with self.assertRaisesRegex(ValueError, "ZIP member"):
                verify_zip(path, digest)

    def test_summary_fields_are_recomputed(self):
        for field, value in (("arrivals", 11), ("settled", True),
                             ("sampledExits", 0), ("meanQueuedTravel", 0.),
                             ("meanErrorChange", 0.)):
            report = copy.deepcopy(self.report)
            report["summary"]["baseline"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                verify(report)

    def test_rehashed_wrong_design_is_rejected(self):
        """A self-consistent digest does not make an altered design admissible."""
        report = copy.deepcopy(self.report)
        row = report["rows"][0]
        row["scenario"]["headingOffsetDegrees"] = 42.
        row["scenario"]["initialYawDegrees"] = math.degrees(math.atan2(1., 7.)) + 42.
        raw = json.dumps(row["scenario"], sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode()
        row["scenarioSHA256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(ValueError, "frozen design coverage"):
            verify(report)
