"""Offline terminal-drain evidence and regression tests.

Tests deliberately preserve the first-arrival metric and verify only the
ideal synthetic model. No claim of real actuator or key release is made.
"""
import copy
from pathlib import Path
import unittest

from rift_taxi.contracts import TraceError, load_trace
from rift_taxi.simulation import simulate_route
from rift_taxi.simulation_settling import drain_after_arrival, evaluate_settling_study

SOURCE = Path(__file__).resolve().parents[1]/"samples"/"synthetic_continuous.json"


class SettlingTests(unittest.TestCase):
    def test_zero_delay_is_stationary_and_source_unchanged(self):
        """Observe one stationary step; never rewrite first-arrival data."""
        trace = load_trace(SOURCE)
        result = simulate_route(trace,speed_policy="turn-limited-ordered")
        before = copy.deepcopy(result)
        drain = drain_after_arrival(result,trace)
        self.assertEqual(result,before)
        self.assertTrue(drain["settledWithinTolerance"])
        self.assertEqual(drain["queueDrainSeconds"],0.)
        self.assertEqual(drain["postArrivalDistanceXZ"],0.)
        self.assertEqual(drain["settledErrorXZ"],result["metrics"]["finalXZError"])
        self.assertEqual(drain["observations"][0]["xyz"],drain["observations"][-1]["xyz"])
        self.assertFalse(drain["physicalSettlingVerified"])

    def test_queue_matches_request_history_and_drains_in_order(self):
        """Replay only retained commands, then verify one zero interval."""
        trace = load_trace(SOURCE)
        result = simulate_route(trace,speed_policy="turn-limited-ordered",delay_steps=2)
        self.assertTrue(result["metrics"]["syntheticArrival"])
        drain = drain_after_arrival(result,trace)
        queue = result["syntheticDelay"]["pendingCommands"]
        dt = result["model"]["dtSeconds"]
        self.assertAlmostEqual(drain["postArrivalDistanceXZ"],sum(c["speed"]*dt for c in queue))
        self.assertEqual(len(drain["observations"]),4)
        for actual,expected in zip(drain["observations"][1:-1],queue):
            self.assertEqual(actual["appliedSpeed"],expected["speed"])
            self.assertEqual(actual["appliedYawRateDegreesPerSecond"],expected["yawRateDegreesPerSecond"])
        self.assertEqual(drain["observations"][-1]["xyz"],drain["observations"][-2]["xyz"])
        self.assertEqual(drain["observations"][-1]["appliedSpeed"],0.)
        forged = copy.deepcopy(result)
        forged["syntheticDelay"]["pendingCommands"][0]["speed"] = 0.
        with self.assertRaisesRegex(TraceError,"queue disagrees"):
            drain_after_arrival(forged,trace)

    def test_failed_approach_cannot_become_settled_arrival(self):
        """A timeout is not a successful terminal observation."""
        trace = load_trace(SOURCE)
        result = simulate_route(trace,speed_policy="turn-limited-ordered",max_seconds=.2)
        drain = drain_after_arrival(result,trace)
        self.assertEqual(drain["status"],"not-geometrically-arrived")
        self.assertFalse(drain["settledWithinTolerance"])

    def test_frozen_study_retains_overshoots_and_failures(self):
        """Keep all denominators and distinguish final error from entry."""
        report = evaluate_settling_study()
        self.assertEqual(len(report["cases"]),432)
        self.assertEqual([r["geometricArrivals"] for r in report["summary"]],[108,106,96,72])
        self.assertEqual([r["settledWithinTolerance"] for r in report["summary"]],[108,106,91,67])
        self.assertEqual([r["leftToleranceAtSample"] for r in report["summary"]],[0,0,5,5])
        self.assertFalse(report["physicalSettlingVerified"])
        self.assertFalse(report["gameInputSent"])


if __name__ == "__main__":
    unittest.main()
