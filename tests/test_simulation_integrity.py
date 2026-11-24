"""Synthetic report-consistency tests, including deliberately corrupted copies.

The source fixture is an invented flat course; no game process or live
actuator is involved. A valid report is internally consistent, not
authenticated physical evidence.
"""
import copy
from pathlib import Path
import unittest

from rift_taxi.contracts import TraceError, load_trace
from rift_taxi.simulation import simulate_route
from rift_taxi.simulation_integrity import verify_synthetic_trajectory

SOURCE = Path(__file__).resolve().parents[1]/"samples"/"synthetic_continuous.json"


class SyntheticIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace = load_trace(SOURCE)
        cls.normal = simulate_route(cls.trace)
        cls.delayed = simulate_route(cls.trace,delay_steps=2)

    def test_accept_valid_zero_delay_and_fifo_reports(self):
        """Validation must leave the generated reports unmodified."""
        for result in (self.normal,self.delayed):
            before = copy.deepcopy(result)
            verify_synthetic_trajectory(result,self.trace)
            self.assertEqual(result,before)

    def test_reject_wrong_identity_and_physical_claims(self):
        """Synthetic-only provenance and false live flags are required."""
        for key,value in (("inputTraceSHA256","0"*64),("routeId","unrelated"),
                          ("liveArrivalVerified",True),("gameInputSent",True)):
            result = copy.deepcopy(self.normal)
            result[key] = value
            with self.subTest(key=key),self.assertRaises(TraceError):
                verify_synthetic_trajectory(result,self.trace)

    def test_reject_inconsistent_frame_integration(self):
        """A valid endpoint does not excuse a corrupted intermediate pose."""
        for key,value in (("t",.001),("yawDegrees",34.),("speed",0.),
                          ("stepSeconds",.001)):
            result = copy.deepcopy(self.normal)
            result["frames"][2][key] = value
            with self.subTest(key=key),self.assertRaises(TraceError):
                verify_synthetic_trajectory(result,self.trace)
        result = copy.deepcopy(self.normal)
        result["frames"][2]["xyz"][1] += .1
        with self.assertRaisesRegex(TraceError,"integrated position"):
            verify_synthetic_trajectory(result,self.trace)

    def test_reject_nonfinite_and_boolean_fields(self):
        """Python bool and nonfinite floats are not valid evidence numbers."""
        for value in (float("nan"),float("inf"),True):
            result = copy.deepcopy(self.normal)
            result["frames"][1]["progress"] = value
            with self.subTest(value=value),self.assertRaises(TraceError):
                verify_synthetic_trajectory(result,self.trace)

    def test_reject_summary_and_status_forgery(self):
        """Recompute metrics from applied motion rather than trust totals."""
        for key in ("forwardSeconds","simulatedDistanceXZ","forwardDutyRatio",
                    "maxCrossTrackErrorXZ","turningWhileForwardSeconds"):
            result = copy.deepcopy(self.normal)
            result["metrics"][key] += .2
            with self.subTest(key=key),self.assertRaisesRegex(TraceError,"disagrees"):
                verify_synthetic_trajectory(result,self.trace)
        result = copy.deepcopy(self.normal)
        result["metrics"]["syntheticArrival"] = False
        with self.assertRaisesRegex(TraceError,"arrival status"):
            verify_synthetic_trajectory(result,self.trace)

    def test_reject_fifo_history_and_terminal_queue_forgery(self):
        """Applied commands and pending queue must match prior requests."""
        result = copy.deepcopy(self.delayed)
        result["frames"][0]["requestedSpeed"] = 0.
        with self.assertRaises(TraceError):
            verify_synthetic_trajectory(result,self.trace)
        result = copy.deepcopy(self.delayed)
        result["syntheticDelay"]["pendingCommands"][0]["speed"] = 0.
        with self.assertRaisesRegex(TraceError,"terminal queue disagrees"):
            verify_synthetic_trajectory(result,self.trace)
        result = copy.deepcopy(self.delayed)
        del result["syntheticDelay"]
        with self.assertRaisesRegex(TraceError,"lack delay"):
            verify_synthetic_trajectory(result,self.trace)

    def test_timeout_and_terminal_frame_remain_distinct(self):
        """Accept honest failures but reject nonzero terminal yaw requests."""
        result = simulate_route(self.trace,max_seconds=.22)
        self.assertEqual(result["status"],"time-budget-exhausted")
        verify_synthetic_trajectory(result,self.trace)
        result["frames"][-1]["yawRateDegreesPerSecond"] = 1.
        with self.assertRaisesRegex(TraceError,"terminal frame"):
            verify_synthetic_trajectory(result,self.trace)


if __name__ == "__main__":
    unittest.main()
