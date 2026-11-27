"""Exercise the separate sampled closed loop and its independent audit."""
from copy import deepcopy
from dataclasses import replace
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.simulation_holdout import _case_trace
from rift_taxi.synthetic_sampled_steering import (
    DT, ROUTES, Observation, SampledController, arrival_tick, run, verify, evaluate,
)


def trace():
    return _case_trace({"routeId": "sampled-straight-test",
                        "routeXYZ": [[0,0,0],[12,0,0]],
                        "initialXYZ": [0.,0.,.15], "initialYawDegrees": 5.})


class SampledSteeringTests(unittest.TestCase):
    def test_fresh_straight_route_settles_with_zero_witness(self):
        source = trace()
        for delay in (0,3):
            report = run(source,delay=delay,mode="predict-application")
            self.assertTrue(report["summary"]["finalModelSettled"])
            self.assertEqual(len(report["drain"]), delay+1)
            self.assertEqual(report["drain"][-1]["applied"], [0.,0.])
            self.assertFalse(report["gameInputSent"])

    def test_delayed_controller_has_no_motion_before_delivery(self):
        report = run(trace(),delay=3,profile="steady-delay",mode="predict-application")
        self.assertEqual(report["frames"][0]["requested"], [0.,0.])
        self.assertEqual(report["frames"][1]["requested"], [0.,0.])
        self.assertEqual(report["frames"][2]["controlPose"]["sourceTick"], 0)
        # A request made at tick 2 cannot affect plant motion until tick 5.
        self.assertTrue(all(f["applied"] == [0.,0.] for f in report["frames"][:5]))

    def test_faults_stop_and_drain_without_rearm(self):
        for profile, reason, tick in (
            ("long-dropout","observation-expired",25),
            ("out-of-order","observation-sequence-rollback",23),
            ("stale-stream","initial-observation-timeout",6),
        ):
            with self.subTest(profile=profile):
                report = run(trace(),delay=3,profile=profile,mode="predict-application")
                self.assertEqual(report["stop"]["reason"],reason)
                self.assertEqual(report["stop"]["tick"],tick)
                self.assertFalse(report["summary"]["finalModelSettled"])
                self.assertEqual(len(report["frames"]),tick)
                self.assertEqual(report["drain"][-1]["applied"],[0.,0.])

    def test_source_only_progress_and_prediction(self):
        source = trace()
        c = SampledController(source,3.,100.,0,"predict-application")
        c.observe(Observation(0,(0.,0.,.15),0.),0)
        c.observe(Observation(2,(.2,0.,.15),0.),2)
        self.assertLessEqual(c.progress,.4)
        progress = c.progress
        # Forecast changes reference position but cannot earn arc progress.
        _, ref = c.decide(3,[(3.,0.)]*3)
        self.assertGreater(ref["xyz"][0],.2)
        self.assertEqual(c.progress,progress)

    def test_audit_rejects_truth_forecast_and_fifo_tampering(self):
        source = trace()
        original = run(source,delay=3,profile="steady-delay",mode="predict-application")
        for mutator in (
            lambda r: r["frames"][8]["xyz"].__setitem__(0,999.),
            lambda r: r["frames"][8]["controlPose"]["xyz"].__setitem__(0,999.),
            lambda r: r["frames"][8]["applied"].__setitem__(0,999.),
            lambda r: r["admissions"][2].__setitem__("budget",999.),
            lambda r: r["drain"][-1]["applied"].__setitem__(0,1.),
        ):
            changed = deepcopy(original)
            mutator(changed)
            with self.assertRaises(TraceError):
                verify(changed,source)

    def test_input_and_schedule_bounds(self):
        for kwargs in ({"delay": True},{"delay":11},{"profile":"unknown"},{"mode":"unknown"},{"speed":float("nan")}):
            with self.assertRaises(TraceError):
                run(trace(),**kwargs)
        with self.assertRaises(TraceError):
            run(replace(trace(),source_type="historical"))
        self.assertEqual(arrival_tick(70,"steady-delay"),72)
        self.assertEqual(arrival_tick(70,"long-dropout"),70)
        self.assertEqual(arrival_tick(65,"jitter-in-order"),67)
        self.assertIsNone(arrival_tick(21,"short-dropout"))

    def test_fixed_study_preserves_all_matched_cases(self):
        report = evaluate()
        self.assertEqual(report["caseCount"],56)
        self.assertEqual(report["executionCount"],168)
        self.assertEqual(len(report["groups"]),14)
        for group in report["groups"]:
            for stats in group["comparisons"].values():
                self.assertEqual(stats["matchedCases"],4)
        for row in report["rows"]:
            if row["profile"] in ("long-dropout","out-of-order","stale-stream"):
                self.assertTrue(all(not v["summary"]["finalModelSettled"] for v in row["results"].values()))
