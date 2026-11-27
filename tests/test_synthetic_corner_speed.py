"""Regressions for the tapered speed cap and unchanged corner certificate."""
from copy import deepcopy
from pathlib import Path
import math
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.synthetic_corner_speed import BASE_GAIN, EXTRA_GAIN, KNEE_XZ, tapered_corner_cap
from rift_taxi.synthetic_corner_speed_study import (
    fresh_cases, previous_design, identity, key, load_baseline, simulate,
)
from rift_taxi.synthetic_sampled_steering import run, verify
from rift_taxi.synthetic_robust_study import cases


def target_case():
    return next(c for c in cases() if c[0].route_id=="sharp-offset"
                and (c[1],c[2],c[3],c[7],c[8])==
                    (2.5,1,"fixed-cross","moderate","jitter-in-order"))


def report(case,policy):
    t,s,d,g,v,y,ch,n,p=case
    return run(t,speed=s,delay=d,profile=p,mode="predict-application",
               actual_speed_gain=v,actual_yaw_gain=y,response_change=ch,
               sensor_noise=n,adaptive=True,adaptive_policy="robust",corner_policy=policy)


class CornerSpeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case=target_case()
        cls.taper=report(cls.case,"bounded-taper")

    def test_same_near_corner_cap(self):
        for d in (0.,.001,.05,.1,.249,KNEE_XZ):
            self.assertEqual(tapered_corner_cap(d),BASE_GAIN*d)

    def test_continuous_monotone_far_corner_cap(self):
        vals=[tapered_corner_cap(i/100.) for i in range(151)]
        self.assertEqual(vals,sorted(vals))
        self.assertAlmostEqual(tapered_corner_cap(.5),3.)
        self.assertAlmostEqual(tapered_corner_cap(1.),7.)
        self.assertAlmostEqual(tapered_corner_cap(KNEE_XZ+1e-8),BASE_GAIN*KNEE_XZ,places=6)

    def test_invalid_chords_rejected(self):
        for v in (True,None,".1",-1.,float("inf"),float("nan"),10**1000):
            with self.assertRaises(TraceError):
                tapered_corner_cap(v)

    def test_certificate_and_arrival_unchanged(self):
        r=self.taper
        self.assertEqual(r["cornerPolicy"],{"name":"bounded-taper","axisErrorBound":.08,
                         "approachGainPerSecond":4.,"extraGainPerSecond":4.,"kneeXZ":.25})
        self.assertTrue(r["summary"]["truthSharpWitnessesValid"])
        self.assertGreaterEqual(len(r["sharpWitnesses"]),2)
        self.assertTrue(all(w["radiusXZ"]==.15 and w["upperDistanceXZ"]<=.15
                            for w in r["sharpWitnesses"]))
        self.assertFalse(r["gameInputSent"])
        self.assertFalse(r["physicalQualification"])
        verify(r,self.case[0])

    def test_tampered_policy_and_target_refused(self):
        r=deepcopy(self.taper)
        r["cornerPolicy"]["kneeXZ"]=.1
        with self.assertRaises(TraceError):
            verify(r,self.case[0])
        r=deepcopy(self.taper)
        f=next(f for f in r["frames"] if f["controlPose"] is not None)
        f["controlPose"]["targetXYZ"][0]+=1.
        with self.assertRaises(TraceError):
            verify(r,self.case[0])

    def test_fault_expiry_and_terminal_zero_witness(self):
        c=next(c for c in cases() if c[8]=="long-dropout" and c[2]==7)
        r=report(c,"bounded-taper")
        self.assertEqual(r["stop"]["reason"],"observation-expired")
        self.assertEqual(len(r["drain"]),c[2]+1)
        self.assertEqual(r["drain"][-1]["applied"],[0.,0.])
        self.assertFalse(r["summary"]["finalModelSettled"])

    def test_prespecified_design_unique(self):
        old=[key(identity(c)) for _,c in previous_design()]
        fresh=[key(identity(c)) for c in fresh_cases()]
        self.assertEqual(len(old),192)
        self.assertEqual(len(fresh),48)
        self.assertEqual(len(set(old+fresh)),240)
        self.assertEqual(sum(c[8]=="long-dropout" for c in fresh_cases()),16)

    def test_bad_archive_refused(self):
        with self.assertRaises(TraceError):
            load_baseline(b'{}')

    def test_original_bounded_policy_has_original_receipt_shape(self):
        r=report(self.case,"bounded")
        self.assertEqual(r["cornerPolicy"],{"name":"bounded","axisErrorBound":.08,
                                            "approachGainPerSecond":4.})
        verify(r,self.case[0])
