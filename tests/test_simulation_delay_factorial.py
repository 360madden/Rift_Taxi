"""Factorial synthetic study coverage, matching and frozen-reference tests.

No physical client or hardware. Retain all failed outcomes rather than
conditioning effect estimates on successful journeys.
"""
import contextlib
import io
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rift_taxi.cli import main
from rift_taxi.simulation_delay_factorial import evaluate_delay_factorial
from rift_taxi.simulation_holdout_v3 import evaluate_holdout_v3


class DelayFactorialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluate_delay_factorial()

    def test_complete_crossed_design_and_matched_delay(self):
        """Each initial condition appears exactly once in each profile."""
        r = self.report
        self.assertEqual((r["geometryCount"], r["profileCount"], r["simulationCount"]), (36, 24, 864))
        keys = {(row["geometryCase"], row["speed"], row["maxYawRate"], row["dt"],
                 row["nominalDelaySeconds"]) for row in r["cases"]}
        expected = set(product(range(1, 37), (2.2, 3.4), (65., 140.),
                               (.055, .11), (0., .11, .33)))
        self.assertEqual(keys, expected)
        self.assertEqual(len(r["cases"]), len(keys))
        self.assertEqual(len({row["scenarioSHA256"] for row in r["cases"]}), 288)
        for row in r["cases"]:
            self.assertAlmostEqual(row["delaySteps"] * row["dt"], row["nominalDelaySeconds"])
            if not row["geometricArrival"]:
                self.assertFalse(row["settledWithinTolerance"])
                self.assertIsNone(row["settledErrorXZ"])
        self.assertFalse(r["gameInputSent"])
        self.assertFalse(r["liveArrivalVerified"])

    def test_original_high_profile_matches_frozen_v3_per_case(self):
        """Do not accidentally change old geometry, policy, or result semantics."""
        original = evaluate_holdout_v3()
        old = {row["scenarioSHA256"]: row for row in original["cases"]
               if (row["speed"], row["maxYawRate"], row["dt"]) == (3.4, 140., .11)}
        self.assertEqual(len(old), 36)
        selected = [r for r in self.report["cases"]
                    if (r["speed"], r["maxYawRate"], r["dt"]) == (3.4, 140., .11)]
        self.assertEqual(len(selected), 108)
        for row in selected:
            outcome = old[row["scenarioSHA256"]]["outcomes"][f"turn-limited-ordered:{row['delaySteps']}"]
            self.assertEqual(row["status"], outcome["status"])
            self.assertEqual(row["geometricArrival"], outcome["metrics"]["syntheticArrival"])
            self.assertEqual(row["settledWithinTolerance"], outcome["terminalDrain"]["settledWithinTolerance"])
            self.assertEqual(row["finalXZError"], outcome["metrics"]["finalXZError"])
            self.assertEqual(row["settledErrorXZ"], outcome["terminalDrain"].get("settledErrorXZ"))

    def test_paired_effects_reconcile_to_all_outcomes(self):
        """Verify gains/losses direction against independent marginal counts."""
        r = self.report
        self.assertEqual(len(r["matchedEffects"]), 9)
        for effect in r["matchedEffects"]:
            self.assertEqual(effect["pairs"], 144)
            for name, counts in effect["outcomes"].items():
                self.assertEqual(sum(counts.values()), 144)
                selected = [row for row in r["cases"]
                            if row["nominalDelaySeconds"] == effect["nominalDelaySeconds"]]
                old = sum(row[name] for row in selected if row[effect["factor"]] == effect["low"])
                new = sum(row[name] for row in selected if row[effect["factor"]] == effect["high"])
                self.assertEqual(counts["lost"] + counts["both"], old)
                self.assertEqual(counts["gained"] + counts["both"], new)
        for summary in r["byDelay"]:
            self.assertEqual(summary["runs"], 288)
            self.assertEqual(sum(summary["statusCounts"].values()), 288)
            self.assertEqual(summary["settledWithinTolerance"] + summary["settledOutside"],
                             summary["geometricArrivals"])

    def test_cli_preflights_and_preserves_report_bytes(self):
        """Test the actual writer with cached study output to avoid rerunning the grid."""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "factorial.json"
            args = ["study-delay-factors", "--out", str(target)]
            with patch("rift_taxi.cli.evaluate_delay_factorial", return_value=self.report) as evaluate:
                self.assertEqual(main(args), 0)
                self.assertEqual(json.loads(target.read_text()), self.report)
                before = target.read_bytes()
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(args), 2)
                self.assertEqual(target.read_bytes(), before)
                evaluate.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
