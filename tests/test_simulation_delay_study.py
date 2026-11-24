"""Regression tests for the offline synthetic command FIFO.

No game process, real input, or external source is involved. Preserve the
zero-delay benchmark, verify requested/applied separation, and never equate
an observation-boundary position match with a settled delayed arrival.
"""
from pathlib import Path
import unittest

from rift_taxi.contracts import TraceError, load_trace
from rift_taxi.simulation import simulate_route
from rift_taxi.simulation_delay_study import evaluate_delay_study

SOURCE = Path(__file__).resolve().parents[1]/"samples"/"synthetic_continuous.json"


class DelayStudyTests(unittest.TestCase):
    def test_zero_delay_preserves_report(self):
        """Explicit zero is identical to the original default."""
        trace = load_trace(SOURCE)
        self.assertEqual(simulate_route(trace), simulate_route(trace,delay_steps=0))

    def test_fifo_applies_exact_requested_commands_after_two_steps(self):
        """Initial history is stationary; metrics use applied, not requested motion."""
        result = simulate_route(load_trace(SOURCE),delay_steps=2)
        frames = result["frames"][:-1]
        self.assertGreater(len(frames),2)
        for i,frame in enumerate(frames):
            expected = ((0.,0.) if i<2 else
                        (frames[i-2]["requestedSpeed"],
                         frames[i-2]["requestedYawRateDegreesPerSecond"]))
            self.assertEqual((frame["speed"],frame["yawRateDegreesPerSecond"]),expected)
        self.assertAlmostEqual(result["metrics"]["forwardSeconds"],
                               sum(f["stepSeconds"] for f in frames if f["speed"]>0.))
        self.assertFalse(result["syntheticDelay"]["settledArrivalVerified"])
        self.assertEqual(len(result["syntheticDelay"]["pendingCommands"]),2)
        self.assertFalse(result["gameInputSent"])

    def test_invalid_delay_rejected(self):
        """No silent conversion of booleans, fractional or unbounded delay."""
        trace = load_trace(SOURCE)
        for delay in (-1,11,True,1.5):
            with self.subTest(delay=delay),self.assertRaises(TraceError):
                simulate_route(trace,delay_steps=delay)

    def test_frozen_delay_sensitivity_and_pending_motion(self):
        """Preserve the actual measured synthetic outcomes, including failures."""
        report = evaluate_delay_study()
        self.assertEqual(len(report["cases"]),432)
        self.assertEqual([r["geometricArrivals"] for r in report["summary"]],[108,106,96,72])
        self.assertEqual([r["arrivalAndDutyTarget"] for r in report["summary"]],[40,35,24,17])
        self.assertEqual([r["arrivalsWithPendingMotion"] for r in report["summary"]],[0,106,96,72])
        self.assertFalse(report["settledArrivalVerified"])
        self.assertFalse(report["gameInputSent"])


if __name__ == "__main__":
    unittest.main()
