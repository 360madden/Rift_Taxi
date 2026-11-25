"""Functional tests for the ideal terminal-only reference maneuver."""
import unittest

from rift_taxi.synthetic_terminal_finish import finish_after_drain, evaluate_observed


class SyntheticTerminalFinishTests(unittest.TestCase):
    def case(self, **changes):
        params = dict(xyz=[1., 0., 0.], yaw=0., goal=[0., 0., 0.],
                      dt=.1, speed=2., yaw_rate=90., delay_steps=3)
        params.update(changes)
        return finish_after_drain(**params)

    def test_corrects_with_bounded_delayed_commands(self):
        result = self.case()
        self.assertTrue(result["settled"])
        self.assertEqual(result["status"], "model-corrected")
        self.assertAlmostEqual(result["finalErrorXZ"], .15)
        self.assertLessEqual(result["extraSeconds"], 5.)
        self.assertFalse(result["physicalQualification"])
        self.assertFalse(result["gameInputSent"])
        frames = result["frames"]
        self.assertTrue(all(f["appliedSpeed"] == 0. and f["appliedYawRate"] == 0.
                            for f in frames[:4]))
        self.assertTrue(all(0. <= f["appliedSpeed"] <= 2. and
                            abs(f["appliedYawRate"]) <= 90. for f in frames))
        self.assertEqual(frames[-1]["appliedSpeed"], 0.)
        self.assertEqual(frames[-1]["appliedYawRate"], 0.)
        self.assertEqual(frames[-1]["xyz"], frames[-2]["xyz"])

    def test_preserves_passive_success_without_extra_motion(self):
        result = self.case(xyz=[.2, 0., 0.])
        self.assertEqual(result["status"], "already-settled")
        self.assertEqual(result["extraSeconds"], 0.)
        self.assertEqual(result["extraTravelXZ"], 0.)
        self.assertEqual(len(result["frames"]), 1)

    def test_budget_refusal_leaves_pose_unchanged(self):
        result = self.case(budget=.1)
        self.assertEqual(result["status"], "terminal-budget-insufficient")
        self.assertFalse(result["settled"])
        self.assertEqual(result["frames"][-1]["xyz"], [1., 0., 0.])
        self.assertEqual(result["extraSeconds"], 0.)

    def test_invalid_delay_and_nonflat_plane(self):
        with self.assertRaises(ValueError):
            self.case(delay_steps=True)
        with self.assertRaises(ValueError):
            self.case(goal=[0., 1., 0.])

    def test_observed_cases_and_passive_outcomes(self):
        report = evaluate_observed()
        self.assertEqual(len(report["rows"]), 24)
        self.assertEqual(report["summary"]["baseline"]["passiveSettled"], 11)
        self.assertEqual(report["summary"]["candidate"]["passiveSettled"], 0)
        for side in ("baseline", "candidate"):
            self.assertEqual(report["summary"][side]["afterCorrectionSettled"], 12)
            self.assertLessEqual(report["summary"][side]["maxExtraSeconds"], 5.)
        self.assertFalse(report["physicalQualification"])
        self.assertFalse(report["gameInputSent"])


if __name__ == "__main__":
    unittest.main()
