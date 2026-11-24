"""Synthetic V3 failure taxonomy regressions; no live game access."""
import unittest
from rift_taxi.simulation_v3_failure_audit import audit_v3_failures, _tail_motion


class V3FailureAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = audit_v3_failures()

    def test_preserve_all_matched_outcomes_and_profile_confound(self):
        """Keep all cases, including the two distinct failure classes."""
        report = self.report
        self.assertEqual(report["caseCount"],216)
        self.assertEqual(len({(r["case"],r["delaySteps"]) for r in report["cases"]}),216)
        self.assertEqual(report["byDelay"][-1]["outcomeCounts"],
                         {"approach-failed":12,"settled-inside":47,"settled-outside":13})
        adverse = [r for r in report["cases"] if r["category"]!="settled-inside"]
        self.assertEqual(len(adverse),25)
        self.assertTrue(all(r["delaySteps"]==3 and r["profile"]["dt"]==.11 for r in adverse))
        self.assertFalse(report["gameInputSent"])
        self.assertFalse(report["liveArrivalVerified"])

    def test_timeout_is_motion_without_arc_progress(self):
        """The frozen approach failures do not represent stationary waits."""
        failed = [r for r in self.report["cases"] if r["category"]=="approach-failed"]
        self.assertEqual(len(failed),12)
        for row in failed:
            self.assertEqual(row["orderedCornersPassed"],0)
            self.assertGreater(row["orderedCorners"],0)
            window = row["terminalMotionWindow"]
            self.assertAlmostEqual(window["sampledSeconds"],4.91)
            self.assertGreater(window["distanceXZ"],3.5)
            self.assertGreater(window["absoluteYawTravelDegrees"],600.)
            self.assertLess(window["arcAdvance"],.021)

    def test_tail_window_uses_applied_complete_intervals(self):
        """Boundary excludes partial intervals and ignores requested values."""
        frames = [{"t":float(t),"speed":1.,"stepSeconds":1.,
                   "yawRateDegreesPerSecond":(-1.)**t*20.,
                   "requestedSpeed":10.,"progress":float(t)/10.}
                  for t in range(7)]
        frames.append({"t":7.,"progress":.7})
        measured = _tail_motion({"frames":frames})
        self.assertEqual(measured["sampledSeconds"],5.)
        self.assertEqual(measured["distanceXZ"],5.)
        self.assertEqual(measured["absoluteYawTravelDegrees"],100.)
        self.assertAlmostEqual(measured["arcAdvance"],.5)


if __name__ == "__main__":
    unittest.main()
