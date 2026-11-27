"""Independent saved constrained receipt verification, synthetic only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
import io

from rift_taxi.contracts import TraceError
from rift_taxi.synthetic_constrained_journey import run_constrained_journey
from rift_taxi.synthetic_constrained_audit import verify_constrained_report,audit_saved,main
from test_synthetic_constrained_journey import fixture


class ConstrainedAuditTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.path,self.trace,self.policy=fixture(self.root)
        self.good=run_constrained_journey(self.trace,self.policy,delay_steps=2)

    def verify(self,report):
        return verify_constrained_report(report,self.trace,self.policy)

    def test_valid_reports_and_failed_outcomes(self):
        for report in (self.good,run_constrained_journey(self.trace,self.policy),
                       run_constrained_journey(self.trace,self.policy,approach_budget=.2)):
            original=deepcopy(report)
            result=self.verify(report)
            self.assertEqual(result["allObligationsObserved"],report["allObligationsObserved"])
            self.assertTrue(result["poseCarryoverVerified"])
            self.assertFalse(result["approachControllerReexecuted"])
            self.assertFalse(result["physicalQualification"])
            self.assertEqual(report,original)

    def test_delayed_multibend_requires_real_modeled_terminal_correction(self):
        # Freeze the observed development case without retuning its region
        # sizes or model parameters. The first leg reuses the previously
        # observed staggered-finish correction geometry; the second bends
        # again after carrying the actual settled pose into the new leg.
        document=json.loads(self.path.read_bytes())
        document["source"]["generator"]="taxi-constrained-multibend-development/1"
        document["route"]["id"]="constrained-staggered-multibend"
        document["route"]["points"]=[
            {"name":str(i),"kind":k,"xyz":xyz} for i,(k,xyz) in enumerate((
                ("guide",[0,0,0]),("guide",[3,0,0]),("mandatory_passage",[4,0,2]),
                ("guide",[7,0,2]),("hard_stop",[7.4,0,2.4]),("guide",[10.4,0,2.4]),
                ("mandatory_passage",[11.4,0,4.4]),("destination",[14.4,0,4.4])))]
        document["poses"][0]["xyz"]=[0.,0.,.35]
        document["poses"][0]["actorYawDeg"]=-50.
        path=self.root/"multibend.json"
        path.write_text(json.dumps(document),encoding="utf-8")
        from rift_taxi.contracts import load_trace
        trace=load_trace(path)
        policy={**self.policy,"traceSHA256":trace.trace_sha256,
                "passageRegions":[
                    {"pointIndex":2,"minXYZ":[3.,-.1,1.],"maxXYZ":[5.,.1,3.]},
                    {"pointIndex":6,"minXYZ":[10.4,-.1,3.4],"maxXYZ":[12.4,.1,5.4]}]}
        options=dict(dt=.12,speed=3.6,yaw_rate=125.,delay_steps=3)
        report=run_constrained_journey(trace,policy,**options)
        self.assertTrue(report["allObligationsObserved"])
        first,second=report["legs"]
        correction=first["journey"]["terminalCorrection"]
        self.assertEqual(correction["status"],"model-corrected")
        self.assertGreater(correction["extraTravelXZ"],0.)
        self.assertAlmostEqual(correction["extraSeconds"],1.56)
        self.assertEqual(first["finalXYZ"],second["initialXYZ"])
        self.assertTrue(verify_constrained_report(report,trace,policy)["allObligationsObserved"])
        # An otherwise identical model with insufficient correction time
        # must never resume from the unqualified hard-stop endpoint.
        failed=run_constrained_journey(trace,policy,terminal_budget=.01,**options)
        self.assertEqual(failed["status"],"terminal-unsettled")
        self.assertEqual(len(failed["legs"]),1)
        self.assertEqual(failed["completedLegs"],0)
        self.assertEqual(failed["legs"][0]["dwellFrames"],[])
        self.assertFalse(verify_constrained_report(failed,trace,policy)["allObligationsObserved"])

    def test_forged_carryover_pose_and_leg_identity_refused(self):
        for key,value in (("initialXYZ",[4.,0.,0.]),("controllerTraceSHA256","0"*64),
                          ("legNumber",1)):
            report=deepcopy(self.good)
            if key=="initialXYZ":
                report["legs"][1][key][0]+=1.
            else:
                report["legs"][1][key]=value
            with self.subTest(key=key),self.assertRaises(TraceError):
                self.verify(report)

    def test_dwell_and_witness_corruption_refused(self):
        report=deepcopy(self.good)
        report["legs"][0]["dwellFrames"][-1]["appliedSpeed"]=.1
        with self.assertRaisesRegex(TraceError,"dwell frames"):
            self.verify(report)
        report=deepcopy(self.good)
        report["legs"][0]["obligationAudit"]["obligations"][0]["witness"]["sampleIndex"]+=1
        with self.assertRaisesRegex(TraceError,"obligation evidence"):
            self.verify(report)

    def test_truncated_accepted_prefix_refused(self):
        report=deepcopy(self.good)
        report["legs"]=report["legs"][:1]
        report["completedLegs"]=1
        report["allObligationsObserved"]=False
        with self.assertRaisesRegex(TraceError,"truncated"):
            self.verify(report)

    def test_failed_region_cannot_resume(self):
        _,trace,policy=fixture(self.root,narrow=True)
        failed=run_constrained_journey(trace,policy)
        self.assertFalse(verify_constrained_report(failed,trace,policy)["allObligationsObserved"])
        failed["legs"].append(deepcopy(self.good["legs"][1]))
        with self.assertRaisesRegex(TraceError,"resumes after failed"):
            verify_constrained_report(failed,trace,policy)

    def test_forged_model_and_totals_refused(self):
        report=deepcopy(self.good)
        report["model"]["delaySteps"]=1
        with self.assertRaisesRegex(TraceError,"leg delay"):
            self.verify(report)
        for key,value in (("totalDistanceXZ",999.),("allObligationsObserved",1),
                          ("status","invented"),("physicalQualification",True)):
            report=deepcopy(self.good)
            report[key]=value
            with self.subTest(key=key),self.assertRaises(TraceError):
                self.verify(report)

    def test_saved_bytes_pin_and_policy_exact_hash(self):
        pol=self.root/"policy.json"
        raw_policy=json.dumps(self.policy).encode()
        pol.write_bytes(raw_policy)
        report=deepcopy(self.good)
        report["policySHA256"]=hashlib.sha256(raw_policy).hexdigest()
        path=self.root/"report.json"
        raw=json.dumps(report,allow_nan=False).encode()
        path.write_bytes(raw)
        pin=hashlib.sha256(raw).hexdigest()
        result=audit_saved(self.path,pol,path,expected_sha256=pin)
        self.assertTrue(result["declaredPolicySHA256Matched"])
        self.assertTrue(result["expectedSHA256Matched"])
        self.assertEqual(path.read_bytes(),raw)
        with self.assertRaisesRegex(TraceError,"report SHA"):
            audit_saved(self.path,pol,path,expected_sha256="0"*64)
        # Semantic policy is unchanged but exact bytes disagree.
        pol.write_bytes(raw_policy+b"\n")
        with self.assertRaisesRegex(TraceError,"policy byte SHA"):
            audit_saved(self.path,pol,path)

    def test_cli_refuses_overwrite_and_duplicate_json(self):
        pol=self.root/"policy.json"
        pol.write_text(json.dumps(self.policy),encoding="utf-8")
        report=self.root/"report.json"
        report.write_text(json.dumps(self.good),encoding="utf-8")
        out=self.root/"audit.json"
        args=[str(self.path),str(pol),str(report),"--out",str(out)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args),0)
        original=out.read_bytes()
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as ctx:
            main(args)
        self.assertEqual(ctx.exception.code,2)
        self.assertEqual(out.read_bytes(),original)
        report.write_text('{"schema":"x","schema":"y"}',encoding="utf-8")
        with self.assertRaisesRegex(TraceError,"duplicate"):
            audit_saved(self.path,pol,report)
