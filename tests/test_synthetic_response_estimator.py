"""Source-only response estimation, confidence, expiry, and integration."""
from copy import deepcopy
import math
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.simulation_holdout import _case_trace
from rift_taxi.synthetic_response_estimator import (
    ResponseEstimator, fit_response, NOMINAL, WINDOW, HOLD_TICKS, DT,
)
from rift_taxi.synthetic_sampled_steering import run, verify


def commands(n=60):
    # Repeatable, varying non-periodic excitation across both channels.
    return [(1.+((i*i+3*i)%13)/5., ((i*i*7+11*i)%31-15)*4.) for i in range(n)]


def observed_pairs(req, delay, vg, yg, start=0, end=40):
    return [(i, (req[i-delay][0]*vg if i>=delay else 0.),
             (req[i-delay][1]*yg if i>=delay else 0.)) for i in range(start,end)]


def source():
    return _case_trace({"routeId":"adaptive-test",
                        "routeXYZ":[[0,0,0],[5,0,2],[9,0,5],[13,0,4],[20,0,8]],
                        "initialXYZ":[0.,0.,.2],"initialYawDegrees":-15.})


class ResponseEstimatorTests(unittest.TestCase):
    def test_exact_bounded_fit_recovers_delays_and_gains(self):
        req = commands()
        for delay, vg, yg in ((0,1.,1.),(1,.85,.75),(5,1.15,1.25),(10,.5,1.5)):
            fit = fit_response(observed_pairs(req,delay,vg,yg),req)
            self.assertIsNotNone(fit)
            self.assertEqual(fit.delay,delay)
            self.assertAlmostEqual(fit.speed_gain,vg)
            self.assertAlmostEqual(fit.yaw_gain,yg)
            self.assertLess(fit.score,1e-12)

    def test_unexcited_and_ambiguous_commands_are_not_identifiable(self):
        req = [(2.,20.)]*60
        self.assertIsNone(fit_response(observed_pairs(req,3,1.,1.,start=12),req))
        req = [(2.,0.)]*60
        self.assertIsNone(fit_response(observed_pairs(req,3,1.,1.),req))
        self.assertIsNone(fit_response([],req))

    def test_causal_source_only_and_expiry(self):
        req = commands()
        estimator = ResponseEstimator()
        xyz, yaw = (0.,0.,0.), 0.
        estimator.observe(0,xyz,yaw,2,req[:2])
        for tick,velocity,rate in observed_pairs(req,5,.85,.75):
            mid = math.radians(yaw+rate*DT/2)
            xyz = (xyz[0]+velocity*DT*math.cos(mid),0.,xyz[2]+velocity*DT*math.sin(mid))
            yaw = (yaw+rate*DT+180.)%360.-180.
            capture = tick+1
            estimator.observe(capture,xyz,yaw,capture+2,req[:capture+2])
        result = estimator.estimate(42)
        self.assertTrue(result["qualified"])
        self.assertEqual(result["delay"],5)
        self.assertAlmostEqual(result["speedGain"],.85)
        self.assertAlmostEqual(result["yawGain"],.75)
        expired = estimator.estimate(result["fitCaptureTick"]+HOLD_TICKS+1)
        self.assertFalse(expired["qualified"])
        self.assertEqual((expired["delay"],expired["speedGain"],expired["yawGain"]),NOMINAL)

    def test_gap_is_not_treated_as_one_step(self):
        e = ResponseEstimator()
        e.observe(0,(0.,0.,0.),0.,0,[])
        e.observe(3,(1.,0.,0.),20.,3,[(2.,20.)]*3)
        self.assertEqual(e.accepted_pairs,0)
        e.observe(4,(1.1,0.,0.),21.,4,[(2.,20.)]*4)
        self.assertEqual(e.accepted_pairs,1)
        self.assertFalse(e.estimate(4)["qualified"])

    def test_invalid_or_future_epochs_and_nonfinite_inputs_refused(self):
        e = ResponseEstimator()
        for args in ((1,(0.,0.,0.),0.,0,[]),
                     (0,(0.,0.,0.),float("nan"),0,[]),
                     (0,(True,0.,0.),0.,0,[]),
                     (0,(0.,0.,0.),0.,1,[])):
            with self.assertRaises(TraceError):
                e.observe(*args)
        e.observe(0,(0.,0.,0.),0.,2,[(0.,0.)]*2)
        with self.assertRaises(TraceError):
            e.estimate(1)
        with self.assertRaises(TraceError):
            e.observe(1,(0.,0.,0.),0.,1,[(0.,0.)])
        with self.assertRaises(TraceError):
            fit_response([(60,1.,2.)],commands())
        with self.assertRaises(TraceError):
            fit_response([(i,1.,2.) for i in range(WINDOW+1)],commands())

    def test_integrated_fit_and_audit_tampering(self):
        s = source()
        r = run(s,delay=5,actual_speed_gain=.85,actual_yaw_gain=.75,
                profile="steady-delay",mode="predict-application",adaptive=True)
        self.assertTrue(r["adaptiveResponse"])
        self.assertFalse(r["frames"][0]["responseEstimate"]["qualified"])
        qualified = [f["responseEstimate"] for f in r["frames"] if f["responseEstimate"]["qualified"]]
        self.assertTrue(qualified)
        self.assertTrue(any(f["delay"]==5 for f in qualified))
        verify(r,s)
        bad = deepcopy(r)
        bad["frames"][8]["responseEstimate"]["delay"] = 7
        with self.assertRaises(TraceError):
            verify(bad,s)
        self.assertFalse(r["gameInputSent"])

    def test_adaptive_starts_nominal_and_never_rearms_after_dropout(self):
        r = run(source(),delay=5,actual_speed_gain=1.15,actual_yaw_gain=1.25,
                profile="long-dropout",mode="predict-application",adaptive=True)
        self.assertEqual(r["actuatorModel"]["assumedDelaySteps"],3)
        self.assertEqual(r["stop"]["reason"],"observation-expired")
        self.assertFalse(r["summary"]["finalModelSettled"])
        with self.assertRaises(TraceError):
            run(source(),mode="held-pose",adaptive=True)
        with self.assertRaises(TraceError):
            run(source(),mode="predict-application",adaptive=True,assumed_delay=5)
