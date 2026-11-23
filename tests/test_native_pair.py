"""Offline source-hashed native-candidate pair tests; never contact RIFT."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest

from rift_taxi.native_pair import compare_native_candidates, NativePairError
from rift_taxi.cli import main

SHA = "df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01"
EXE = r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"


def matrix(degrees: float) -> dict:
    radians = math.radians(degrees)
    c, s = math.cos(radians), math.sin(radians)
    bits = list(struct.unpack("<9I", struct.pack(
        "<9f", c, 0, -s, 0, 1, 0, s, 0, c
    )))
    return {
        "positionSecondaryRawBits": bits[:], "actorRawBits": bits[:],
        "exactRawBitsMatch": True,
        "positionSecondaryPlanarAngleDegreesCandidate": degrees,
        "actorPlanarAngleDegreesCandidate": degrees,
        "positionMatrixStatus": "structural-y-planar-matrix-candidate",
        "actorMatrixStatus": "structural-y-planar-matrix-candidate",
        "actorHeadingQualified": False,
    }


def candidate(*, time: float, xyz: tuple[float, float, float],
              angle: float, owner: str = "333",
              actor_translation: bool = False) -> dict:
    guard = {
        "refreshHandleDecimal": "0", "refreshHandleHex": "0x0000000000000000",
        "refreshFlagRaw": 0,
        "topLevelBranchCandidate": "both-known-top-level-routes-ineligible-candidate",
        "knownWriterExecuted": False, "passiveXyzFreshnessQualified": False,
        "apiGetterMayRefreshCache": True,
    }
    actor = None
    if actor_translation:
        secondary = list(xyz)
        stored = [xyz[0], xyz[1] - .06, xyz[2]]
        actor = {
            "positionSecondaryXyz": secondary,
            "actorStoredWorldTranslationCandidate": stored,
            "offsetAt04F8": [0., 0., 0.],
            "offsetAt0770": [0., -.06, 0.],
            "reconstructedActorWorldTranslationCandidate": stored[:],
            "reconstructionMaxAbsDelta": 0.,
            "primarySecondaryMaxAbsDelta": 0.,
            "actorFlagsRaw": 1,
            "renderBranchStatus": "alternate-render-reference-not-followed",
            "normalRenderWorldTranslationCandidate": None,
            "actorRenderMaxAbsDelta": None,
            "independentlyFresh": False,
            "authoritativePlayerPosition": False,
        }
    return {
        "schema": "taxi.native-candidate/1", "status": "candidate-only",
        "process": {
            "host": "LEGION", "pid": 7,
            "startUtcTicks": 638_000_000_000_000_000,
            "executablePath": EXE, "onDiskExecutableSha256": SHA,
            "windowHandle": 987, "foregroundAtStartAndEnd": True,
        },
        "candidate": {
            "ownerKeyDecimal": owner, "xyz": list(xyz),
            "playerSystemBearingDegrees": -angle,
            "observationMonotonicSeconds": time,
        },
        "matrixEvidence": matrix(angle), "refreshGuardEvidence": guard,
        "actorTranslationEvidence": actor,
        "evidence": {
            "captureBracketSeconds": .18,
            "actorHeadingQualified": False, "matrixEvidenceRequested": True,
            "refreshGuardEvidenceRequested": True,
            "actorTranslationEvidenceRequested": actor_translation,
            "passivePositionFreshnessQualified": False,
            "liveInGameResponseVerified": False,
            "inputSent": False, "loadedModuleBytesHashed": False,
            "arrivalVerified": False,
        },
    }


class NativePairTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.early_path = self.root / "early.json"
        self.late_path = self.root / "late.json"
        self.early = candidate(time=90., xyz=(10., 4., 20.), angle=25.)
        self.late = candidate(time=110., xyz=(11., 4.125, 22.), angle=-4.,
                              actor_translation=True)
        self.flush()

    def flush(self) -> None:
        self.early_path.write_text(json.dumps(self.early), encoding="utf-8")
        self.late_path.write_text(json.dumps(self.late), encoding="utf-8")

    def pair(self) -> dict:
        return compare_native_candidates(self.early_path, self.late_path)

    def test_changed_same_epoch_xyz_yaw_and_matrix_never_claim_live_movement(self) -> None:
        report = self.pair()
        self.assertEqual(report["schema"], "taxi.native-candidate-pair/1")
        self.assertEqual(report["timeGapSeconds"], 20.)
        self.assertEqual(report["candidateChanges"]["deltaXYZ"], [1., .125, 2.])
        self.assertAlmostEqual(report["candidateChanges"]["horizontalXZDistanceSourceUnits"],
                               math.sqrt(5))
        self.assertEqual(report["candidateChanges"]["playerSystemYawDeltaDegreesCandidate"], 29.)
        self.assertEqual(report["candidateChanges"]["matrixPair"]["actorMatrixAngleDeltaDegreesCandidate"], -29.)
        self.assertAlmostEqual(
            report["candidateChanges"]["matrixPair"]["beforeActorPlusPlayerSystemAngleDegreesCandidate"], 0.)
        self.assertEqual(report["source"]["ownerKeyDecimalCandidate"], "333")
        self.assertTrue(report["candidateChanges"]["refreshGuardPair"]["bothKnownRoutesIneligibleAtBothEndpoints"])
        self.assertFalse(report["candidateChanges"]["refreshGuardPair"]["otherWriterPathsRuledOut"])
        self.assertIsNone(report["candidateChanges"]["beforeActorTranslationEvidence"])
        self.assertFalse(report["candidateChanges"]["afterActorTranslationEvidence"]["independentlyFresh"])
        self.assertFalse(report["qualifications"]["actorBodyHeadingVerified"])
        self.assertFalse(report["qualifications"]["gameMovementVerified"])
        self.assertFalse(report["qualifications"]["independentPassivePositionFreshnessVerified"])

    def test_input_files_have_exact_original_sha256_receipts(self) -> None:
        result = self.pair()
        self.assertEqual(result["sourceFiles"][0]["sha256"],
                         hashlib.sha256(self.early_path.read_bytes()).hexdigest())
        self.assertEqual(result["sourceFiles"][1]["sha256"],
                         hashlib.sha256(self.late_path.read_bytes()).hexdigest())

    def test_different_player_or_windows_session_fails_closed(self) -> None:
        for field, different in (
            ("host", "AMD-DESKTOP"), ("pid", 8),
            ("startUtcTicks", 638_000_000_000_000_001),
            ("executablePath", r"C:\Other\rift_x64.exe"),
            ("onDiskExecutableSha256", "e" * 64), ("windowHandle", 8),
        ):
            self.late = candidate(time=110., xyz=(11., 4.125, 22.), angle=-4.,
                                  actor_translation=True)
            self.late["process"][field] = different
            self.flush()
            with self.subTest(field=field), self.assertRaises(NativePairError):
                self.pair()
        self.late = candidate(time=110., xyz=(11., 4.125, 22.), angle=-4.,
                              owner="777", actor_translation=True)
        self.flush()
        with self.assertRaisesRegex(NativePairError, "identity changed"):
            self.pair()

    def test_reversed_time_and_duplicate_path_refused(self) -> None:
        self.late["candidate"]["observationMonotonicSeconds"] = 80.
        self.flush()
        with self.assertRaisesRegex(NativePairError, "nonadvancing"):
            self.pair()
        with self.assertRaisesRegex(NativePairError, "distinct"):
            compare_native_candidates(self.early_path, self.early_path)

    def test_bad_evidence_flags_and_raw_matrix_bits_refused(self) -> None:
        changes = (
            lambda doc: doc["evidence"].__setitem__("inputSent", True),
            lambda doc: doc["evidence"].__setitem__("actorHeadingQualified", True),
            lambda doc: doc["matrixEvidence"].__setitem__("actorHeadingQualified", True),
            lambda doc: doc["matrixEvidence"].__setitem__("exactRawBitsMatch", False),
            lambda doc: doc["refreshGuardEvidence"].__setitem__("knownWriterExecuted", True),
            lambda doc: doc["refreshGuardEvidence"].__setitem__("refreshFlagRaw", 700),
        )
        for change in changes:
            self.late = candidate(time=110., xyz=(11., 4.125, 22.), angle=-4.,
                                  actor_translation=True)
            change(self.late)
            self.flush()
            with self.subTest(change=repr(change)), self.assertRaises(NativePairError):
                self.pair()

    def test_bad_actor_translation_and_render_flags_refused(self) -> None:
        for field, value in (
            ("independentlyFresh", True),
            ("authoritativePlayerPosition", True),
            ("actorFlagsRaw", 0),
            ("renderBranchStatus", "unknown"),
            ("reconstructedActorWorldTranslationCandidate", [0., 0., 0.]),
            ("reconstructionMaxAbsDelta", 1000.),
            ("primarySecondaryMaxAbsDelta", 50.),
        ):
            self.late = candidate(time=110., xyz=(11., 4.125, 22.), angle=-4.,
                                  actor_translation=True)
            self.late["actorTranslationEvidence"][field] = value
            self.flush()
            with self.subTest(field=field), self.assertRaises(NativePairError):
                self.pair()

    def test_optional_matrix_and_refresh_evidence_unavailable_is_unavailable(self) -> None:
        for doc in (self.early, self.late):
            doc["matrixEvidence"] = None
            doc["evidence"]["matrixEvidenceRequested"] = False
            doc["refreshGuardEvidence"] = None
            doc["evidence"]["refreshGuardEvidenceRequested"] = False
        self.flush()
        result = self.pair()
        self.assertIsNone(result["candidateChanges"]["matrixPair"])
        self.assertIsNone(result["candidateChanges"]["refreshGuardPair"])
        self.assertTrue(result["candidateChanges"]["xyzValuesChanged"])

    def test_both_actor_stored_translations_allow_candidate_delta(self) -> None:
        self.early = candidate(time=90., xyz=(10., 4., 20.), angle=25.,
                               actor_translation=True)
        self.flush()
        report = self.pair()
        actor = report["candidateChanges"]["actorStoredTranslationPair"]
        for observed, expected in zip(actor["deltaActorStoredWorldTranslationCandidate"],
                                      (1., .125, 2.)):
            self.assertAlmostEqual(observed, expected, places=9)
        self.assertAlmostEqual(actor["horizontalXZDistanceSourceUnits"], math.sqrt(5))
        self.assertFalse(actor["independentlyFresh"])
        self.assertFalse(actor["gameMovementVerified"])

    def test_missing_oversized_nonfinite_file_refused(self) -> None:
        self.early_path.write_text('{"x":NaN}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.pair()
        self.early_path.write_text(" " * 1_000_001, encoding="utf-8")
        with self.assertRaises(ValueError):
            self.pair()
        self.early_path.unlink()
        with self.assertRaises((OSError, ValueError)):
            self.pair()

    def test_cli_new_file_and_no_overwrite(self) -> None:
        output = self.root / "pair.json"
        argv = ["compare-native-candidates", "--before", str(self.early_path),
                "--after", str(self.late_path), "--out", str(output)]
        self.assertEqual(main(argv), 0)
        self.assertEqual(json.loads(output.read_text())["status"],
                         "offline-same-session-candidate-comparison")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(argv), 2)

    def test_cli_doctor_keeps_live_navigation_disabled(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["doctor"]), 0)
        status = json.loads(output.getvalue())
        self.assertTrue(status["offlineNativeCandidatePairComparisonAvailable"])
        self.assertFalse(status["nativeCandidateQualifiedForMovement"])
        self.assertFalse(status["gameInputEnabled"])


if __name__ == "__main__":
    unittest.main()
