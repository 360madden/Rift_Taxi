"""Invented candidate fixtures; no actual map or upstream runtime dependency."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from rift_taxi.contracts import TraceError
from rift_taxi.world_candidate_review import inspect_candidate, content_id, IDENTITY_FIELDS


def fixture():
    ends = {"requestedStartXYZ":[0,0,0],"requestedGoalXYZ":[4,0,0],
            "snappedStartXYZ":[0,0,0],"snappedGoalXYZ":[4,0,0]}
    return {"schema":"riftworld.candidate-path/1","patchId":"a"*64,
            "status":"complete","world":{"sourceWorld":"synthetic","authority":"source-map-name"},
            "coordinates":{"axisOrder":["x","y","z"],"upAxis":"y","frameId":"test","units":"test",
                           "transformToRr2Native":{"kind":"unknown"}},
            "query":ends.copy(),"points":[{"id":"0","xyz":[0,0,0],"flags":1},
                                          {"id":"1","xyz":[4,0,0],"flags":2}],
            "planner":{"buildId":"b"*64},
            "evidence":{"geometry":"unknown","walkability":"estimated","traversal":"unverified"},
            "sourceRefs":{"patchDescriptor":"not-accessed.json"},
            "plannerResult":{"status":"complete","cacheKey":"b"*64,**ends,
                             "waypoints":[{"pos":[0,0,0],"flags":1},{"pos":[4,0,0],"flags":2}]}}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/"candidate.json"

    def inspect(self, doc, *, repin=True, expected=None):
        if repin:
            identity={k:doc[k] for k in IDENTITY_FIELDS}
            identity["plannerResult"]=doc.get("plannerResult")
            doc["candidateId"]=content_id(identity)
        raw=json.dumps(doc).encode()
        self.path.write_bytes(raw)
        return inspect_candidate(self.path,expected_sha256=expected or hashlib.sha256(raw).hexdigest(),
                                 source_commit="c"*40)

    def test_valid_review_retains_coordinates_and_disclaims_authority(self):
        doc=fixture()
        result=self.inspect(doc)
        self.assertEqual(result["points"][1]["xyz"],[4.,0.,0.])
        self.assertEqual(result["coordinates"],doc["coordinates"])
        for field in ("physicalQualification","transformQualified","patchCoverageVerified",
                      "endpointConnectorsVerified","productionInputAuthorized","gameInputSent"):
            self.assertIs(result[field],False)

    def test_wrong_byte_hash_and_semantic_id(self):
        doc=fixture()
        with self.assertRaisesRegex(TraceError,"SHA mismatch"):
            self.inspect(doc,expected="0"*64)
        doc["points"][1]["xyz"][0]=9
        with self.assertRaisesRegex(TraceError,"semantic identity"):
            self.inspect(doc,repin=False)

    def test_partial_wrong_axis_duplicate_and_boolean_refused(self):
        for kind in ("partial","axis","duplicate","bool","flags"):
            doc=fixture()
            if kind=="partial": doc["status"]="partial"
            elif kind=="axis": doc["coordinates"]["upAxis"]="z"
            elif kind=="duplicate": doc["points"][1]["id"]="0"
            elif kind=="bool": doc["points"][1]["xyz"][0]=True
            else: doc["points"][1]["flags"]=False
            with self.subTest(kind=kind),self.assertRaises(TraceError):
                self.inspect(doc)

    def test_rehashed_planner_mismatch_refused(self):
        doc=fixture()
        doc["plannerResult"]["waypoints"][1]["pos"]=[3,0,0]
        with self.assertRaisesRegex(TraceError,"planner waypoint"):
            self.inspect(doc)

    def test_nonzero_connector_offset_remains_unverified(self):
        doc=fixture()
        for target in (doc["query"],doc["plannerResult"]):
            target["requestedGoalXYZ"]=[4,2,1]
        r=self.inspect(doc)
        self.assertEqual(r["endpointOffsets"]["goal"],{"horizontalXZ":1.,"verticalY":2.})
        self.assertFalse(r["endpointConnectorsVerified"])

    def test_rejected_snap_cannot_be_relabelled(self):
        doc=fixture()
        for target in (doc["query"],doc["plannerResult"]):
            target["requestedGoalXYZ"]=[4,2,0]
        doc["plannerResult"]["endpointSnaps"]={
            "limits":{"maxHorizontalXZ":.5,"maxVerticalY":.5},
            "start":{"horizontalXZ":0.,"verticalY":0.,"accepted":True},
            "goal":{"horizontalXZ":0.,"verticalY":2.,"accepted":True}}
        with self.assertRaisesRegex(TraceError,"rejected endpoint"):
            self.inspect(doc)

    def test_duplicate_json_key_refused_even_with_correct_byte_pin(self):
        raw=b'{"schema":"wrong","schema":"riftworld.candidate-path/1"}'
        self.path.write_bytes(raw)
        with self.assertRaisesRegex(TraceError,"duplicate"):
            inspect_candidate(self.path,expected_sha256=hashlib.sha256(raw).hexdigest(),source_commit="c"*40)
