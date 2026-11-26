"""Test independent simulated actuator and prediction models."""
from copy import deepcopy
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.simulation_holdout import _case_trace
from rift_taxi.synthetic_sampled_steering import run, verify, DT
from rift_taxi.synthetic_combined_uncertainty import evaluate


def trace():
    return _case_trace({"routeId":"uncertain-straight-test",
                        "routeXYZ":[[0,0,0],[12,0,0]],
                        "initialXYZ":[0.,0.,.15],"initialYawDegrees":5.})


class CombinedUncertaintyTests(unittest.TestCase):
    def test_unit_gains_and_matched_delay_preserve_report(self):
        source = trace()
        args = dict(delay=3,profile="steady-delay",mode="predict-application")
        self.assertEqual(run(source,**args),
                         run(source,**args,assumed_delay=3,actual_speed_gain=1.,
                             actual_yaw_gain=1.,assumed_speed_gain=1.,assumed_yaw_gain=1.))

    def test_actual_fifo_and_prediction_models_are_independent(self):
        source = trace()
        r = run(source,delay=5,assumed_delay=1,actual_speed_gain=.85,
                actual_yaw_gain=.75,profile="steady-delay",mode="predict-application")
        verify(r,source)
        self.assertEqual(r["actuatorModel"]["assumedDelaySteps"],1)
        self.assertEqual(r["actualDelaySteps"],5)
        frames = r["frames"]
        # First request occurs at capture delivery tick 2. The predictor
        # assumes one step but the plant cannot move until tick 7.
        self.assertTrue(all(f["applied"] == [0.,0.] for f in frames[:7]))
        self.assertEqual(frames[7]["applied"],
                         [frames[2]["requested"][0]*.85,frames[2]["requested"][1]*.75])
        exact = run(source,delay=5,assumed_delay=5,actual_speed_gain=.85,
                    actual_yaw_gain=.75,assumed_speed_gain=.85,assumed_yaw_gain=.75,
                    profile="steady-delay",mode="predict-application")
        self.assertNotEqual(r["frames"],exact["frames"])
        self.assertFalse(r["gameInputSent"])

    def test_metadata_and_applied_motion_tamper_refused(self):
        source = trace()
        r = run(source,delay=3,assumed_delay=1,actual_yaw_gain=.75,
                actual_speed_gain=.85,mode="predict-application")
        for change in (
            lambda a:a["actuatorModel"].__setitem__("actualYawGain",1.),
            lambda a:a["actuatorModel"].__setitem__("assumedDelaySteps",2),
            lambda a:a["actuatorModel"].__setitem__("assumedSpeedGain",1.2),
            lambda a:a["actuatorModel"].__setitem__("actualSpeedGain",float("nan")),
            lambda a:a["frames"][8]["applied"].__setitem__(0,999.),
        ):
            bad = deepcopy(r)
            change(bad)
            with self.assertRaises(TraceError):
                verify(bad,source)

    def test_invalid_estimates_refused(self):
        source = trace()
        for options in ({"assumed_delay": True},{"assumed_delay":11},
                        {"actual_yaw_gain":False},{"actual_speed_gain":.1},
                        {"assumed_yaw_gain":float("inf")},{"assumed_speed_gain":2.}):
            with self.assertRaises(TraceError):
                run(source,mode="predict-application",**options)
        with self.assertRaises(TraceError):
            run(source,mode="held-pose",delay=3,assumed_delay=1)

    def test_fault_stop_preserves_scaled_pending_motion_and_zero_witness(self):
        r = run(trace(),delay=5,assumed_delay=1,actual_speed_gain=1.15,
                actual_yaw_gain=1.25,profile="long-dropout",mode="predict-application")
        self.assertEqual(r["stop"]["reason"],"observation-expired")
        self.assertEqual(len(r["drain"]),6)
        self.assertEqual(r["drain"][-1]["applied"],[0.,0.])
        self.assertFalse(r["summary"]["finalModelSettled"])

    def test_prespecified_combined_study_preserves_all_conditions(self):
        result = evaluate()
        self.assertEqual(result["caseCount"],144)
        self.assertEqual(result["executionCount"],432)
        self.assertEqual(len(result["groups"]),36)
        for group in result["groups"]:
            self.assertTrue(all(s["matchedCases"]==4 for s in group["comparisons"].values()))
        for row in result["rows"]:
            self.assertEqual(row["results"]["nominal-prediction"]["assumedDelaySteps"],3)
            self.assertEqual(row["results"]["nominal-prediction"]["assumedGains"],[1.,1.])
            self.assertEqual(row["results"]["exact-model-reference"]["assumedGains"],row["actualGains"])
            if row["profile"]=="long-dropout":
                self.assertTrue(all(not r["summary"]["finalModelSettled"] for r in row["results"].values()))
        self.assertFalse(result["physicalQualification"])
