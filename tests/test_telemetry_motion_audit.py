"""Offline regression fixtures for retained API position and clock evidence.

These files model the already-verified bracket/replay interface; the test
does not claim an actual RIFT source or call an upstream sibling reader.
"""
from copy import deepcopy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.telemetry_motion_audit import (
    PREFIX, SUFFIX, MotionAuditRefused, audit, main,
)

PLAYER="u035400012FA2D207"
ZONE="z487C9102D2EA79BE"
SESSION="a"*32
BUILD="b"*64


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def frame(seq):
    return {"schemaVersion":4,"addon":"Telemetry","addonVersion":"0.5.0",
            "source":"rift-api","status":"observed","sessionId":SESSION,"epoch":8,
            "sequence":seq,"frameTime":seq/10.,"playerId":PLAYER,
            "player":{"id":PLAYER,"zone":ZONE,"coordX":10.,"coordY":2.,"coordZ":3.},
            "playerTelemetry":{"id":PLAYER,"status":"observed",
                               "zone":{"status":"observed","id":ZONE}}}


class MotionAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.summary=self.root/"summary.json"
        self.replay=self.root/"zone-replay.json"
        self.target={"hostName":"LEGION","processId":123,"processStartUtcTicks":"456",
                     "executableSha256":BUILD}
        for i in (1,2):
            (self.root/f"pass-{i:02d}").mkdir()

    def build(self,mutate=None):
        """Write a small two-pass fixture including a repeated source sequence."""
        passes=[]
        for i,seqs in enumerate(((1,2),(2,4)),1):
            rows=[]
            for n,s in enumerate(seqs,1):
                doc=frame(s)
                if mutate:
                    mutate(i,s,doc)
                name=f"frame-{n:02d}.wire"
                raw=PREFIX+json.dumps(doc,separators=(",",":")).encode()+SUFFIX
                (self.root/f"pass-{i:02d}"/name).write_bytes(raw)
                rows.append({"seq":s,"epoch":8,"clock":s/10.,"session":SESSION,
                             "zoneId":ZONE,"wire":f"C:\\old\\pass-{i:02d}\\{name}",
                             "sha":digest(raw)})
            passes.append({"frames":rows})
        self.summary_doc={"schemaVersion":1,
                          "evidenceKind":"physical-native-telemetry-zone-bracket-candidate/1",
                          "status":"matching-candidates","sameProcessEpoch":True,
                          "target":deepcopy(self.target),"passes":passes}
        self.replay_doc={"schemaVersion":1,
                         "evidenceKind":"physical-native-telemetry-zone-offline-replay/1",
                         "status":"matching-candidates",**deepcopy(self.target),
                         "playerUnitId":PLAYER,"zoneIdCandidate":ZONE,
                         "sourceSessionId":SESSION,"sourceEpoch":8,"savedFrames":[2,2],
                         "uniqueSourceSequences":3,"firstSourceSequence":1,
                         "lastSourceSequence":4,"newAdvancingSourceFrames":1}
        return self.rehash()

    def rehash(self):
        raw=json.dumps(self.summary_doc).encode()
        self.summary.write_bytes(raw)
        self.summary_sha=digest(raw)
        self.replay_doc["evidenceSummarySha256"]=self.summary_sha
        return self.write_replay()

    def write_replay(self):
        raw=json.dumps(self.replay_doc).encode()
        self.replay.write_bytes(raw)
        self.replay_sha=digest(raw)
        return self.check

    def check(self):
        return audit(self.summary,self.summary_sha,self.replay,self.replay_sha)

    def test_static_pose_is_not_stale_publisher_or_qualified_heading(self):
        self.build()
        r=self.check()
        self.assertEqual(r["frameOccurrences"],4)
        self.assertEqual(r["uniqueSequences"],3)
        self.assertEqual(r["xyzAvailableFrames"],3)
        self.assertEqual(r["uniqueXYZCandidates"],1)
        self.assertEqual(r["changedComparablePairs"],0)
        self.assertEqual(r["consecutiveComparablePairs"],1)
        self.assertEqual(r["newAdvancingSequences"],[4])
        self.assertEqual(r["headingLikeFieldNames"],[])
        self.assertAlmostEqual(r["sourceClockSpanSeconds"],.3)
        for key in ("sourceClockHostAligned","nativePassiveFreshnessVerified",
                    "bodyHeadingVerified","gameInputConsumptionVerified",
                    "actualCurrentSessionVerified","productionInputAuthorized"):
            self.assertIs(r[key],False)

    def test_changed_pose_and_sequence_gap_remain_distinct(self):
        def mutate(i,s,d):
            if s==4:
                d["player"]["coordX"]=13.
                d["player"]["coordZ"]=7.
                d["player"]["heading"]=42.
        self.build(mutate)
        r=self.check()
        self.assertEqual(r["changedComparablePairs"],1)
        self.assertEqual(r["maxAdjacentXZDifference"],5.)
        self.assertFalse(r["pairs"][-1]["consecutivePublisherSequences"])
        self.assertEqual(r["headingLikeFieldNames"],["heading"])
        self.assertFalse(r["bodyHeadingVerified"])

    def test_missing_xyz_does_not_bridge_observations(self):
        self.build(lambda i,s,d:d["player"].pop("coordY") if s==2 else None)
        r=self.check()
        self.assertEqual(r["xyzAvailableFrames"],2)
        self.assertEqual(r["adjacentComparablePairs"],0)
        self.assertIsNone(r["maxAdjacentXZDifference"])

    def test_invalid_present_coordinate_refuses_even_with_valid_digests(self):
        for value in (True,"10",None,float("inf"),1e20):
            with self.subTest(value=value):
                self.build(lambda i,s,d:d["player"].__setitem__("coordX",value))
                with self.assertRaises(MotionAuditRefused):
                    self.check()

    def test_wire_tampering_and_conflicting_repeat_refused(self):
        self.build()
        f=self.root/"pass-01"/"frame-01.wire"
        f.write_bytes(f.read_bytes()+b" ")
        with self.assertRaises(MotionAuditRefused):
            self.check()
        self.build(lambda i,s,d:d["player"].__setitem__("coordZ",99.) if (i,s)==(2,2) else None)
        with self.assertRaises(MotionAuditRefused):
            self.check()

    def test_wrong_player_generation_or_index_refused(self):
        for key,value in (("playerId","u"+"0"*16),("epoch",9),
                          ("sequence",99),("frameTime",0.001),("sessionId","c"*32)):
            with self.subTest(field=key):
                self.build(lambda i,s,d:d.__setitem__(key,value))
                with self.assertRaises(MotionAuditRefused):
                    self.check()

    def test_replay_binding_and_counts_refused(self):
        for key,value in (("processId",124),("uniqueSourceSequences",4),
                          ("newAdvancingSourceFrames",0),("evidenceSummarySha256","f"*64)):
            with self.subTest(field=key):
                self.build()
                self.replay_doc[key]=value
                self.write_replay()
                with self.assertRaises(MotionAuditRefused):
                    self.check()

    def test_bad_index_name_and_wrong_summary_digest_refused(self):
        self.build()
        self.summary_doc["passes"][0]["frames"][0]["wire"]="wrong.wire"
        self.rehash()
        with self.assertRaises(MotionAuditRefused):
            self.check()
        self.build()
        self.summary_sha="a"*64
        with self.assertRaises(MotionAuditRefused):
            self.check()

    def test_cli_refuses_overwrite(self):
        self.build()
        out=self.root/"motion.json"
        argv=["--summary",str(self.summary),"--summary-sha",self.summary_sha,
              "--replay",str(self.replay),"--replay-sha",self.replay_sha,"--out",str(out)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(argv),0)
        before=out.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as e:
            main(argv)
        self.assertEqual(e.exception.code,2)
        self.assertEqual(out.read_bytes(),before)
