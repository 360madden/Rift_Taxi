"""Frozen v3 synthetic evaluation regression; no physical input or map."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.cli import main
from rift_taxi.simulation_holdout import _case_trace
from rift_taxi.simulation_holdout_v3 import evaluate_holdout_v3

_KEYS = ("routeId","routeXYZ","initialXYZ","initialYawDegrees",
         "lateralOffset","headingOffsetDegrees","speed","maxYawRate","dt")


class HoldoutV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluate_holdout_v3()

    def test_unique_matched_scenarios_and_run_counts(self):
        """Every policy/delay uses identical source geometry and initial pose."""
        rows = self.report["cases"]
        self.assertEqual(len(rows),72)
        self.assertEqual(self.report["simulationCount"],432)
        self.assertEqual(len({r["scenarioSHA256"] for r in rows}),72)
        for row in rows:
            trace = _case_trace({k:row[k] for k in _KEYS},generator="taxi-holdout-v3")
            self.assertEqual(trace.trace_sha256,row["scenarioSHA256"])
            self.assertEqual(len(row["outcomes"]),6)
        self.assertFalse(self.report["gameInputSent"])
        self.assertFalse(self.report["liveArrivalVerified"])

    def test_frozen_outcomes_keep_failures_and_settling_separate(self):
        """Never drop failed approaches or count geometric entry as settling."""
        summary = self.report["summary"]
        keys = ("fixed:0","turn-limited:0","turn-limited-rejoin:0",
                "turn-limited-ordered:0","turn-limited-ordered:1","turn-limited-ordered:3")
        self.assertEqual([summary[k]["geometricArrivals"] for k in keys],[61,36,54,72,72,60])
        self.assertEqual([summary[k]["arrivalAndDutyTarget"] for k in keys],[23,26,26,26,22,12])
        self.assertEqual([summary[k]["settledWithinTolerance"] for k in keys[3:]],[72,72,47])
        self.assertEqual(summary[keys[-1]]["sampledToleranceExits"],13)
        for row in self.report["byRoute"]:
            expected = 6 if row["routeId"] in ("narrow-return","double-crossing") else 12
            self.assertEqual(row["summary"][keys[-1]]["geometricArrivals"],expected)

    def test_cli_deterministic_and_no_overwrite(self):
        """Use the existing new-file-only writer; protect earlier evidence."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"v3.json"
            args = ["evaluate-holdout-v3","--out",str(path)]
            self.assertEqual(main(args),0)
            self.assertEqual(json.loads(path.read_text()),self.report)
            before = path.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args),2)
            self.assertEqual(path.read_bytes(),before)


if __name__ == "__main__":
    unittest.main()
