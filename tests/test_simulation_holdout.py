"""Regression protection for the untuned route-shape holdout.

All tests run an ideal synthetic plant only. No game access or external input.
Keep the observed v1 failures visible: a future controller change must be
compared against this baseline rather than silently deleting hard cases.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.cli import main
from rift_taxi.simulation_holdout import evaluate_holdout, _case_trace


class HoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Share one deterministic report across the accounting tests.
        cls.report = evaluate_holdout()

    def test_complete_paired_grid_and_scenario_hashes(self):
        """Each policy sees the same uniquely identified scenario."""
        cases = self.report["cases"]
        self.assertEqual(len(cases), 162)
        self.assertEqual(len({row["scenarioSHA256"] for row in cases}), 162)
        keys = ("routeId", "routeXYZ", "initialXYZ", "initialYawDegrees",
                "lateralOffset", "headingOffsetDegrees", "speed", "maxYawRate", "dt")
        for row in cases:
            spec = {key: row[key] for key in keys}
            self.assertEqual(_case_trace(spec).trace_sha256, row["scenarioSHA256"])
        self.assertEqual(len(self.report["byRoute"]), 6)

    def test_preserve_both_improvements_and_regressions(self):
        """Pin the observed v1 baseline, including the short-zigzag failures."""
        report = self.report
        self.assertEqual(report["summary"]["fixed"]["arrivals"], 112)
        self.assertEqual(report["summary"]["turn-limited"]["arrivals"], 135)
        self.assertEqual(report["summary"]["turn-limited"]["arrivalAndDutyTarget"], 101)
        self.assertEqual(report["paired"]["newArrivals"], 38)
        self.assertEqual(report["paired"]["lostArrivals"], 15)
        self.assertEqual(report["paired"]["commonArrivals"], 97)
        zigzag = next(r for r in report["byRoute"] if r["routeId"] == "short-zigzag")
        self.assertEqual(zigzag["turn-limited"]["statusCounts"], {"lookahead-degenerate":27})
        self.assertFalse(report["gameInputSent"])
        self.assertFalse(report["liveNavigabilityVerified"])
        self.assertFalse(report["liveArrivalVerified"])

    def test_counts_and_timing_use_correct_populations(self):
        """Failure counts stay in denominators; timing uses common arrivals."""
        report = self.report
        for policy in ("fixed", "turn-limited"):
            summary = report["summary"][policy]
            self.assertEqual(sum(summary["statusCounts"].values()), 162)
            self.assertEqual(summary["arrivalAndDutyTarget"],
                             sum(r[policy]["arrivalAndDutyTarget"] for r in report["cases"]))
        common = [r for r in report["cases"] if all(
            r[p]["metrics"]["syntheticArrival"] for p in ("fixed","turn-limited"))]
        for policy in ("fixed","turn-limited"):
            expected = sum(r[policy]["metrics"]["elapsedSeconds"] for r in common)/len(common)
            self.assertAlmostEqual(report["paired"]["meanCommonArrivalSeconds"][policy], expected)

    def test_reproducible_report(self):
        """A second run must retain ordering and exact scenario outcomes."""
        self.assertEqual(evaluate_holdout(), self.report)

    def test_cli_new_report_and_no_overwrite(self):
        """Use the existing evidence-preserving writer, never overwrite."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"holdout.json"
            args = ["evaluate-holdout", "--out", str(path)]
            self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(path.read_text()), self.report)
            before = path.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 2)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
