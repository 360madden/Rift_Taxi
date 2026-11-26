"""Offline native-series receipt regressions using the existing injected observer.

The harness contains no actual game/keyboard/process access. SHA-pinning and
semantic checks are exercised separately: even a freshly rehashed malformed
fixture must fail. A positive audit must never promote candidate authority.
"""
from copy import deepcopy
from dataclasses import replace
import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest

from test_native_series import SeriesHarness, PATH, SHA, PID, TICKS, HWND
from rift_taxi.native_candidate import ZoneKeyCandidate
from rift_taxi.verify_native_series import audit, main, SeriesAuditRefused

PIN=dict(host="LEGION",pid=PID,start_ticks=TICKS,exe_path=PATH,
         exe_sha256=SHA,hwnd=HWND,owner_key="123")


def fixture(with_options=True):
    """Use actual observer's receipt shape, replacing only fake decode fields."""
    h=SeriesHarness()
    original=h.decode
    words=struct.unpack("<9I",struct.pack("<9f",1,0,0,0,1,0,0,0,1))
    def decode(session,*,clock,**options):
        r=original(session,clock=clock,**options)
        if r.matrix_copy_candidate:
            m=replace(r.matrix_copy_candidate,actor_raw_bits=words,
                      position_secondary_raw_bits=words,
                      actor_planar_angle_degrees_candidate=0.,
                      position_planar_angle_degrees_candidate=0.)
            r=replace(r,matrix_copy_candidate=m)
        if options.get("include_zone_key_candidate"):
            r=replace(r,zone_key_candidate=ZoneKeyCandidate(0x12345678))
        return r
    h.decode=decode
    class FakeKeys:
        def __init__(self):
            self.i=0
        def snapshot(self):
            self.i+=1
            h.clock.time+=.001
            return {"W":self.i in (3,4,5),"A":False,"D":False}
    return h.run(include_matrix_candidate=with_options,
                 include_refresh_guard_candidate=with_options,
                 include_actor_translation_candidate=with_options,
                 include_zone_key_candidate=with_options,
                 observe_manual_keys=with_options,keyboard_factory=FakeKeys)


class NativeSeriesAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"source.json"
        self.source=fixture()

    def write(self, doc=None, raw=None):
        if raw is None:
            raw=json.dumps(self.source if doc is None else doc).encode()
        self.path.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def check(self,doc=None,**pin):
        return audit(self.path,self.write(doc),**{**PIN,**pin})

    def reject_mutations(self,mutators):
        for mutate in mutators:
            d=deepcopy(self.source)
            mutate(d)
            with self.subTest(mutation=mutate),self.assertRaises(SeriesAuditRefused):
                self.check(d)

    def test_complete_candidate_receipt_remains_non_authoritative(self):
        r=self.check()
        self.assertEqual(r["samples"],4)
        self.assertEqual(r["matrixMatches"],4)
        self.assertEqual(r["keyPollsPerKey"],8)
        self.assertEqual(r["keyDownPollsByKey"],{"W":3,"A":0,"D":0})
        self.assertEqual(r["rawZoneKeys"],["0x12345678"])
        self.assertEqual(r["uniqueXYZCandidates"],4)
        for k in ("actualCurrentSessionVerified","passiveFreshnessVerified",
                  "bodyHeadingVerified","publicZoneIdVerified","worldInstanceVerified",
                  "gameInputConsumptionVerified","gameInputSent","productionInputAuthorized"):
            self.assertIs(r[k],False)

    def test_no_optional_evidence_is_explicit(self):
        r=self.check(fixture(False))
        self.assertIsNone(r["matrixMatches"])
        self.assertIsNone(r["keyDownPollsByKey"])
        self.assertEqual(r["keyPollsPerKey"],0)
        self.assertEqual(r["rawZoneKeys"],[])

    def test_wrong_source_pin_even_with_matching_original_hash(self):
        for k,v in (("host","AMD-DESKTOP"),("pid",PID+1),("start_ticks",TICKS+1),
                    ("exe_path",r"C:\other\rift_x64.exe"),("exe_sha256","a"*64),
                    ("hwnd",HWND+1),("owner_key","124"),("pid",True)):
            with self.subTest(field=k),self.assertRaises(SeriesAuditRefused):
                self.check(**{k:v})

    def test_changed_bytes_and_ambiguous_json_refused(self):
        h=self.write()
        self.path.write_bytes(self.path.read_bytes()+b" ")
        with self.assertRaises(SeriesAuditRefused):
            audit(self.path,h,**PIN)
        for raw in (b'{"schema":1,"schema":2}',b'{"value":NaN}',b'{"value":1e999}',
                    b'[]',b'\xff'):
            with self.subTest(raw=raw),self.assertRaises(SeriesAuditRefused):
                audit(self.path,self.write(raw=raw),**PIN)

    def test_identity_counts_and_authority_tampering_refused(self):
        self.reject_mutations((
            lambda d:d["source"].__setitem__("pid",True),
            lambda d:d.__setitem__("completedSamples",3),
            lambda d:d["observations"][2].__setitem__("ownerKeyDecimal","124"),
            lambda d:d["observations"][0].__setitem__("index",True),
            lambda d:d["qualifications"].__setitem__("nativeXYZPassiveFreshnessVerified",True),
            lambda d:d["qualifications"].__setitem__("fullExecutableIdentityChecks",2.0),
            lambda d:d["observations"][0].__setitem__("actorHeadingVerified",0),
        ))

    def test_cadence_and_key_bracket_tampering_refused(self):
        self.reject_mutations((
            lambda d:d["observations"][1].__setitem__("captureStartMonotonicSeconds",100.01),
            lambda d:d["observations"][0].__setitem__("observedMonotonicSeconds",999.),
            lambda d:d["observations"][0].__setitem__("captureBracketSeconds",.4),
            lambda d:d["observedSampleGapSeconds"].__setitem__("median",.01),
            lambda d:d["observedCaptureStartGapSeconds"].__setitem__("maximum",.01),
            lambda d:d["observations"][0]["manualWindowsKeyStates"]["beforeNativeRead"].__setitem__("atMonotonicSeconds",0.),
            lambda d:d["observations"][0]["manualWindowsKeyStates"]["beforeNativeRead"]["keys"].__setitem__("W",1),
            lambda d:d["manualWindowsKeyObservation"]["observedDownPollsByKey"].__setitem__("W",0),
        ))

    def test_candidate_matrix_zone_and_summary_tampering_refused(self):
        self.reject_mutations((
            lambda d:d["observations"][0]["matrixEvidence"].__setitem__("rawBitsMatch",False),
            lambda d:d["observations"][0]["matrixEvidence"].__setitem__("actorPlanarAngleDegreesCandidate",20.),
            lambda d:d["observations"][0]["matrixEvidence"]["actorRawBits"].__setitem__(0,-1),
            lambda d:d["observations"][0]["refreshGuardEvidence"].__setitem__("flagRaw",1),
            lambda d:d["observations"][0]["zoneKeyEvidence"].__setitem__("rawSelfZoneKeyHex","0xDEADBEEF"),
            lambda d:d["observations"][0]["zoneKeyEvidence"].__setitem__("authoritativeZoneQualified",True),
            lambda d:d["observations"][0]["actorTranslationEvidence"].__setitem__("independentlyFresh",True),
            lambda d:d["candidateChanges"].__setitem__("firstToLastDeltaXYZ",[0.,0.,0.]),
        ))

    def test_cli_output_is_exclusive(self):
        dest=Path(self.tmp.name)/"audit.json"
        args=[str(self.path),"--expected-sha256",self.write(),"--host","LEGION",
              "--pid",str(PID),"--start-ticks",str(TICKS),"--exe-path",PATH,
              "--exe-sha256",SHA,"--hwnd",str(HWND),"--owner","123","--out",str(dest)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(args),0)
        original=dest.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as e:
            main(args)
        self.assertEqual(e.exception.code,2)
        self.assertEqual(dest.read_bytes(),original)
