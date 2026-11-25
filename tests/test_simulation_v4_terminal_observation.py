"""Regression coverage for the observed V4 terminal diagnostic."""
import json
import math
import unittest

from rift_taxi.simulation_v4_terminal_observation import evaluate


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
