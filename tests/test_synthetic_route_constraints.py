"""Ordered synthetic passage and stop evidence; no live client or input."""
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.contracts import TraceError, load_trace
from rift_taxi.synthetic_route_constraints import audit_constraints, SCHEMA, main


def fixture(root, *, samples=None, events=None):
    # A region visit at (2,0,.5) deliberately misses the nominal point
    # (2,0,0); guides are not exact-position obligations.
    points=[("start","guide",[0,0,0]),("hint","optional",[1,0,1]),
            ("pass","mandatory_passage",[2,0,0]),("stop","hard_stop",[4,0,0]),
            ("goal","destination",[6,0,0])]
    samples=samples if samples is not None else [
        (0,[0,0,0]),(.2,[2,0,.5]),(.4,[4,0,0]),(.6,[4,0,0]),
        (.8,[4,0,0]),(1.,[6,0,0]),(1.2,[6,0,0]),(1.4,[6,0,0])]
    doc={"schema":"taxi.motion-trace/1","sourceType":"synthetic",
         "source":{"generator":"ordered-constraint-fixture"},
         "frame":{"frameId":"synthetic-local-xyz","axisOrder":["x","y","z"],
                  "upAxis":"y","units":"synthetic-units"},
         "route":{"id":"constraint-course","arrivalToleranceXZ":.3,
                  "points":[{"name":n,"kind":k,"xyz":p} for n,k,p in points]},
         "movementWindow":[0,samples[-1][0]],
         "poses":[{"t":t,"xyz":p,"actorYawDeg":None} for t,p in samples],
         "events":events if events is not None else []}
    path=root/"trace.json"
    path.write_text(json.dumps(doc),encoding="utf-8")
    trace=load_trace(path)
    policy={"schema":SCHEMA,"traceSHA256":trace.trace_sha256,
            "maxSampleGapSeconds":.25,"stopDwellSeconds":.4,"stopYTolerance":.1,
            "passageRegions":[{"pointIndex":2,"minXYZ":[1.5,-.1,-1],
                               "maxXYZ":[2.5,.1,1]}]}
    return path,trace,policy


class ConstraintTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)

    def test_complete_ordered_regions_and_stationary_stops(self):
        _,trace,policy=fixture(self.root)
        r=audit_constraints(trace,policy)
        self.assertTrue(r["allObligationsObserved"])
        self.assertEqual(r["ordinaryGuideCount"],2)
        self.assertEqual([o["status"] for o in r["obligations"]],
                         ["sampled-region-observed","sampled-stop-observed","sampled-stop-observed"])
        self.assertEqual(r["obligations"][0]["witness"]["xyz"],[2.,0.,.5])
        self.assertFalse(r["physicalQualification"])
        self.assertFalse(r["continuousStationarityVerified"])
        self.assertFalse(r["corridorClearanceVerified"])

    def test_missing_region_wrong_floor_blocks_later_obligations(self):
        _,trace,policy=fixture(self.root,samples=[
            (0,[0,0,0]),(.2,[2,1,0]),(.4,[4,0,0]),(.6,[4,0,0]),(.8,[4,0,0]),
            (1.,[6,0,0]),(1.2,[6,0,0]),(1.4,[6,0,0])])
        r=audit_constraints(trace,policy)
        self.assertFalse(r["allObligationsObserved"])
        self.assertEqual([o["status"] for o in r["obligations"]],
                         ["not-observed","blocked-by-prior-obligation","blocked-by-prior-obligation"])

    def test_interpolation_is_not_passage_evidence(self):
        _,trace,policy=fixture(self.root,samples=[
            (0,[0,0,0]),(.4,[4,0,0]),(.6,[4,0,0]),(.8,[4,0,0]),
            (1.,[6,0,0]),(1.2,[6,0,0]),(1.4,[6,0,0])])
        self.assertFalse(audit_constraints(trace,policy)["allObligationsObserved"])

    def test_key_pulse_between_stationary_samples_breaks_stop(self):
        events=[{"t":.45,"key":"W","edge":"down"},{"t":.5,"key":"W","edge":"up"}]
        _,trace,policy=fixture(self.root,events=events)
        r=audit_constraints(trace,policy)
        self.assertEqual(r["obligations"][1]["status"],"not-observed")
        self.assertFalse(r["allObligationsObserved"])

    def test_stop_sample_gap_and_accumulating_drift_refused(self):
        for samples in (
            [(0,[0,0,0]),(.2,[2,0,0]),(.4,[4,0,0]),(.9,[4,0,0]),
             (1.1,[6,0,0]),(1.3,[6,0,0]),(1.5,[6,0,0])],
            [(0,[0,0,0]),(.2,[2,0,0]),(.4,[4,0,0]),(.6,[4.01,0,0]),(.8,[4.02,0,0]),
             (1.,[6,0,0]),(1.2,[6,0,0]),(1.4,[6,0,0])]):
            _,trace,policy=fixture(self.root,samples=samples)
            self.assertEqual(audit_constraints(trace,policy)["obligations"][1]["status"],"not-observed")

    def test_destination_must_remain_at_final_sample(self):
        _,trace,policy=fixture(self.root,samples=[
            (0,[0,0,0]),(.2,[2,0,0]),(.4,[4,0,0]),(.6,[4,0,0]),(.8,[4,0,0]),
            (1.,[6,0,0]),(1.2,[6,0,0]),(1.4,[6,0,0]),(1.6,[7,0,0])])
        self.assertEqual(audit_constraints(trace,policy)["obligations"][-1]["status"],"not-observed")

    def test_malformed_or_unpinned_policy_refused(self):
        from copy import deepcopy
        _,trace,policy=fixture(self.root)
        for mutation in ("hash","missing","index","inverted","gap","point"):
            bad=deepcopy(policy)
            if mutation=="hash": bad["traceSHA256"]="0"*64
            elif mutation=="missing": bad["passageRegions"]=[]
            elif mutation=="index": bad["passageRegions"][0]["pointIndex"]=True
            elif mutation=="inverted": bad["passageRegions"][0]["minXYZ"]=[3,0,0]
            elif mutation=="gap": bad["maxSampleGapSeconds"]=False
            else: bad["passageRegions"][0]["maxXYZ"]=[1.9,.1,1]
            with self.subTest(mutation=mutation),self.assertRaises(TraceError):
                audit_constraints(trace,bad)

    def test_cli_retains_failed_receipt_and_never_overwrites(self):
        from contextlib import redirect_stdout, redirect_stderr
        import io
        path,_,policy=fixture(self.root)
        policy["stopDwellSeconds"]=5.
        pin=self.root/"policy.json"
        pin.write_text(json.dumps(policy),encoding="utf-8")
        out=self.root/"audit.json"
        args=[str(path),str(pin),"--out",str(out),"--require-observed"]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args),1)
        before=out.read_bytes()
        self.assertFalse(json.loads(before)["allObligationsObserved"])
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as ctx:
            main(args)
        self.assertEqual(ctx.exception.code,2)
        self.assertEqual(out.read_bytes(),before)
