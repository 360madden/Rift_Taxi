"""Fixed-grid synthetic robustness benchmark regression tests."""
from dataclasses import replace
from pathlib import Path
import contextlib
import io
import json
import tempfile
import unittest

from rift_taxi.cli import main
from rift_taxi.contracts import TraceError, load_trace
from rift_taxi.simulation_stress import stress_route

SOURCE = Path(__file__).resolve().parents[1] / "samples" / "synthetic_continuous.json"


class StressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace = load_trace(SOURCE)
        cls.report = stress_route(cls.trace)

    def test_full_grid_retains_unique_cases_and_all_outcomes(self):
        rows = self.report["cases"]
        self.assertEqual(len(rows), 180)
        self.assertEqual(len({(r["offsetXZ"], r["headingOffsetDegrees"], r["speed"],
                              r["maxYawRate"], r["dt"]) for r in rows}), 180)
        summary = self.report["summary"]
        self.assertEqual(summary["cases"], 180)
        self.assertEqual(sum(summary["statusCounts"].values()), 180)
        self.assertEqual(summary["arrived"], sum(r["metrics"]["syntheticArrival"] for r in rows))
        self.assertEqual(summary["arrivalAndDutyTarget"],
                         sum(r["meetsArrivalAndDutyTarget"] for r in rows))
        self.assertEqual(summary["arrived"], 165)
        self.assertEqual(summary["arrivalAndDutyTarget"], 131)
        self.assertEqual(summary["statusCounts"]["cross-track-limit"], 15)
        self.assertEqual([r["arrived"] for r in self.report["byYawRate"]], [45, 60, 60])

    def test_start_overrides_are_explicit_and_base_is_unchanged(self):
        self.assertEqual(self.report["baseTraceSHA256"], self.trace.trace_sha256)
        self.assertEqual(self.report["baseInitialXYZ"], list(self.trace.poses[0].xyz))
        self.assertEqual(self.report["baseInitialYawDegrees"], self.trace.poses[0].actor_yaw_deg)
        for row in self.report["cases"]:
            self.assertEqual(row["initialXYZ"], [0., 0., row["offsetXZ"]])
            self.assertEqual(row["initialYawDegrees"], row["headingOffsetDegrees"])
        self.assertFalse(self.report["gameInputSent"])
        self.assertFalse(self.report["liveArrivalVerified"])
        self.assertFalse(self.report["liveNavigabilityVerified"])

    def test_repeatable_grid(self):
        self.assertEqual(self.report, stress_route(self.trace))

    def test_reject_historical_and_missing_initial_heading(self):
        with self.assertRaises(TraceError):
            stress_route(replace(self.trace, source_type="historical"))
        with self.assertRaises(TraceError):
            stress_route(replace(self.trace,
                poses=(replace(self.trace.poses[0], actor_yaw_deg=None),)))

    def test_cli_new_report_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/"stress.json"
            args = ["stress-route", str(SOURCE), "--out", str(output)]
            self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(output.read_text())["summary"], self.report["summary"])
            original = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 2)
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
