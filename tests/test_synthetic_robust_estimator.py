"""Regressions for robust causal response fitting and noisy plant separation."""
from copy import deepcopy
import math
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.simulation_holdout import _case_trace
from rift_taxi.steering import _angle_delta
from rift_taxi.synthetic_response_estimator import NOMINAL, DT
from rift_taxi.synthetic_response_estimator_v2 import (
    RobustResponseEstimator, fit_robust, HOLD_TICKS, WINDOW,
)
from rift_taxi.synthetic_sensor_noise import measurement, BOUNDS, PROFILES
from rift_taxi.synthetic_sampled_steering import run, verify


def requests(n=200):
    return [(1.+((i*i+3*i)%13)/5.,((i*i*7+11*i)%31-15)*4.) for i in range(n)]


def trace():
    return _case_trace({"routeId":"robust-response-test",
        "routeXYZ":[[0,0,0],[5,0,2],[9,0,5],[13,0,4],[20,0,8]],
        "initialXYZ":[0.,0.,.2],"initialYawDegrees":-15.})


def feed(profile="none", change=True):
    """Independent excited fixture; measured samples never alter plant truth."""
    history=requests()
    e=RobustResponseEstimator()
    xyz,yaw=(0.,0.,0.),0.
    observed=measurement(0,xyz,yaw,profile)
    e.observe(0,*observed,2,history[:2])
    fits=[]
    for tick in range(144):
        v,r=history[tick-5] if tick>=5 else (0.,0.)
        gv,gr=(1.2,1.3) if change and tick>=64 else (.8,.7)
        v,r=v*gv,r*gr
        mid=math.radians(yaw+r*DT/2.)
        xyz=(xyz[0]+v*DT*math.cos(mid),0.,xyz[2]+v*DT*math.sin(mid))
        yaw=_angle_delta(yaw+r*DT,0.)
        capture=tick+1
        observed=measurement(capture,xyz,yaw,profile)
        e.observe(capture,*observed,capture+2,history[:capture+2])
        fits.append(e.estimate(capture+2))
    return e,fits


class RobustEstimatorTests(unittest.TestCase):
    def test_exact_fit_recovers_delay_and_gain(self):
        history=requests()
        for delay in (0,5,10):
            pairs=[(i,history[i-delay][0]*.85 if i>=delay else 0.,
                       history[i-delay][1]*1.25 if i>=delay else 0.)
                   for i in range(WINDOW)]
            fit=fit_robust(pairs,history)
            self.assertIsNotNone(fit)
            self.assertEqual(fit.delay,delay)
            self.assertAlmostEqual(fit.speed_gain,.85)
            self.assertAlmostEqual(fit.yaw_gain,1.25)

    def test_unexcited_delay_and_turn_rejected(self):
        for command in ((2.,20.),(2.,0.),(0.,20.)):
            history=[command]*80
            pairs=[(i,*command) for i in range(20,20+WINDOW)]
            self.assertIsNone(fit_robust(pairs,history))

    def test_missing_captures_cannot_create_single_step_increments(self):
        e=RobustResponseEstimator()
        e.observe(0,(0.,0.,0.),0.,0,[])
        e.observe(3,(1.,0.,0.),20.,3,requests()[:3])
        self.assertEqual(e.accepted_pairs,0)
        e.observe(4,(1.1,0.,0.),21.,4,requests()[:4])
        self.assertEqual(e.accepted_pairs,1)
        self.assertFalse(e.estimate(4)["qualified"])

    def test_change_invalidates_fit_and_relearns(self):
        e,fits=feed()
        self.assertTrue(fits[50]["qualified"])
        self.assertEqual(fits[50]["delay"],5)
        self.assertAlmostEqual(fits[50]["speedGain"],.8)
        self.assertGreater(e.change_resets,0)
        self.assertTrue(any(not f["qualified"] for f in fits[64:96]))
        self.assertTrue(fits[-1]["qualified"])
        self.assertEqual(fits[-1]["delay"],5)
        self.assertAlmostEqual(fits[-1]["speedGain"],1.2)
        self.assertAlmostEqual(fits[-1]["yawGain"],1.3)
        expired=e.estimate(fits[-1]["fitCaptureTick"]+HOLD_TICKS+1)
        self.assertFalse(expired["qualified"])
        self.assertEqual((expired["delay"],expired["speedGain"],expired["yawGain"]),NOMINAL)

    def test_moderate_noise_recovers_fixed_model(self):
        e,fits=feed("moderate",change=False)
        last=fits[-1]
        self.assertTrue(last["qualified"])
        self.assertEqual(last["delay"],5)
        self.assertAlmostEqual(last["speedGain"],.8,delta=.06)
        self.assertAlmostEqual(last["yawGain"],.7,delta=.06)

    def test_invalid_time_and_history_refused(self):
        e=RobustResponseEstimator()
        for args in ((1,(0.,0.,0.),0.,0,[]),(0,(0.,0.,0.),float("nan"),0,[]),
                     (0,(True,0.,0.),0.,0,[]),(0,(0.,0.,0.),0.,1,[])):
            with self.assertRaises(TraceError):
                e.observe(*args)
        e.observe(0,(0.,0.,0.),0.,2,requests()[:2])
        with self.assertRaises(TraceError):
            e.estimate(1)
        with self.assertRaises(TraceError):
            e.observe(1,(0.,0.,0.),0.,1,requests()[:1])

    def test_noise_is_bounded_deterministic_and_wraps(self):
        for profile in PROFILES:
            for tick in (0,13,29,42,640):
                a=measurement(tick,(1.,2.,3.),179.9,profile)
                self.assertEqual(a,measurement(tick,(1.,2.,3.),179.9,profile))
                pos,yaw=a
                bound,angle=BOUNDS[profile]
                if profile=="impulse" and tick%29==13:
                    bound,angle=.08,3.
                self.assertLessEqual(abs(pos[0]-1.),bound+1e-12)
                self.assertLessEqual(abs(pos[2]-3.),bound+1e-12)
                self.assertEqual(pos[1],2.)
                self.assertLessEqual(abs(_angle_delta(yaw,179.9)),angle+1e-12)
                self.assertTrue(-180.<=yaw<180.)

    def test_noisy_closed_loop_and_audited_truth(self):
        t=trace()
        opts=dict(delay=5,mode="predict-application",adaptive=True,
                  adaptive_policy="robust",sensor_noise="moderate",
                  actual_speed_gain=.85,actual_yaw_gain=.75,profile="steady-delay")
        r=run(t,**opts)
        self.assertEqual(r["adaptivePolicy"],"robust")
        self.assertEqual(r["sensorNoise"],"moderate")
        self.assertIn("truthSharpWitnessesValid",r["summary"])
        self.assertFalse(r["gameInputSent"])
        verify(r,t)
        for mutate in (lambda a:a.__setitem__("sensorNoise","mild"),
                       lambda a:a["frames"][15]["responseEstimate"].__setitem__("delay",10),
                       lambda a:a["summary"].__setitem__("maxSharpWitnessTruthErrorXZ",999.)):
            bad=deepcopy(r)
            mutate(bad)
            with self.assertRaises(TraceError):
                verify(bad,t)

    def test_noise_fault_still_expires_and_drains(self):
        r=run(trace(),delay=5,mode="predict-application",adaptive=True,
              adaptive_policy="robust",sensor_noise="impulse",profile="long-dropout")
        self.assertEqual(r["stop"]["reason"],"observation-expired")
        self.assertEqual(len(r["drain"]),6)
        self.assertEqual(r["drain"][-1]["applied"],[0.,0.])
        self.assertFalse(r["summary"]["finalModelSettled"])

    def test_legacy_default_is_identical_and_new_mode_explicit(self):
        t=trace()
        opts=dict(delay=3,mode="predict-application",adaptive=True)
        self.assertEqual(run(t,**opts),run(t,adaptive_policy="legacy",sensor_noise="none",**opts))
        with self.assertRaises(TraceError):
            run(t,adaptive_policy="robust")
        with self.assertRaises(TraceError):
            run(t,sensor_noise="unknown")
