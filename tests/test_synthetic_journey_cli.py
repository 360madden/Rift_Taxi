"""Subprocess smoke tests for the standalone offline journey interface.

Use the checked-in three-bend trace and the actual module entry point, not
a mocked main() or game process. Temporary files exercise the CLI's
exclusive-create output contract. No game memory or input is accessed.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "samples" / "synthetic_continuous.json"


class SyntheticJourneyCLITests(unittest.TestCase):
    def invoke(self, *args):
        """Run the user-facing command using the same interpreter as tests.

        The explicit cwd makes repository imports deterministic; this is
        a source-checkout smoke test, not an installed-wheel qualification.
        A generous timeout also bounds unexpected subprocess hangs.
        """
        return subprocess.run(
            [sys.executable, "-B", "-m", "rift_taxi.synthetic_journey_demo",
             str(TRACE), *map(str, args)],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
            encoding="utf-8",
        )

    def test_stdout_is_complete_synthetic_report(self):
        result = self.invoke("--delay-steps", 2)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema"], "taxi.synthetic-journey-demo/1")
        self.assertEqual(report["routeId"], "three-bend-synthetic-course")
        self.assertEqual(report["classification"], "SYNTHETIC_ONLY")
        self.assertFalse(report["physicalQualification"])
        self.assertFalse(report["gameInputSent"])
        # Avoid assuming a particular outcome for an observed development
        # fixture; failed arrivals must remain visible rather than vanish.
        self.assertIn(report["summary"]["status"],
                      {"model-settled", "terminal-unsettled", "approach-failed"})
        self.assertEqual(report["summary"]["geometricArrival"],
                         report["approach"]["metrics"]["syntheticArrival"])

    def test_budget_exhaustion_stays_failed_in_written_report(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            result = self.invoke("--approach-budget", 0.2, "--out", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            # A successful report write is not a successful modeled journey.
            self.assertEqual(result.stdout, "")
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["status"], "approach-failed")
            self.assertFalse(report["summary"]["finalModelSettled"])
            self.assertIsNone(report["terminalCorrection"])

    def test_existing_output_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "existing.json"
            original = b"existing evidence\n"
            output.write_bytes(original)
            result = self.invoke("--out", output)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("Synthetic journey refused:", result.stderr)
            self.assertEqual(output.read_bytes(), original)

    def test_opt_in_prediction_is_exposed_by_cli(self):
        result = self.invoke("--approach-mode", "predict-near-stall", "--delay-steps", 2)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["experimentalApproachMode"], "predict-near-stall")
        self.assertIn("syntheticCommandPrediction", report["approach"])
        self.assertFalse(report["gameInputSent"])

    def test_invalid_budget_refuses_without_creating_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "invalid.json"
            result = self.invoke("--terminal-budget", "nan", "--out", output)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("Synthetic journey refused:", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
