"""Analytic oracle and complete-grid reconciliation for offline strata."""
import random
import unittest

from test_delay_factorial_audit import fixture
from rift_taxi.delay_factorial_stratification import stratify


class StratificationTests(unittest.TestCase):
    def test_known_speed_effect_and_terminal_denominator(self):
        """Low speed always succeeds; high speed always fails in fixture."""
        result = stratify(fixture())
        self.assertFalse(result["physicalQualification"])
        route = result["routes"][0]
        for effect in route["effects"]:
            self.assertEqual(effect["pairs"], 144)
            expected = (dict(both=0, lost=144, gained=0, neither=0)
                        if effect["factor"] == "speed"
                        else dict(both=72, lost=0, gained=0, neither=72))
            for outcome in effect["outcomes"].values():
                self.assertEqual(outcome, expected)
        for patterns in route["delayHistories"].values():
            self.assertEqual(patterns, {"000": 144, "111": 144})
        for terminal in route["terminalDistribution"]:
            self.assertEqual((terminal["total"], terminal["arrivals"],
                              terminal["failedApproaches"]), (288, 144, 144))
            self.assertEqual((terminal["minError"], terminal["medianError"],
                              terminal["maxError"]), (.1, .1, .1))
            self.assertEqual(terminal["outsideTolerance"], 0)

    def test_row_order_does_not_change_result(self):
        report = fixture()
        baseline = stratify(report)
        random.Random(2026).shuffle(report["cases"])
        self.assertEqual(stratify(report), baseline)

    def test_incomplete_report_refused(self):
        report = fixture()
        report["cases"].pop()
        with self.assertRaises(ValueError):
            stratify(report)
