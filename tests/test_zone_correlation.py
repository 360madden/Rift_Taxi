"""Synthetic tests of candidate-only Taxi/RR2 zone-source correlation."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.zone_correlation import compare_native_zone_sources, ZoneCorrelationRefused
from rift_taxi.cli import main


EXE=r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"
SHA="a"*64
OWNER="239816685251645959"
ZONE=0x487C9102
ID="z487C9102D2EA79BE"


def fixture():
    taxi={
        "schema":"taxi.native-candidate/1",
        "status":"candidate-only",
        "process":{
            "host":"LEGION","pid":424,"startUtcTicks":639310421805307472,
            "executablePath":EXE,"onDiskExecutableSha256":SHA,
            "windowHandle":1968794,"foregroundAtStartAndEnd":True,
        },
        "candidate":{
            "ownerKeyDecimal":OWNER,
            "observationMonotonicSeconds":29000.15,
        },
        "zoneKeyEvidence":{
            "rawSelfZoneKey":ZONE,"rawSelfZoneKeyHex":"0x487C9102",
            "authoritativeZoneQualified":False,
            "publicZoneIdStatus":"not-derived",
            "worldInstanceStatus":"unavailable",
        },
        "evidence":{
            "zoneKeyEvidenceRequested":True,
            "inputSent":False,
            "actorHeadingQualified":False,
            "passivePositionFreshnessQualified":False,
        },
    }
    rr2={
        "schemaVersion":1,
        "contractVersion":"native-current-zone-seed-candidate/1",
        "status":"complete",
        "observation":{
            "identity":{
                "processId":424,"processStartUtcTicks":639310421805307472,
                "executablePath":EXE,"executableSha256":SHA,
            },
            "startedAtUtc":"2026-11-23T19:29:40.6321317+00:00",
            "completedAtUtc":"2026-11-23T19:29:40.6900084+00:00",
            "selfKey":int(OWNER),
            "rawZoneKey":ZONE,
            "status":"type-0073-candidate",
            "childStatus":"type-1e17-raw-candidate",
            "outerVtableCandidate":True,
            "childKey":650763347,
            "zoneIdCandidate":ID,
            "qualification":"1179 zone ID candidate only; API correspondence unverified",
        },
    }
    return taxi,rr2


class ZoneCrossSourceTests(unittest.TestCase):
    def setUp(self):
        ctx=tempfile.TemporaryDirectory()
        self.addCleanup(ctx.cleanup)
        self.folder=Path(ctx.name)

    def _write(self,taxi=None,rr2=None):
        orig_t,orig_r=fixture()
        taxi=orig_t if taxi is None else taxi
        rr2=orig_r if rr2 is None else rr2
        a=self.folder/"taxi.json"
        b=self.folder/"rr2.json"
        a_bytes=(json.dumps(taxi,allow_nan=False)+"\n").encode()
        b_bytes=(json.dumps(rr2,allow_nan=False)+"\n").encode()
        a.write_bytes(a_bytes)
        b.write_bytes(b_bytes)
        return {
            "taxi_report":a,
            "taxi_sha256":hashlib.sha256(a_bytes).hexdigest(),
            "rr2_report":b,
            "rr2_sha256":hashlib.sha256(b_bytes).hexdigest(),
        }

    def test_matching_typed_native_zone_is_not_public_zone_authority(self):
        result=compare_native_zone_sources(**self._write())
        self.assertEqual(result["schema"],"taxi.m1-cross-source-zone-candidate/1")
        self.assertEqual(result["status"],"native-zone-candidates-correlated-not-publicly-qualified")
        self.assertEqual(result["candidates"]["nativeZoneIdCandidate"],ID)
        self.assertEqual(result["candidates"]["rawSelfZoneKeyUnsigned"],ZONE)
        self.assertTrue(result["qualification"]["exactGameEpochAndPlayerOwnerMatch"])
        self.assertTrue(result["qualification"]["sourceOriginalsSHA256Verified"])
        self.assertFalse(result["qualification"]["independentHostIdentityVerified"])
        self.assertFalse(result["qualification"]["sourceClockAlignmentVerified"])
        self.assertFalse(result["qualification"]["publicZoneIdFromAddonApiVerified"])
        self.assertFalse(result["qualification"]["worldInstanceVerified"])
        self.assertFalse(result["qualification"]["productionNavigationArmed"])
        self.assertFalse(result["qualification"]["M1Complete"])

    def test_hash_tampering_refused(self):
        params=self._write()
        with self.assertRaisesRegex(ZoneCorrelationRefused,"SHA-256 mismatch"):
            compare_native_zone_sources(**{**params,"rr2_sha256":"0"*64})
        params["taxi_report"].write_text("{}")
        with self.assertRaisesRegex(ZoneCorrelationRefused,"SHA-256 mismatch"):
            compare_native_zone_sources(**params)

    def test_cross_epoch_and_build_mismatch_refused(self):
        for section,field,value in (
            ("identity","processId",1),
            ("identity","processStartUtcTicks",1),
            ("identity","executableSha256","b"*64),
            ("identity","executablePath",r"C:\OTHER\rift_x64.exe"),
        ):
            taxi,rr2=fixture()
            rr2["observation"][section][field]=value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ZoneCorrelationRefused,"process/start epoch"):
                    compare_native_zone_sources(**self._write(taxi,rr2))

    def test_wrong_raw_key_or_wrong_owner_refused(self):
        for field,value in (("rawZoneKey",ZONE+1),("selfKey",1234)):
            taxi,rr2=fixture()
            rr2["observation"][field]=value
            with self.subTest(field=field):
                with self.assertRaises(ZoneCorrelationRefused):
                    compare_native_zone_sources(**self._write(taxi,rr2))

    def test_false_public_promotion_refused(self):
        for section,field,value in (
            ("zoneKeyEvidence","authoritativeZoneQualified",True),
            ("zoneKeyEvidence","publicZoneIdStatus","verified"),
            ("zoneKeyEvidence","worldInstanceStatus","verified"),
            ("evidence","inputSent",True),
        ):
            taxi,rr2=fixture()
            taxi[section][field]=value
            with self.subTest(field=field),self.assertRaises(ZoneCorrelationRefused):
                compare_native_zone_sources(**self._write(taxi,rr2))

    def test_rr2_untyped_incomplete_and_wrong_prefix_refused(self):
        for field,value in (
            ("zoneIdCandidate",None),
            ("zoneIdCandidate","z00000000D2EA79BE"),
            ("status","unqualified-cache-record"),
            ("outerVtableCandidate",False),
            ("childStatus","unverified-type"),
        ):
            taxi,rr2=fixture()
            rr2["observation"][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(
                    ZoneCorrelationRefused,"typed native record"):
                compare_native_zone_sources(**self._write(taxi,rr2))

    def test_rr2_bracket_must_have_valid_timezone_and_order(self):
        for field,value in (
            ("startedAtUtc","invalid"),
            ("startedAtUtc","2026-11-23T19:29:40"),
            ("completedAtUtc","2026-11-22T18:00:00+00:00"),
            ("completedAtUtc","2026-11-23T19:30:00+00:00"),
        ):
            taxi,rr2=fixture()
            rr2["observation"][field]=value
            with self.subTest(field=field),self.assertRaises(ZoneCorrelationRefused):
                compare_native_zone_sources(**self._write(taxi,rr2))

    def test_duplicate_files_refused(self):
        args=self._write()
        args["rr2_report"]=args["taxi_report"]
        with self.assertRaisesRegex(ZoneCorrelationRefused,"different original"):
            compare_native_zone_sources(**args)

    def test_taxi_not_current_foreground_refused(self):
        taxi,rr2=fixture()
        taxi["process"]["foregroundAtStartAndEnd"]=False
        with self.assertRaisesRegex(ZoneCorrelationRefused,"foreground"):
            compare_native_zone_sources(**self._write(taxi,rr2))

    def _rewrite_raw(self,args,source,raw):
        args[source+"_report"].write_bytes(raw)
        args[source+"_sha256"]=hashlib.sha256(raw).hexdigest()
        return args

    def test_duplicate_json_fields_are_refused_even_with_valid_hash(self):
        for source,old,new in (
            ("taxi",b'"inputSent": false',b'"inputSent": true, "inputSent": false'),
            ("rr2",b'"schemaVersion": 1',b'"schemaVersion": 2, "schemaVersion": 1'),
        ):
            args=self._write()
            raw=args[source+"_report"].read_bytes()
            self.assertIn(old,raw)
            with self.subTest(source=source),self.assertRaisesRegex(ZoneCorrelationRefused,"duplicate JSON key"):
                compare_native_zone_sources(**self._rewrite_raw(args,source,raw.replace(old,new,1)))

    def test_nonfinite_json_and_overflowing_exponents_are_refused(self):
        for value in (b'NaN',b'Infinity',b'-Infinity',b'1e999'):
            args=self._write()
            raw=args["taxi_report"].read_bytes().replace(b'29000.15',value,1)
            with self.subTest(value=value),self.assertRaisesRegex(ZoneCorrelationRefused,"non-finite"):
                compare_native_zone_sources(**self._rewrite_raw(args,"taxi",raw))

    def test_malformed_taxi_evidence_is_controlled_refusal(self):
        for value in (None,[],True,"candidate-only"):
            taxi,rr2=fixture()
            taxi["evidence"]=value
            with self.subTest(value=value),self.assertRaisesRegex(ZoneCorrelationRefused,"evidence object"):
                compare_native_zone_sources(**self._write(taxi,rr2))

    def test_boolean_or_float_schema_version_is_refused(self):
        for value in (True,1.0):
            taxi,rr2=fixture()
            rr2["schemaVersion"]=value
            with self.subTest(value=value),self.assertRaisesRegex(ZoneCorrelationRefused,"zone-seed contract"):
                compare_native_zone_sources(**self._write(taxi,rr2))

    def test_owner_key_is_unsigned_64_bit_not_unbounded_integer(self):
        for value in (2**64,10**40):
            taxi,rr2=fixture()
            taxi["candidate"]["ownerKeyDecimal"]=str(value)
            rr2["observation"]["selfKey"]=value
            with self.subTest(value=value),self.assertRaisesRegex(ZoneCorrelationRefused,"player owner"):
                compare_native_zone_sources(**self._write(taxi,rr2))

    def test_monotonic_clock_bounds_are_enforced(self):
        for value in (0,-1,True,10**40):
            taxi,rr2=fixture()
            taxi["candidate"]["observationMonotonicSeconds"]=value
            with self.subTest(value=value),self.assertRaisesRegex(ZoneCorrelationRefused,"monotonic sample clock"):
                compare_native_zone_sources(**self._write(taxi,rr2))

    def test_cli_can_write_new_candidate_only_json(self):
        args=self._write()
        output=self.folder/"comparison.json"
        argv=[
            "correlate-zone-candidates","--taxi-report",str(args["taxi_report"]),
            "--taxi-sha256",args["taxi_sha256"],
            "--rr2-report",str(args["rr2_report"]),
            "--rr2-sha256",args["rr2_sha256"],
            "--out",str(output),
        ]
        self.assertEqual(main(argv),0)
        self.assertEqual(json.loads(output.read_text())["candidates"]["nativeZoneIdCandidate"],ID)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(argv),2)  # original output cannot be overwritten


if __name__=="__main__":
    unittest.main()
