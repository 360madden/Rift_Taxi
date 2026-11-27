"""Regression guards for matched complete-journey batch evidence."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rift_taxi.synthetic_journey_batch import compare, cases, paired_metrics, main
from rift_taxi.simulation_holdout import _case_trace


class JourneyBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Run the actual complete synthetic journeys once, not a fabricated
        # result table. Reuse the report for independent accounting checks.
        cls.report = compare()

    def test_frozen_design_and_case_identity(self):
        specs = list(cases())
        self.assertEqual(len(specs), 48)
        self.assertEqual(_case_trace(specs[0][0]).trace_sha256,
                         "42760df450690b232fc4189ecc98c36655fa80cc9a466562ef33d71fa0b13455")
        rows = self.report["rows"]
        self.assertEqual(len({r["caseSHA256"] for r in rows}), 48)
        self.assertEqual(self.report["executionCount"], 128)
        self.assertFalse(self.report["physicalQualification"])
        self.assertFalse(self.report["gameInputSent"])

    def test_policy_eligibility_and_frozen_outcomes(self):
        for row in self.report["rows"]:
            expected = {"baseline", "zero-delay-rejoin"} if row["delaySteps"] == 0 else {
                "baseline", "predict-near-goal", "predict-near-stall"}
            self.assertEqual(set(row["results"]), expected)
            for value in row["results"].values():
                self.assertEqual(value["inputTraceSHA256"], row["scenarioSHA256"])
                self.assertFalse(value["gameInputSent"])
        for mode, counts in (("zero-delay-rejoin", (16, 12, 16, 4)),
                             ("predict-near-goal", (32, 30, 32, 2)),
                             ("predict-near-stall", (32, 30, 32, 2))):
            stats = self.report["comparisons"][mode]
            self.assertEqual(tuple(stats[k] for k in
                ("matchedCases", "baselineSettled", "candidateSettled", "settledGains")), counts)
            self.assertEqual(stats["settledLosses"], 0)

    def test_means_use_only_common_settled_cases(self):
        def outcome(ok, seconds):
            return {"summary": {"finalModelSettled": ok, "totalElapsedSeconds": seconds,
                                "totalForwardDutyRatio": .5}}
        rows = [{"results": {"baseline": outcome(True, 2), "test": outcome(True, 3)}},
                {"results": {"baseline": outcome(False, 40), "test": outcome(True, 1)}},
                {"results": {"baseline": outcome(True, 1), "test": outcome(False, 40)}}]
        stats = paired_metrics(rows, "test")
        self.assertEqual(stats["settledGains"], 1)
        self.assertEqual(stats["settledLosses"], 1)
        self.assertEqual(stats["baselineCommonSettledMeans"]["meanTotalElapsedSeconds"], 2)
        self.assertEqual(stats["candidateCommonSettledMeans"]["meanTotalElapsedSeconds"], 3)
        self.assertIsNone(paired_metrics(rows[1:], "test")["baselineCommonSettledMeans"])

    def test_existing_output_refused_without_simulating(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "existing.json"
            path.write_text("keep", encoding="utf-8")
            with patch("rift_taxi.synthetic_journey_batch.compare") as run, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main(["--out", str(path)])
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()
            self.assertEqual(path.read_text(encoding="utf-8"), "keep")

    def test_summary_preserves_full_file(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "new.json"
            stdout = io.StringIO()
            with patch("rift_taxi.synthetic_journey_batch.compare", return_value=self.report), contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["--out", str(path), "--summary"]), 0)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), self.report)
            compact = json.loads(stdout.getvalue())
            self.assertNotIn("rows", compact)
            self.assertEqual(compact["comparisons"], self.report["comparisons"])
