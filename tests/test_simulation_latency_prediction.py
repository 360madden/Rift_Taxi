"""Regressions for opt-in synthetic queued-pose prediction.

All geometry and command rates are model-only. The short-terminal case
was observed failing in the recovered V1 experiment, so it is a
regression fixture, not an independent validation case.
"""
import copy
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.simulation import simulate_route
from rift_taxi.simulation_holdout import _case_trace
from rift_taxi.simulation_integrity import verify_synthetic_trajectory
from rift_taxi.simulation_settling import drain_after_arrival


def short_terminal_trace():
    """Preserve the geometry, seed pose and declared tolerance of case 32."""
    return _case_trace({
        "routeId": "short-terminal-leg",
        "routeXYZ": [[0.,0.,0.], [5.,0.,0.], [5.,0.,5.],
                     [9.,0.,5.], [9.,0.,5.7]],
        "initialXYZ": [0.,0.,-.6], "initialYawDegrees": 40.,
        "lateralOffset": -.6, "headingOffsetDegrees": 40.,
        "speed": 3.4, "maxYawRate": 65., "dt": .11,
    }, generator="taxi-holdout-v3")


def simulate(trace, *, delay=1, predict=True):
    return simulate_route(trace, speed=3.4, max_yaw_rate=65., dt=.11,
                          max_seconds=40., speed_policy="turn-limited-ordered",
                          delay_steps=delay, predict_command_application=predict)


class LatencyPredictionTests(unittest.TestCase):
    def test_terminal_rejoin_earns_progress_without_relaxing_arrival(self):
        trace = short_terminal_trace()
        report = simulate(trace)
        verify_synthetic_trajectory(report, trace)
        self.assertTrue(report["metrics"]["syntheticArrival"])
        self.assertTrue(drain_after_arrival(report, trace)["settledWithinTolerance"])
        self.assertGreaterEqual(report["metrics"]["finalProgress"],
                                report["metrics"]["routeLengthXZ"] - trace.arrival_tolerance_xz)
        self.assertTrue(any(f.get("targetMode") == "terminal-progress-rejoin"
                            for f in report["frames"]))
        # Independent trajectory verification enforces the displacement
        # budget on every frame, including rejoin. No progress teleport.

    def test_zero_delay_is_exact_noop(self):
        trace = short_terminal_trace()
        self.assertEqual(simulate(trace, delay=0, predict=False),
                         simulate(trace, delay=0, predict=True))

    def test_prediction_is_opt_in_and_ordered_only(self):
        trace = short_terminal_trace()
        baseline = simulate(trace, predict=False)
        self.assertNotIn("syntheticCommandPrediction", baseline)
        self.assertFalse(any(f.get("targetMode") == "terminal-progress-rejoin"
                             for f in baseline["frames"]))
        with self.assertRaises(TraceError):
            simulate_route(trace, delay_steps=1, predict_command_application=True)

    def test_near_stall_preserves_arrival_and_zero_delay(self):
        # V3 is a named opt-in experiment; V2 and the original zero-delay
        # policy remain reproducible. Check the formerly deadlocked route.
        trace = short_terminal_trace()
        kwargs = dict(speed=3.4, max_yaw_rate=65., dt=.11, max_seconds=40.,
                      speed_policy="turn-limited-ordered",
                      predict_command_application=True,
                      prediction_rejoin_policy="near-stall")
        report = simulate_route(trace, delay_steps=1, **kwargs)
        verify_synthetic_trajectory(report, trace)
        self.assertTrue(report["metrics"]["syntheticArrival"])
        self.assertTrue(drain_after_arrival(report, trace)["settledWithinTolerance"])
        self.assertEqual(report["syntheticCommandPrediction"]["terminalRejoinFraction"], .1)
        self.assertEqual(simulate_route(trace, delay_steps=0, **kwargs),
                         simulate(trace, delay=0, predict=False))

    def test_alternate_policy_requires_explicit_prediction(self):
        with self.assertRaises(TraceError):
            simulate_route(short_terminal_trace(), prediction_rejoin_policy="near-stall")
        with self.assertRaises(TraceError):
            simulate_route(short_terminal_trace(), speed_policy="turn-limited-ordered",
                           predict_command_application=True,
                           prediction_rejoin_policy="unknown")

    def test_forecast_tampering_is_rejected(self):
        trace = short_terminal_trace()
        report = copy.deepcopy(simulate(trace))
        report["frames"][0]["predictedApplicationXYZ"][0] += 1.
        with self.assertRaises(TraceError):
            verify_synthetic_trajectory(report, trace)

    def test_prediction_does_not_certify_live_navigation(self):
        report = simulate(short_terminal_trace())
        self.assertFalse(report["gameInputSent"])
        self.assertFalse(report["liveArrivalVerified"])
        self.assertFalse(report["liveNavigabilityVerified"])


if __name__ == "__main__":
    unittest.main()
