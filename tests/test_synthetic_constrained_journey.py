"""Synthetic constrained journey regression, no live or historical inputs."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
import io

from rift_taxi.contracts import TraceError,load_trace
from rift_taxi.synthetic_route_constraints import SCHEMA
from rift_taxi.synthetic_constrained_journey import run_constrained_journey,main


def fixture(root,*,narrow=False):
    points=[("start","guide",[0,0,0]),("pass-one","mandatory_passage",[2,0,0]),
            ("rest","hard_stop",[4,0,0]),("hint","optional",[5,0,0]),
            ("pass-two","mandatory_passage",[6,0,0]),("goal","destination",[8,0,0])]
    doc={"schema":"taxi.motion-trace/1","sourceType":"synthetic",
         "source":{"generator":"constrained-straight-fixture"},
         "frame":{"frameId":"synthetic-local-xyz","axisOrder":["x","y","z"],
                  "upAxis":"y","units":"synthetic-units"},
         "route":{"id":"constrained-straight","arrivalToleranceXZ":.3,
                  "points":[{"name":n,"kind":k,"xyz":v} for n,k,v in points]},
         "movementWindow":[0,1],"poses":[{"t":0,"xyz":[0,0,0],"actorYawDeg":0},
                                         {"t":1,"xyz":[0,0,0],"actorYawDeg":0}],
         "events":[]}
    path=root/"trace.json"
    path.write_text(json.dumps(doc),encoding="utf-8")
    trace=load_trace(path)
    # Narrow first region is deliberately between nominal .3-unit samples.
    half=.001 if narrow else .5
    policy={"schema":SCHEMA,"traceSHA256":trace.trace_sha256,
            "maxSampleGapSeconds":.15,"stopDwellSeconds":.4,"stopYTolerance":.1,
            "passageRegions":[{"pointIndex":1,"minXYZ":[2-half,-.1,-.5],
                               "maxXYZ":[2+half,.1,.5]},
                              {"pointIndex":4,"minXYZ":[5.5,-.1,-.5],
                               "maxXYZ":[6.5,.1,.5]}]}
    return path,trace,policy


class ConstrainedJourneyTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)

    def test_two_legs_with_dwell_and_actual_pose_carryover(self):
        _,trace,policy=fixture(self.root)
        report=run_constrained_journey(trace,policy)
        self.assertTrue(report["allObligationsObserved"],report["status"])
        self.assertEqual(report["plannedLegs"],2)
        self.assertEqual(report["completedLegs"],2)
        self.assertEqual([r["kind"] for r in report["obligations"]],
                         ["mandatory_passage","hard_stop","mandatory_passage","destination"])
        a,b=report["legs"]
        self.assertEqual(a["finalXYZ"],b["initialXYZ"])
        self.assertEqual(a["finalYawDegrees"],b["initialYawDegrees"])
        self.assertNotEqual(a["finalXYZ"],list(trace.points[2].xyz))
        self.assertEqual(a["endSeconds"],b["startSeconds"])
        for leg in report["legs"]:
            self.assertTrue(leg["legAccepted"])
            self.assertEqual(len(leg["dwellFrames"]),4)
            self.assertTrue(all(f["appliedSpeed"]==0. and f["appliedYawRateDegreesPerSecond"]==0.
                                for f in leg["dwellFrames"]))
            self.assertGreaterEqual(leg["obligationAudit"]["obligations"][-1]["witness"]["durationSeconds"]+1e-12,.4)
            # Mandatory passages were observed in the moving approach,
            # rather than a forced stop or terminal correction.
            passage=leg["obligationAudit"]["obligations"][0]["witness"]
            frame=leg["journey"]["approach"]["frames"][passage["sampleIndex"]]
            self.assertGreater(frame["speed"],0.)
        self.assertGreater(report["totalElapsedSeconds"],0.)
        self.assertLess(report["totalForwardDutyRatio"],1.)
        self.assertFalse(report["physicalQualification"])
        self.assertFalse(report["gameInputSent"])
        self.assertFalse(report["continuousStationarityVerified"])

    def test_delayed_legs_use_settled_drain_and_deterministic_reports(self):
        _,trace,policy=fixture(self.root)
        a=run_constrained_journey(trace,policy,delay_steps=2)
        b=run_constrained_journey(trace,policy,delay_steps=2)
        self.assertEqual(a,b)
        self.assertTrue(a["allObligationsObserved"],a["status"])
        for leg in a["legs"]:
            self.assertGreater(leg["journey"]["passiveDrain"]["queueDrainSeconds"],0.)
            self.assertTrue(leg["journey"]["summary"]["finalModelSettled"])
            self.assertEqual(leg["obligationAudit"]["sampleEvidenceBasis"],"applied-ideal-model-commands")
        self.assertEqual(a["legs"][0]["finalXYZ"],a["legs"][1]["initialXYZ"])

    def test_missed_mandatory_region_prevents_next_leg(self):
        _,trace,policy=fixture(self.root,narrow=True)
        report=run_constrained_journey(trace,policy)
        self.assertEqual(report["status"],"constraint-not-observed")
        self.assertEqual(report["completedLegs"],0)
        self.assertEqual(len(report["legs"]),1)
        self.assertTrue(report["legs"][0]["journey"]["summary"]["finalModelSettled"])
        self.assertEqual(report["obligations"][0]["status"],"not-observed")
        self.assertEqual(report["obligations"][2]["status"],"not-attempted")
        self.assertFalse(report["allObligationsObserved"])

    def test_approach_failure_does_not_start_next_leg_or_fake_dwell(self):
        _,trace,policy=fixture(self.root)
        report=run_constrained_journey(trace,policy,approach_budget=.2)
        self.assertEqual(report["status"],"approach-failed")
        self.assertEqual(len(report["legs"]),1)
        self.assertEqual(report["legs"][0]["dwellFrames"],[])
        self.assertFalse(report["allObligationsObserved"])

    def test_model_limits_and_policy_mismatches_refuse(self):
        _,trace,policy=fixture(self.root)
        for kwargs in ({"dt":.2},{"delay_steps":True},{"speed":float("nan")},{"terminal_budget":6.}):
            with self.subTest(kwargs=kwargs),self.assertRaises(TraceError):
                run_constrained_journey(trace,policy,**kwargs)
        with self.assertRaises(TraceError):
            run_constrained_journey(replace(trace,source_type="historical"),policy)
        bad=deepcopy(policy)
        bad["traceSHA256"]="0"*64
        with self.assertRaises(TraceError):
            run_constrained_journey(trace,bad)

    def test_seed_and_later_observations_remain_distinct(self):
        _,trace,policy=fixture(self.root)
        # Source trace observations are not used to manufacture success.
        changed=replace(trace,poses=(trace.poses[0],replace(trace.poses[-1],xyz=(900.,0.,900.))))
        self.assertEqual(run_constrained_journey(trace,policy),
                         run_constrained_journey(changed,policy))

    def test_invalid_stop_geometry_refused_before_execution(self):
        _,trace,policy=fixture(self.root)
        points=list(trace.points)
        points[2]=replace(points[2],xyz=points[1].xyz)
        with self.assertRaisesRegex(TraceError,"degenerate"):
            run_constrained_journey(replace(trace,points=tuple(points)),policy)

    def test_cli_preserves_failed_receipt_and_exclusive_output(self):
        path,_,policy=fixture(self.root,narrow=True)
        pol=self.root/"policy.json"
        pol.write_text(json.dumps(policy),encoding="utf-8")
        out=self.root/"report.json"
        args=[str(path),str(pol),"--out",str(out),"--require-observed"]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args),1)
        raw=out.read_bytes()
        report=json.loads(raw)
        self.assertFalse(report["allObligationsObserved"])
        self.assertEqual(report["policySHA256"],hashlib.sha256(pol.read_bytes()).hexdigest())
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as caught:
            main(args)
        self.assertEqual(caught.exception.code,2)
        self.assertEqual(out.read_bytes(),raw)
