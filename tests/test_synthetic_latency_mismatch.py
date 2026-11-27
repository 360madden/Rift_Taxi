"""Check assumed-queue independence and fixed-design study accounting."""
from copy import deepcopy
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.simulation import simulate_route
from rift_taxi.simulation_integrity import verify_synthetic_trajectory
from rift_taxi.simulation_holdout import _case_trace
from rift_taxi.synthetic_journey_demo import journey, compact_report
from rift_taxi.synthetic_latency_mismatch import cases, evaluate


class LatencyMismatchTests(unittest.TestCase):
    def setUp(self):
        spec, *_ = next(cases())
        self.trace = _case_trace(spec)
        self.kwargs = dict(dt=.1, delay_steps=3, speed_policy="turn-limited-ordered",
                           predict_command_application=True)

    def test_equal_estimate_preserves_exact_legacy_report(self):
        self.assertEqual(simulate_route(self.trace, **self.kwargs),
                         simulate_route(self.trace, **self.kwargs, prediction_delay_steps=3))

    def test_under_and_over_estimate_independently_verified(self):
        for estimate in (1, 5):
            result = simulate_route(self.trace, **self.kwargs, prediction_delay_steps=estimate)
            verify_synthetic_trajectory(result, self.trace)
            self.assertEqual(result["syntheticDelay"]["steps"], 3)
            self.assertEqual(result["syntheticCommandPrediction"]["assumedDelaySteps"], estimate)
            # The actual FIFO still has three initial stationary commands,
            # even when the predictor assumes a different history length.
            self.assertTrue(all(f["speed"] == 0 and f["yawRateDegreesPerSecond"] == 0
                                for f in result["frames"][:3]))
            self.assertNotEqual(result, simulate_route(self.trace, **self.kwargs))
            changed = deepcopy(result)
            changed["syntheticCommandPrediction"]["assumedDelaySteps"] = 2
            with self.assertRaises(TraceError):
                verify_synthetic_trajectory(changed, self.trace)

    def test_forecast_tampering_refused(self):
        result = simulate_route(self.trace, **self.kwargs, prediction_delay_steps=1)
        changed = deepcopy(result)
        changed["frames"][2]["predictedApplicationXYZ"][0] += .1
        with self.assertRaises(TraceError):
            verify_synthetic_trajectory(changed, self.trace)

    def test_invalid_estimates_refused(self):
        for estimate in (True, 0, -1, 11, 1.5):
            with self.subTest(estimate=estimate), self.assertRaises(TraceError):
                simulate_route(self.trace, **self.kwargs, prediction_delay_steps=estimate)
        for kwargs in ({"delay_steps": 0, "predict_command_application": True},
                       {"delay_steps": 3, "predict_command_application": False}):
            with self.assertRaises(TraceError):
                simulate_route(self.trace, speed_policy="turn-limited-ordered",
                               prediction_delay_steps=1, **kwargs)

    def test_compact_report_labels_mismatch(self):
        result = journey(self.trace, delay_steps=3, approach_mode="predict-near-stall",
                         prediction_delay_steps=1)
        self.assertEqual(compact_report(result)["assumedDelaySteps"], 1)
        self.assertFalse(result["gameInputSent"])

    def test_study_retains_all_pairs(self):
        report = evaluate()
        self.assertEqual(report["caseCount"], 36)
        self.assertEqual(report["executionCount"], 144)
        self.assertEqual(len(report["groups"]), 9)
        self.assertEqual(len(report["rows"]), 36)
        for group in report["groups"]:
            self.assertEqual(group["versusNoPrediction"]["matchedCases"], 12)
            self.assertEqual(group["versusExactPrediction"]["matchedCases"], 12)
            if group["actualDelaySteps"] == group["assumedDelaySteps"]:
                self.assertEqual(group["versusExactPrediction"]["settledGains"], 0)
                self.assertEqual(group["versusExactPrediction"]["settledLosses"], 0)
        self.assertFalse(report["physicalQualification"])
