"""Regression protection for the untuned route-shape holdout.

All tests run an ideal synthetic plant only. No game access or external input.
Keep the observed v1 failures visible: a future controller change must be
compared against this baseline rather than silently deleting hard cases.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.cli import main
from rift_taxi.simulation_holdout import evaluate_holdout, _case_trace


class HoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Share one deterministic report across the accounting tests.
        cls.report = evaluate_holdout()

    def test_complete_paired_grid_and_scenario_hashes(self):
        """Each policy sees the same uniquely identified scenario."""
        cases = self.report["cases"]
        self.assertEqual(len(cases), 162)
        self.assertEqual(len({row["scenarioSHA256"] for row in cases}), 162)
        keys = ("routeId", "routeXYZ", "initialXYZ", "initialYawDegrees",
                "lateralOffset", "headingOffsetDegrees", "speed", "maxYawRate", "dt")
        for row in cases:
            spec = {key: row[key] for key in keys}
            self.assertEqual(_case_trace(spec).trace_sha256, row["scenarioSHA256"])
        self.assertEqual(len(self.report["byRoute"]), 6)

    def test_preserve_both_improvements_and_regressions(self):
        """Pin the observed v1 baseline, including the short-zigzag failures."""
        report = self.report
        self.assertEqual(report["summary"]["fixed"]["arrivals"], 112)
        self.assertEqual(report["summary"]["turn-limited"]["arrivals"], 135)
        self.assertEqual(report["summary"]["turn-limited"]["arrivalAndDutyTarget"], 101)
        self.assertEqual(report["paired"]["newArrivals"], 38)
        self.assertEqual(report["paired"]["lostArrivals"], 15)
        self.assertEqual(report["paired"]["commonArrivals"], 97)
        zigzag = next(r for r in report["byRoute"] if r["routeId"] == "short-zigzag")
        self.assertEqual(zigzag["turn-limited"]["statusCounts"], {"lookahead-degenerate":27})
        self.assertFalse(report["gameInputSent"])
        self.assertFalse(report["liveNavigabilityVerified"])
        self.assertFalse(report["liveArrivalVerified"])

    def test_counts_and_timing_use_correct_populations(self):
        """Failure counts stay in denominators; timing uses common arrivals."""
        report = self.report
        for policy in ("fixed", "turn-limited"):
            summary = report["summary"][policy]
            self.assertEqual(sum(summary["statusCounts"].values()), 162)
            self.assertEqual(summary["arrivalAndDutyTarget"],
                             sum(r[policy]["arrivalAndDutyTarget"] for r in report["cases"]))
        common = [r for r in report["cases"] if all(
            r[p]["metrics"]["syntheticArrival"] for p in ("fixed","turn-limited"))]
        for policy in ("fixed","turn-limited"):
            expected = sum(r[policy]["metrics"]["elapsedSeconds"] for r in common)/len(common)
            self.assertAlmostEqual(report["paired"]["meanCommonArrivalSeconds"][policy], expected)

    def test_rejoin_comparison_preserves_baselines_and_rescues_zigzags(self):
        """Recovery is opt-in; preserve original failures and paired evidence."""
        result = evaluate_holdout(include_rejoin=True)
        self.assertEqual(result["schema"], "taxi.synthetic-rejoin-comparison/1")
        candidate = "turn-limited-rejoin"
        self.assertEqual(result["summary"][candidate]["arrivals"], 162)
        self.assertEqual(result["summary"][candidate]["arrivalAndDutyTarget"], 101)
        self.assertEqual(result["rejoinComparison"]["newArrivals"], 27)
        self.assertEqual(result["rejoinComparison"]["lostArrivals"], 0)
        self.assertEqual(result["rejoinComparison"]["casesEnteringRejoin"], 27)
        self.assertEqual(result["rejoinComparison"]["newCombinedSuccesses"], 0)
        self.assertEqual(result["rejoinComparison"]["lostCombinedSuccesses"], 0)
        for original, revised in zip(self.report["cases"], result["cases"], strict=True):
            # Removing only the extra policy leaves the original case unchanged.
            self.assertEqual(original, {k:v for k,v in revised.items() if k != candidate})
            self.assertLessEqual(revised[candidate]["metrics"]["finalXZError"], .3)
        self.assertFalse(result["gameInputSent"])
        self.assertFalse(result["liveArrivalVerified"])

    def test_rejoin_target_does_not_advance_arc_or_claim_early_arrival(self):
        """Reproduce case 95: a local anchor replaces a vanishing chord."""
        from rift_taxi.simulation import simulate_route
        from rift_taxi.steering import _segments, _lookahead_point
        import math
        case = next(r for r in self.report["cases"] if r["case"] == 95)
        keys = ("routeId", "routeXYZ", "initialXYZ", "initialYawDegrees",
                "lateralOffset", "headingOffsetDegrees", "speed", "maxYawRate", "dt")
        trace = _case_trace({k:case[k] for k in keys})
        report = simulate_route(trace, speed=case["speed"], max_yaw_rate=case["maxYawRate"],
                                dt=case["dt"], max_seconds=40., speed_policy="turn-limited-rejoin")
        cumulative, total = _segments(trace.points)
        frames = report["frames"]
        rejoin = [f for f in frames if f.get("targetMode") == "local-projection-rejoin"]
        self.assertTrue(rejoin)
        for f in rejoin:
            anchor = _lookahead_point(trace.points, cumulative, f["progress"])
            self.assertEqual(f["lookaheadXYZ"], list(anchor))
        # The original per-step projection budget and arrival test stay intact.
        for a,b in zip(frames, frames[1:]):
            displacement = math.hypot(b["xyz"][0]-a["xyz"][0], b["xyz"][2]-a["xyz"][2])
            self.assertGreaterEqual(b["progress"], a["progress"])
            self.assertLessEqual(b["progress"]-a["progress"], 2.*displacement+1e-8)
        self.assertGreaterEqual(frames[-1]["progress"], total-.3)
        self.assertLessEqual(report["metrics"]["finalXZError"], .3)
        self.assertEqual(report["status"], "synthetic-arrived")

    def test_rejoin_development_grid_retains_all_combined_successes(self):
        """An improvement on zigzags must not regress the prior tuning grid."""
        from rift_taxi.contracts import load_trace
        from rift_taxi.simulation_stress import stress_route
        path = Path(__file__).resolve().parents[1] / "samples" / "synthetic_continuous.json"
        result = stress_route(load_trace(path), speed_policy="turn-limited-rejoin")
        self.assertEqual(result["summary"]["arrived"], 180)
        self.assertEqual(result["summary"]["arrivalAndDutyTarget"], 180)

    def test_reproducible_report(self):
        """A second run must retain ordering and exact scenario outcomes."""
        self.assertEqual(evaluate_holdout(), self.report)

    def test_cli_new_report_and_no_overwrite(self):
        """Use the existing evidence-preserving writer, never overwrite."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"holdout.json"
            args = ["evaluate-holdout", "--out", str(path)]
            self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(path.read_text()), self.report)
            before = path.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 2)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
