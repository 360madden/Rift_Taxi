"""Verify synthetic phase accounting without changing the original duty metric."""
import copy
import unittest
from rift_taxi.contracts import TraceError
from rift_taxi.simulation_recovery_audit import measure_recovery_phases, audit_recovery_efficiency


def fixture():
    # Deliberately cover startup, ordinary movement, rejoin stop, nearly
    # zero motion, and ordinary motion. The terminal frame has no duration.
    values = [(0., 0., "lookahead"), (.1, 1., "lookahead"),
              (.2, 0., "local-projection-rejoin"),
              (.3, .01, "local-projection-rejoin"), (.4, 1., "lookahead")]
    return {
        "classification":"SYNTHETIC_CLOSED_LOOP_ONLY",
        "model":{"speedPolicy":"turn-limited-rejoin"},
        "frames":[{"t":t,"stepSeconds":.1,"speed":speed,"targetMode":mode}
                  for t,speed,mode in values]+[{"t":.5,"stepSeconds":0.,"speed":0.}],
        "metrics":{"elapsedSeconds":.5,"forwardSeconds":.3},
    }


class RecoveryAuditTests(unittest.TestCase):
    def test_phase_partition_and_near_zero_diagnostic(self):
        """Each interval belongs to one phase; near-zero is not a second stop."""
        result = measure_recovery_phases(fixture())
        self.assertAlmostEqual(result["stationarySeconds"], .2)
        self.assertAlmostEqual(result["nearZeroMovingSeconds"], .1)
        self.assertAlmostEqual(result["positiveVelocityDutyRatio"], .6)
        self.assertAlmostEqual(result["atLeastThresholdDutyRatio"], .4)
        self.assertEqual(result["stationaryRuns"], 2)
        self.assertAlmostEqual(result["phases"]["startup-alignment"]["seconds"], .1)
        self.assertAlmostEqual(result["phases"]["local-projection-rejoin"]["stationarySeconds"], .1)

    def test_inconsistent_timing_and_wrong_source_refused(self):
        """Do not silently repair clocks or reinterpret non-rejoin reports."""
        for key, value in (("t",.6), ("speed",float("nan")), ("stepSeconds",0.)):
            report = fixture()
            report["frames"][2][key] = value
            with self.subTest(key=key), self.assertRaises(TraceError):
                measure_recovery_phases(report)
        report = fixture()
        report["metrics"]["forwardSeconds"] = .1
        with self.assertRaises(TraceError):
            measure_recovery_phases(report)
        report = fixture()
        report["model"]["speedPolicy"] = "fixed"
        with self.assertRaises(TraceError):
            measure_recovery_phases(report)

    def test_full_audit_retains_all_cases_and_zigzag_interruptions(self):
        """Pin the observed phase separation on the unchanged recovery model."""
        result = audit_recovery_efficiency()
        self.assertEqual(len(result["cases"]),162)
        self.assertFalse(result["gameInputSent"])
        self.assertFalse(result["liveNavigabilityVerified"])
        zigzag = next(r for r in result["byRoute"] if r["routeId"]=="short-zigzag")
        self.assertAlmostEqual(zigzag["meanStationarySeconds"],2.31)
        self.assertAlmostEqual(zigzag["meanStationarySecondsByPhase"]["local-projection-rejoin"],1.255)
        for row in result["byRoute"]:
            if row["routeId"] != "short-zigzag":
                self.assertEqual(row["meanStationarySecondsByPhase"]["lookahead"],0.)
                self.assertEqual(row["meanStationarySecondsByPhase"]["local-projection-rejoin"],0.)
        for case in result["cases"]:
            self.assertAlmostEqual(case["movingSeconds"]+case["stationarySeconds"],case["elapsedSeconds"])
            self.assertAlmostEqual(case["positiveVelocityDutyRatio"],case["metrics"]["forwardDutyRatio"])


if __name__ == "__main__":
    unittest.main()
