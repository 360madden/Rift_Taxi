"""Bounded synthetic corner certificate and integration regressions."""
from copy import deepcopy
import math
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.synthetic_corner_certificate import (
    AXIS_ERROR_BOUND, worst_case_distance_xz, certified_corner,
)
from rift_taxi.synthetic_sampled_steering import run, verify
from rift_taxi.synthetic_sensor_noise import PROFILES, measurement
from rift_taxi.synthetic_robust_study import cases
from rift_taxi.synthetic_corner_study import new_cases


def adverse_cases():
    wanted={(2.5,1,"fixed-cross","moderate","jitter-in-order"),
            (2.5,1,"fixed-cross","impulse","steady-delay"),
            (3.4,7,"slow-to-fast","moderate","jitter-in-order")}
    return [c for c in cases() if c[0].route_id=="sharp-offset"
            and (c[1],c[2],c[3],c[7],c[8]) in wanted]


def simulate(case,policy="bounded"):
    t,s,d,g,v,y,ch,n,p=case
    return run(t,speed=s,delay=d,profile=p,mode="predict-application",
               actual_speed_gain=v,actual_yaw_gain=y,response_change=ch,
               sensor_noise=n,adaptive=True,adaptive_policy="robust",
               corner_policy=policy)


class CornerCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=adverse_cases()
        cls.reports=[simulate(c) for c in cls.cases]

    def test_closed_form_matches_all_rectangle_vertices(self):
        for x in (-.4,-.08,0.,.04,.3):
            for z in (-.2,0.,.13):
                expect=max(math.hypot(x+sx*AXIS_ERROR_BOUND,z+sz*AXIS_ERROR_BOUND)
                           for sx in (-1,1) for sz in (-1,1))
                self.assertAlmostEqual(worst_case_distance_xz((x,5.,z),(0.,0.,0.)),expect)
        self.assertAlmostEqual(worst_case_distance_xz((3,0,4),(0,0,0),0),5.)

    def test_near_boundary_and_impossible_radius(self):
        self.assertTrue(certified_corner((0.,0.,0.),(0.,0.,0.),.15))
        self.assertFalse(certified_corner((.14,0.,0.),(0.,0.,0.),.15))
        self.assertFalse(certified_corner((0.,0.,0.),(0.,0.,0.),.10))

    def test_invalid_geometry_or_bound_rejected(self):
        for args in ((None,(0,0,0)),((0,0),(0,0,0)),
                     ((True,0,0),(0,0,0)),((float("nan"),0,0),(0,0,0)),
                     ((0,0,0),(0,0,0),float("inf")),((0,0,0),(0,0,0),True),
                     ((0,0,0),(0,0,0),-.01),((10**1000,0,0),(0,0,0))):
            with self.assertRaises(TraceError):
                worst_case_distance_xz(*args)
        for radius in (0.,-1.,float("nan"),True,2.):
            with self.assertRaises(TraceError):
                certified_corner((0,0,0),(0,0,0),radius)

    def test_fixed_bound_covers_every_supported_fixture_tick(self):
        for profile in PROFILES:
            for tick in range(651):
                truth=(4.5,0.,-7.2)
                p,_=measurement(tick,truth,179.,profile)
                self.assertLessEqual(abs(p[0]-truth[0]),AXIS_ERROR_BOUND+1e-12)
                self.assertLessEqual(abs(p[2]-truth[2]),AXIS_ERROR_BOUND+1e-12)

    def test_targeted_cases_recover_and_preserve_original_radius(self):
        self.assertEqual(len(self.reports),3)
        for case,r in zip(self.cases,self.reports):
            self.assertTrue(r["summary"]["finalModelSettled"])
            self.assertTrue(r["summary"]["truthSharpWitnessesValid"])
            self.assertGreaterEqual(len(r["sharpWitnesses"]),2)
            self.assertFalse(r["gameInputSent"])
            self.assertFalse(r["physicalQualification"])
            for w in r["sharpWitnesses"]:
                self.assertEqual(w["radiusXZ"],.15)
                self.assertLessEqual(w["upperDistanceXZ"],w["radiusXZ"])
            verify(r,case[0])

    def test_tampered_certificate_and_declaration_refused(self):
        for mutate in (lambda a:a["cornerPolicy"].__setitem__("axisErrorBound",.015),
                       lambda a:a["sharpWitnesses"][0].__setitem__("radiusXZ",.3),
                       lambda a:a["sharpWitnesses"][0].__setitem__("upperDistanceXZ",0.),
                       lambda a:a["sharpWitnesses"][0].__setitem__("captureTick",0),
                       lambda a:a["summary"].__setitem__("maxSharpWitnessTruthErrorXZ",999.)):
            bad=deepcopy(self.reports[0])
            mutate(bad)
            with self.assertRaises(TraceError):
                verify(bad,self.cases[0][0])

    def test_dropout_expiry_and_zero_drain_preserved(self):
        c=next(c for c in cases() if c[0].route_id=="sharp-offset" and c[8]=="long-dropout")
        r=simulate(c)
        self.assertEqual(r["stop"]["reason"],"observation-expired")
        self.assertEqual(len(r["drain"]),c[2]+1)
        self.assertEqual(r["drain"][-1]["applied"],[0.,0.])
        self.assertFalse(r["summary"]["finalModelSettled"])

    def test_original_policy_default_unchanged(self):
        t=self.cases[0][0]
        opts=dict(delay=2,mode="predict-application")
        self.assertEqual(run(t,**opts),run(t,corner_policy="legacy",**opts))
        self.assertNotIn("cornerPolicy",run(t,**opts))
        with self.assertRaises(TraceError):
            run(t,corner_policy="unknown",**opts)

    def test_new_cohort_design_is_distinct_and_complete(self):
        fresh=list(new_cases())
        self.assertEqual(len(fresh),96)
        self.assertEqual(sum(c[8]=="long-dropout" for c in fresh),32)
        self.assertTrue({c[0].trace_sha256 for c in fresh}.isdisjoint(
                        {c[0].trace_sha256 for c in cases()}))
