"""Frozen v2 synthetic validation and trajectory-consistency regressions.

The adverse cases are intentional. Do not tune the scenario definitions to
remove failures; future model changes should preserve this baseline receipt.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.cli import main
from rift_taxi.contracts import TraceError
from rift_taxi.simulation_holdout import _case_trace
from rift_taxi.simulation_holdout_v2 import evaluate_holdout_v2, _verify_trajectory
from rift_taxi.simulation import simulate_route

_KEYS = ("routeId","routeXYZ","initialXYZ","initialYawDegrees",
         "lateralOffset","headingOffsetDegrees","speed","maxYawRate","dt")


class HoldoutV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluate_holdout_v2()

    def test_complete_unique_grid_and_negative_outcomes(self):
        """Keep every matched case and preserve the newly exposed limitations."""
        rows = self.report["cases"]
        self.assertEqual(len(rows),108)
        self.assertEqual(len({r["scenarioSHA256"] for r in rows}),108)
        self.assertEqual([self.report["summary"][p]["arrivals"] for p in
                          ("fixed","turn-limited","turn-limited-rejoin")],[93,60,72])
        self.assertEqual(self.report["pairedRejoin"]["newArrivals"],12)
        self.assertEqual(self.report["pairedRejoin"]["lostArrivals"],0)
        for route in self.report["byRoute"]:
            self.assertEqual(route["turn-limited-rejoin"]["arrivals"],
                             0 if route["routeId"] in ("crossing-bow","acute-return") else 18)
        for row in rows:
            trace = _case_trace({k:row[k] for k in _KEYS}, generator="taxi-holdout-v2")
            self.assertEqual(trace.trace_sha256,row["scenarioSHA256"])
            self.assertEqual(trace.source["generator"],"taxi-holdout-v2")
        self.assertFalse(self.report["gameInputSent"])
        self.assertFalse(self.report["liveArrivalVerified"])

    def test_closed_loop_cannot_arrive_without_traversing_arc(self):
        """Endpoint equals starting point; both position and progress matter."""
        row = next(r for r in self.report["cases"] if r["routeId"]=="closed-loop")
        spec = {k:row[k] for k in _KEYS}
        spec["initialXYZ"] = spec["routeXYZ"][0]
        spec["initialYawDegrees"] = 0.
        trace = _case_trace(spec, generator="taxi-holdout-v2")
        result = simulate_route(trace, speed_policy="turn-limited-rejoin")
        _verify_trajectory(result,trace)
        self.assertTrue(result["metrics"]["syntheticArrival"])
        self.assertGreater(result["metrics"]["elapsedSeconds"],1.)
        self.assertGreaterEqual(result["metrics"]["finalProgress"],17.7)
        # A forged endpoint error is rejected independently of the arrival flag.
        result["metrics"]["finalXZError"] += 1.
        with self.assertRaisesRegex(TraceError,"disagree"):
            _verify_trajectory(result,trace)

    def test_reproducible_cli_and_no_overwrite(self):
        """The new command uses the same evidence-preserving writer as v1."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"holdout-v2.json"
            args = ["evaluate-holdout-v2","--out",str(path)]
            self.assertEqual(main(args),0)
            self.assertEqual(json.loads(path.read_text()),self.report)
            original = path.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args),2)
            self.assertEqual(path.read_bytes(),original)


if __name__ == "__main__":
    unittest.main()
