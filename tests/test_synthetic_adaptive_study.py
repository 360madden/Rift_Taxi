"""Verify adaptive study coverage, changing-response transport, and pairing."""
from collections import Counter
from copy import deepcopy
import math
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.simulation_holdout import _case_trace
from rift_taxi.synthetic_sampled_steering import run, verify, DT
from rift_taxi.synthetic_adaptive_study import new_cases, _row, _group, SWITCH_TICK
from rift_taxi.synthetic_response_estimator import ResponseEstimator


def route():
    return _case_trace({"routeId":"variable-gain-test",
                        "routeXYZ":[[0,0,0],[9,0,2],[14,0,6],[23,0,8],[29,0,12]],
                        "initialXYZ":[0.,0.,.1],"initialYawDegrees":-10.})


class AdaptiveStudyTests(unittest.TestCase):
    def test_design_is_crossed_and_has_no_duplicate_conditions(self):
        cases = list(new_cases())
        self.assertEqual(len(cases),192)
        self.assertEqual(sum(c[6] is not None for c in cases),96)
        self.assertEqual(len({(c[0].trace_sha256,c[1],c[2],c[3],c[7]) for c in cases}),192)
        self.assertEqual(Counter(c[7] for c in cases),{
            "steady-delay":48,"jitter-in-order":48,"short-dropout":48,"long-dropout":48})

    def test_switch_affects_applied_motion_not_issued_requests(self):
        trace = route()
        report = run(trace,delay=4,profile="steady-delay",mode="predict-application",
                     adaptive=True,actual_speed_gain=.8,actual_yaw_gain=.7,
                     response_change=(16,1.2,1.3))
        self.assertEqual(report["actualResponseChange"],[16,1.2,1.3])
        self.assertGreater(len(report["frames"]),20)
        for tick in (15,16,17):
            frame = report["frames"][tick]
            requested = report["frames"][tick-4]["requested"]
            gains = (.8,.7) if tick<16 else (1.2,1.3)
            self.assertEqual(frame["applied"],[requested[0]*gains[0],requested[1]*gains[1]])
        verify(report,trace)
        changed = deepcopy(report)
        changed["actualResponseChange"][0]=17
        with self.assertRaises(TraceError):
            verify(changed,trace)

    def test_switch_during_stop_drain_uses_application_tick(self):
        trace=route()
        # Long dropout stops the approach at tick 25. With a five-step
        # delay, its pending requests cross the plant's tick-27 switch.
        report=run(trace,delay=5,profile="long-dropout",mode="predict-application",
                   adaptive=True,actual_speed_gain=.8,actual_yaw_gain=.7,
                   response_change=(27,1.2,1.3))
        self.assertEqual(report["stop"]["reason"],"observation-expired")
        self.assertEqual(report["stop"]["tick"],25)
        self.assertEqual(len(report["drain"]),6)
        for j,frame in enumerate(report["drain"][:-1]):
            requested=report["frames"][20+j]["requested"]
            gains=(.8,.7) if j<2 else (1.2,1.3)
            self.assertEqual(frame["applied"],[requested[0]*gains[0],requested[1]*gains[1]])
        self.assertEqual(report["drain"][-1]["applied"],[0.,0.])
        self.assertFalse(report["summary"]["finalModelSettled"])

    def test_invalid_change_declarations_fail_closed(self):
        trace=route()
        for change in ((0,1.,1.),(True,1.,1.),(651,1.,1.),(2,.1,1.),
                       (3,1.,float("nan")),(2,1.),"change"):
            with self.subTest(change=change),self.assertRaises(TraceError):
                run(trace,mode="predict-application",adaptive=True,response_change=change)

    def test_constant_response_legacy_report_preserved(self):
        trace=route()
        opts=dict(delay=3,profile="steady-delay",mode="predict-application")
        self.assertEqual(run(trace,**opts),run(trace,response_change=None,**opts))
        self.assertNotIn("actualResponseChange",run(trace,**opts))
        self.assertNotIn("adaptiveResponse",run(trace,**opts))

    def test_step_response_is_relearned_from_source_data(self):
        # An explicitly excited synthetic actuator is independent of the
        # steering experiment. Old fits must eventually yield to a new
        # identifiable gain model after the rolling window has moved.
        estimator=ResponseEstimator()
        requests=[(1.+((i*i+3*i)%13)/5.,((i*i*7+11*i)%31-15)*4.) for i in range(170)]
        delay=4
        xyz,yaw=(0.,0.,0.),0.
        estimator.observe(0,xyz,yaw,0,[])
        for tick in range(144):
            v,r=requests[tick-delay] if tick>=delay else (0.,0.)
            gv,gr=(.8,.7) if tick<64 else (1.2,1.3)
            v,r=v*gv,r*gr
            mid=math.radians(yaw+r*DT/2.)
            xyz=(xyz[0]+v*DT*math.cos(mid),0.,xyz[2]+v*DT*math.sin(mid))
            yaw=(yaw+r*DT+180.)%360.-180.
            estimator.observe(tick+1,xyz,yaw,tick+1,requests[:tick+1])
            if tick==51:
                fit=estimator.estimate(tick+1)
                self.assertTrue(fit["qualified"])
                self.assertEqual(fit["delay"],delay)
                self.assertAlmostEqual(fit["speedGain"],.8)
                self.assertAlmostEqual(fit["yawGain"],.7)
        fit=estimator.estimate(144)
        self.assertTrue(fit["qualified"])
        self.assertEqual(fit["delay"],delay)
        self.assertAlmostEqual(fit["speedGain"],1.2)
        self.assertAlmostEqual(fit["yawGain"],1.3)

    def test_report_counts_faults_and_never_censors_failed_rows(self):
        cases=list(new_cases())
        selected=[cases[0],cases[3],next(c for c in cases if c[6] is not None)]
        rows=[_row(c,"fixture") for c in selected]
        summary=_group(rows)
        self.assertEqual(summary["conditions"],3)
        self.assertEqual(summary["usable"],2)
        self.assertEqual(summary["faultCases"],1)
        self.assertEqual(summary["faultExpiries"],1)
        self.assertEqual(summary["comparison"]["matchedCases"],2)
        self.assertEqual(rows[1]["results"]["adaptive"]["stop"]["reason"],"observation-expired")
        self.assertTrue(all(r["responseChange"] is None or r["responseChange"][0]==SWITCH_TICK for r in rows))
