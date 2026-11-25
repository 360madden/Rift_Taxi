"""Exercise the complete offline journey without a game installation."""
from dataclasses import replace
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.simulation_holdout import _case_trace
from rift_taxi.synthetic_journey_demo import journey


def straight_trace():
    return _case_trace({"routeId": "demo-straight",
                        "routeXYZ": [[0.,0.,0.],[6.,0.,0.]],
                        "initialXYZ": [0.,0.,0.],
                        "initialYawDegrees": 0.}, generator="taxi-journey-demo-test")


class SyntheticJourneyDemoTests(unittest.TestCase):
    def test_complete_journey_retains_phase_boundaries(self):
        trace = straight_trace()
        result = journey(trace, delay_steps=2)
        self.assertTrue(result["summary"]["geometricArrival"])
        self.assertTrue(result["summary"]["finalModelSettled"])
        self.assertEqual(result["inputTraceSHA256"], trace.trace_sha256)
        self.assertEqual(result["approach"]["frames"][-1]["xyz"],
                         result["passiveDrain"]["observations"][0]["xyz"])
        self.assertEqual(result["passiveDrain"]["observations"][-1]["xyz"],
                         result["terminalCorrection"]["frames"][0]["xyz"])
        self.assertFalse(result["physicalQualification"])
        self.assertFalse(result["gameInputSent"])

    def test_approach_timeout_cannot_become_terminal_success(self):
        result = journey(straight_trace(), approach_budget=.2)
        self.assertEqual(result["summary"]["status"], "approach-failed")
        self.assertFalse(result["summary"]["finalModelSettled"])
        self.assertIsNone(result["terminalCorrection"])

    def test_historical_trace_is_refused(self):
        with self.assertRaises(TraceError):
            journey(replace(straight_trace(), source_type="historical"))

    def test_invalid_terminal_budget_is_refused(self):
        with self.assertRaises(TraceError):
            journey(straight_trace(), terminal_budget=float("nan"))
