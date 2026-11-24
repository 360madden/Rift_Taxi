"""Synthetic ordered-corner regression and passage-evidence checks.

Use the frozen v1/v2 scenarios rather than altering geometry after results.
No native input, live pose, or real-world navigation is involved.
"""
import unittest
from pathlib import Path
from rift_taxi.contracts import TraceError, load_trace
from rift_taxi.simulation import simulate_route
from rift_taxi.simulation_holdout import _case_trace
from rift_taxi.simulation_ordered_comparison import compare_ordered_corners, verify_ordered_passages
from rift_taxi.simulation_stress import stress_route

_KEYS = ("routeId", "routeXYZ", "initialXYZ", "initialYawDegrees",
         "lateralOffset", "headingOffsetDegrees", "speed", "maxYawRate", "dt")
_NEW = "turn-limited-ordered"


class OrderedCornerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = compare_ordered_corners()

    def test_frozen_comparison_retains_all_arrivals(self):
        """Retain every case and separate arrival from continuous-motion duty."""
        v1,v2 = self.report["sets"]
        self.assertEqual(v1["summary"][_NEW]["arrivals"],162)
        self.assertEqual(v1["summary"][_NEW]["arrivalAndDutyTarget"],112)
        self.assertEqual(v2["summary"][_NEW]["arrivals"],108)
        self.assertEqual(v2["summary"][_NEW]["arrivalAndDutyTarget"],40)
        self.assertEqual(v2["paired"]["newArrivals"],36)
        self.assertEqual(v2["paired"]["lostArrivals"],0)
        self.assertFalse(self.report["gameInputSent"])
        self.assertFalse(self.report["liveArrivalVerified"])
        for r in v2["byRoute"]:
            self.assertEqual(r[_NEW]["arrivals"],18)

    def test_corner_passage_witness_rejects_forgery(self):
        """A counter is insufficient; witness geometry/time must match a frame."""
        row = next(r for r in self.report["sets"][1]["cases"] if r["routeId"]=="crossing-bow")
        trace = _case_trace({k:row[k] for k in _KEYS},generator="taxi-holdout-v2")
        result = simulate_route(trace,speed=row["speed"],max_yaw_rate=row["maxYawRate"],
                                dt=row["dt"],max_seconds=40.,speed_policy=_NEW)
        verify_ordered_passages(result,trace)
        witnesses = result["syntheticRecovery"]["orderedSharpCornerPassages"]
        self.assertTrue(witnesses)
        witnesses[0]["xyz"][0] += 2.
        with self.assertRaisesRegex(TraceError,"invalid ordered corner passage"):
            verify_ordered_passages(result,trace)

    def test_development_grid_remains_unchanged(self):
        """Ordinary corners must not be converted into new checkpoint stops."""
        path = Path(__file__).resolve().parents[1]/"samples"/"synthetic_continuous.json"
        trace = load_trace(path)
        baseline = stress_route(trace,speed_policy="turn-limited-rejoin")
        candidate = stress_route(trace,speed_policy=_NEW)
        self.assertEqual(candidate["summary"],baseline["summary"])
        self.assertEqual(candidate["summary"]["arrivalAndDutyTarget"],180)


if __name__ == "__main__":
    unittest.main()
