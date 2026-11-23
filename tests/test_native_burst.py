"""Burst tests use only injected candidate reports and simulated monotonic time."""
from __future__ import annotations

import contextlib
import io
import json
import math
import struct
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rift_taxi.native_burst import capture_native_burst
from rift_taxi.native_capture import CandidateCaptureRefused
from rift_taxi.cli import main


EXE = r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"
SHA = "df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01"
START = 638_000_000_000_000_000


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def sleep(self, delta):
        self.t += delta


class BurstFixture:
    def __init__(self):
        self.clock = FakeClock()
        self.calls = 0
        self.changes = [(1., 3., 4., 179.), (1., 3., 4., -179.),
                        (4., 3., 8., -178.), (4., 3., 8., -177.)]
        self.mutate = None
        self.exceptions_at = None
        self.matrix_angles = [175.0, -175.0, -170.0, -160.0]
        self.options = dict(pid=4, start_utc_ticks=START, executable_path=EXE,
                            executable_sha256=SHA, window_handle=1234, host="LEGION")

    def capture(self, **kwargs):
        self.calls += 1
        assert kwargs["pid"] == 4
        assert kwargs["max_capture_s"] == 3.0
        want_matrix = kwargs.get("include_matrix_candidate", False)
        if self.exceptions_at == self.calls:
            raise CandidateCaptureRefused("injected inner failure")
        self.clock.t += .10
        x, y, z, yaw = self.changes[(self.calls - 1) % len(self.changes)]
        doc = {
            "schema": "taxi.native-candidate/1", "status": "candidate-only",
            "process": {
                "host": "LEGION", "pid": 4, "startUtcTicks": START,
                "windowHandle": 1234, "executablePath": EXE,
                "onDiskExecutableSha256": SHA,
                "foregroundAtStartAndEnd": True,
            },
            "candidate": {
                "ownerKeyDecimal": "777",
                "xyz": [x, y, z],
                "playerSystemBearingDegrees": yaw,
                "observationMonotonicSeconds": self.clock.t,
            },
            "evidence": {
                "captureBracketSeconds": 0.1,
                "actorHeadingQualified": False,
                "passivePositionFreshnessQualified": False,
                "liveInGameResponseVerified": False,
                "inputSent": False, "arrivalVerified": False,
                "matrixEvidenceRequested": want_matrix,
            }
        }
        if want_matrix:
            angle = self.matrix_angles[(self.calls - 1) % len(self.matrix_angles)]
            rad = math.radians(angle)
            c, s = math.cos(rad), math.sin(rad)
            values = (c, 0., -s, 0., 1., 0., s, 0., c)
            bits = list(struct.unpack("<9I", struct.pack("<9f", *values)))
            doc["matrixEvidence"] = {
                "positionSecondaryRawBits": bits[:],
                "actorRawBits": bits[:],
                "exactRawBitsMatch": True,
                "positionSecondaryPlanarAngleDegreesCandidate": angle,
                "actorPlanarAngleDegreesCandidate": angle,
                "positionMatrixStatus": "structural-y-planar-matrix-candidate",
                "actorMatrixStatus": "structural-y-planar-matrix-candidate",
                "actorHeadingQualified": False,
            }
        else:
            doc["matrixEvidence"] = None
        if self.mutate:
            self.mutate(doc, self.calls)
        return doc

    def run(self, **kwargs):
        args = {**self.options, "samples": 4, "interval_ms": 200,
                "capture": self.capture, "clock": self.clock,
                "sleep": self.clock.sleep}
        args.update(kwargs)
        return capture_native_burst(**args)


class BurstTests(unittest.TestCase):
    def setUp(self):
        self.fixture = BurstFixture()

    def test_burst_reports_candidate_deltas_not_movement(self):
        report = self.fixture.run()
        self.assertEqual(report["schema"], "taxi.native-candidate-burst/1")
        self.assertEqual(report["completedSamples"], 4)
        self.assertEqual(self.fixture.calls, 4)
        self.assertEqual(report["source"]["ownerKeyDecimalCandidate"], "777")
        self.assertAlmostEqual(report["candidateChanges"]["firstToLastXzDistanceSourceUnits"], 5)
        self.assertAlmostEqual(report["candidateChanges"]["firstToLast3dDistanceSourceUnits"], 5)
        self.assertEqual(report["candidateChanges"]["firstToLastYawDeltaDegrees"], 4)
        self.assertTrue(report["candidateChanges"]["anyXyzChanged"])
        self.assertTrue(report["candidateChanges"]["anyYawChanged"])
        self.assertFalse(report["candidateChanges"]["movementVerified"])
        self.assertFalse(report["candidateChanges"]["freshnessVerified"])
        self.assertFalse(report["evidence"]["inputSent"])
        self.assertFalse(report["evidence"]["independentPositionSourceCompared"])

    def test_matrix_burst_compares_bits_and_yaw_but_never_verifies_heading(self):
        report = self.fixture.run(include_matrix_candidate=True)
        self.assertEqual(self.fixture.calls, 4)
        self.assertTrue(report["matrixEvidenceRequested"])
        matrix = report["matrixCandidateChanges"]
        self.assertTrue(matrix["allPositionActorRawBitsMatch"])
        self.assertTrue(matrix["anyPositionSecondaryMatrixBitsChanged"])
        self.assertTrue(matrix["anyActorMatrixBitsChanged"])
        self.assertAlmostEqual(
            matrix["firstToLastActorPlanarAngleDegreesDeltaCandidate"], 25.0
        )
        self.assertFalse(matrix["headingVerified"])
        self.assertFalse(matrix["sourceFreshnessVerified"])
        self.assertEqual(len(report["observations"][0]["matrixEvidence"]["actorRawBits"]), 9)
        self.assertFalse(report["candidateChanges"]["movementVerified"])
        self.assertFalse(report["evidence"]["inputSent"])

    def test_matrix_mismatch_remains_diagnostic_not_motion_proof(self):
        def change(doc, index):
            if index == 2:
                doc["matrixEvidence"]["actorRawBits"][0] ^= 1
                doc["matrixEvidence"]["exactRawBitsMatch"] = False
        self.fixture.mutate = change
        report = self.fixture.run(include_matrix_candidate=True, samples=2)
        self.assertFalse(report["matrixCandidateChanges"]["allPositionActorRawBitsMatch"])
        self.assertFalse(report["matrixCandidateChanges"]["headingVerified"])

    def test_matrix_optional_reports_no_angle_for_nonstructural_sources(self):
        def change(doc, index):
            doc["matrixEvidence"]["actorMatrixStatus"] = "nonfinite-matrix"
            doc["matrixEvidence"]["positionMatrixStatus"] = "nonfinite-matrix"
            doc["matrixEvidence"]["actorPlanarAngleDegreesCandidate"] = None
            doc["matrixEvidence"]["positionSecondaryPlanarAngleDegreesCandidate"] = None
        self.fixture.mutate = change
        report = self.fixture.run(include_matrix_candidate=True, samples=2)
        self.assertIsNone(
            report["matrixCandidateChanges"]["firstToLastActorPlanarAngleDegreesDeltaCandidate"]
        )
        self.assertFalse(report["matrixCandidateChanges"]["headingVerified"])

    def test_burst_refuses_invalid_optional_matrix_evidence(self):
        cases = [
            ("missing", lambda m: m.pop("matrixEvidence")),
            ("bad_raw_bits", lambda m: m["matrixEvidence"].__setitem__("actorRawBits", [0] * 8)),
            ("bool_bit", lambda m: m["matrixEvidence"]["actorRawBits"].__setitem__(0, True)),
            ("range", lambda m: m["matrixEvidence"]["actorRawBits"].__setitem__(0, 2**32)),
            ("mismatch_flag", lambda m: m["matrixEvidence"].__setitem__("exactRawBitsMatch", False)),
            ("qualified", lambda m: m["matrixEvidence"].__setitem__("actorHeadingQualified", True)),
            ("missing_angle", lambda m: m["matrixEvidence"].__setitem__("actorPlanarAngleDegreesCandidate", None)),
            ("nan_angle", lambda m: m["matrixEvidence"].__setitem__("actorPlanarAngleDegreesCandidate", float("nan"))),
            ("bad_status", lambda m: m["matrixEvidence"].__setitem__("actorMatrixStatus", "verified")),
            ("wrong_request_flag", lambda m: m["evidence"].__setitem__("matrixEvidenceRequested", False)),
        ]
        for name, mutate in cases:
            self.fixture = BurstFixture()
            def change(doc, index):
                if index == 1:
                    mutate(doc)
            self.fixture.mutate = change
            with self.subTest(name=name), self.assertRaises(CandidateCaptureRefused):
                self.fixture.run(include_matrix_candidate=True)
            self.assertEqual(self.fixture.calls, 1)

    def test_unsolicited_matrix_evidence_rejected_in_ordinary_burst(self):
        def change(doc, index):
            if index == 1:
                doc["matrixEvidence"] = {
                    "actorRawBits": [0] * 9, "positionSecondaryRawBits": [0] * 9
                }
        self.fixture.mutate = change
        with self.assertRaisesRegex(CandidateCaptureRefused, "unsolicited"):
            self.fixture.run()
        self.assertEqual(self.fixture.calls, 1)

    def test_stationary_values_dont_establish_freshness(self):
        self.fixture.changes = [(12., 3., -9., 45.)]
        report = self.fixture.run(samples=3)
        self.assertFalse(report["candidateChanges"]["anyXyzChanged"])
        self.assertFalse(report["candidateChanges"]["anyYawChanged"])
        self.assertFalse(report["candidateChanges"]["freshnessVerified"])

    def test_intermediate_change_detected_even_with_same_endpoints(self):
        self.fixture.changes = [(1., 1., 1., 10.), (2., 1., 1., 11.), (1., 1., 1., 10.)]
        report = self.fixture.run(samples=3)
        self.assertEqual(report["candidateChanges"]["firstToLastXzDistanceSourceUnits"], 0)
        self.assertTrue(report["candidateChanges"]["anyXyzChanged"])

    def test_owner_change_aborts_partial_evidence(self):
        def change(doc, i):
            if i == 2:
                doc["candidate"]["ownerKeyDecimal"] = "778"
        self.fixture.mutate = change
        with self.assertRaisesRegex(CandidateCaptureRefused, "owner changed"):
            self.fixture.run()
        self.assertEqual(self.fixture.calls, 2)

    def test_source_identity_or_foreground_change_aborts(self):
        for field, val in (("pid", 5), ("windowHandle", 99),
                           ("startUtcTicks", START + 1),
                           ("onDiskExecutableSha256", "e" * 64),
                           ("foregroundAtStartAndEnd", False)):
            self.fixture = BurstFixture()
            def change(doc, i):
                if i == 2:
                    doc["process"][field] = val
            self.fixture.mutate = change
            with self.subTest(field=field), self.assertRaises(CandidateCaptureRefused):
                self.fixture.run()

    def test_reject_qualified_or_input_sent_flags(self):
        for field in ("actorHeadingQualified", "passivePositionFreshnessQualified",
                      "liveInGameResponseVerified", "inputSent", "arrivalVerified"):
            self.fixture = BurstFixture()
            def change(doc, i):
                if i == 1:
                    doc["evidence"][field] = True
            self.fixture.mutate = change
            with self.subTest(field=field), self.assertRaisesRegex(CandidateCaptureRefused, "qualification"):
                self.fixture.run()

    def test_reject_nan_and_missing_fields(self):
        for section, field, value in (
                ("candidate", "xyz", [float("nan"), 2, 3]),
                ("candidate", "xyz", [1, 2]),
                ("candidate", "playerSystemBearingDegrees", float("inf")),
                ("candidate", "observationMonotonicSeconds", True),
                ("candidate", "ownerKeyDecimal", "no-key"),
                ("evidence", "captureBracketSeconds", -1)):
            self.fixture = BurstFixture()
            def change(doc, i):
                if i == 1:
                    doc[section][field] = value
            self.fixture.mutate = change
            with self.subTest(field=field), self.assertRaises(CandidateCaptureRefused):
                self.fixture.run()

    def test_nonadvancing_monotonic_timestamp_aborts(self):
        def change(doc, i):
            if i == 2:
                doc["candidate"]["observationMonotonicSeconds"] = 100.10
        self.fixture.mutate = change
        with self.assertRaisesRegex(CandidateCaptureRefused, "failed to advance"):
            self.fixture.run()

    def test_time_budget_aborts_no_completed_report(self):
        with self.assertRaisesRegex(CandidateCaptureRefused, "duration"):
            self.fixture.run(max_total_s=2, interval_ms=1500, samples=4)

    def test_inner_capture_failure_aborts(self):
        self.fixture.exceptions_at = 2
        with self.assertRaisesRegex(CandidateCaptureRefused, "injected inner"):
            self.fixture.run()
        self.assertEqual(self.fixture.calls, 2)

    def test_reject_invalid_bounds_before_any_capture(self):
        for key, value in (
                ("samples", 1), ("samples", 9), ("samples", True),
                ("interval_ms", -1), ("interval_ms", 1501),
                ("max_total_s", float("inf")), ("max_total_s", 1),
                ("per_capture_s", 11), ("pid", 0), ("window_handle", True),
                ("executable_sha256", "bad"), ("executable_path", "RIFT.exe"),
                ("include_matrix_candidate", 1)):
            self.fixture = BurstFixture()
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.fixture.run(**{key: value})
            self.assertEqual(self.fixture.calls, 0)

    def test_cli_writes_only_new_report(self):
        payload = self.fixture.run(samples=2)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "burst.json"
            argv = [
                "inspect-native-burst", "--pid", "4", "--start-ticks", str(START),
                "--exe-path", EXE, "--sha256", SHA, "--hwnd", "0x4d2",
                "--host", "LEGION", "--samples", "2", "--interval-ms", "0",
                "--out", str(out),
            ]
            with patch("rift_taxi.cli.capture_native_burst", return_value=payload):
                self.assertEqual(main(argv), 0)
                self.assertEqual(json.loads(out.read_text())["completedSamples"], 2)
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(argv), 2)

    def test_matrix_cli_flag_is_forwarded_and_stored(self):
        report = self.fixture.run(samples=2, include_matrix_candidate=True)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "matrix-burst.json"
            argv = [
                "inspect-native-burst", "--pid", "4", "--start-ticks", str(START),
                "--exe-path", EXE, "--sha256", SHA, "--hwnd", "1234",
                "--host", "LEGION", "--samples", "2", "--include-matrix-candidate",
                "--out", str(out),
            ]
            with patch("rift_taxi.cli.capture_native_burst", return_value=report) as capture:
                self.assertEqual(main(argv), 0)
                self.assertTrue(capture.call_args.kwargs["include_matrix_candidate"])
            saved = json.loads(out.read_text())
            self.assertTrue(saved["matrixEvidenceRequested"])
            self.assertFalse(saved["matrixCandidateChanges"]["headingVerified"])

    def test_cli_doctor_declares_candidate_burst_not_live_reader(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["doctor"]), 0)
        doc = json.loads(output.getvalue())
        self.assertTrue(doc["nativeCandidateBurstAvailable"])
        self.assertFalse(doc["nativeReaderImplemented"])
        self.assertFalse(doc["gameInputEnabled"])


if __name__ == "__main__":
    unittest.main()
