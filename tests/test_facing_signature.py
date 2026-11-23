"""Offline candidate signature comparisons; no game launch, IO to game, or input."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest

from rift_taxi.facing_signature import FacingSignatureError, compare_facing_phases
from rift_taxi.cli import main

PHASES = ("baseline", "camera-only", "turn-left", "turn-right", "forward")
SHA = "df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01"
EXE = r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"


def _matrix(degrees: float) -> dict:
    rad = math.radians(degrees)
    c, s = math.cos(rad), math.sin(rad)
    bits = list(struct.unpack("<9I", struct.pack("<9f", c, 0., -s, 0., 1., 0., s, 0., c)))
    return {
        "positionSecondaryRawBits": bits[:], "actorRawBits": bits[:],
        "exactRawBitsMatch": True,
        "positionSecondaryPlanarAngleDegreesCandidate": degrees,
        "actorPlanarAngleDegreesCandidate": degrees,
        "positionMatrixStatus": "structural-y-planar-matrix-candidate",
        "actorMatrixStatus": "structural-y-planar-matrix-candidate",
        "actorHeadingQualified": False,
    }


def _burst(i: int) -> dict:
    xyz = [(1., 3., 4.), (1., 3., 4.), (1., 3., 4.),
           (1., 3., 4.), (4., 3., 8.)][i]
    yaw = (10., 10., 40., 5., 5.)[i]
    angle = (0., 0., 30., -10., -10.)[i]
    obs = [{
        "index": j + 1,
        "observationMonotonicSeconds": 100. + i * 10 + j * .25,
        "xyzCandidate": list(xyz),
        "playerSystemBearingDegreesCandidate": yaw,
        "captureBracketSeconds": .1,
        "matrixEvidence": _matrix(angle),
    } for j in range(2)]
    return {
        "schema": "taxi.native-candidate-burst/1",
        "status": "candidate-only",
        "matrixEvidenceRequested": True,
        "source": {
            "host": "LEGION", "pid": 123, "startUtcTicks": 638_000_000_000_000_000,
            "windowHandle": 8765, "executablePath": EXE,
            "onDiskExecutableSha256": SHA, "ownerKeyDecimalCandidate": "777",
        },
        "requestedSamples": 2, "completedSamples": 2,
        "observations": obs,
        "candidateChanges": {
            "movementVerified": False, "freshnessVerified": False,
            "actorHeadingVerified": False,
        },
        "matrixCandidateChanges": {
            "headingVerified": False, "sourceFreshnessVerified": False,
            "allPositionActorRawBitsMatch": True,
            "anyPositionSecondaryMatrixBitsChanged": False,
            "anyActorMatrixBitsChanged": False,
            "firstToLastActorPlanarAngleDegreesDeltaCandidate": 0.,
        },
        "evidence": {
            "inputSent": False, "gameResponseVerified": False,
            "liveArrivalVerified": False,
            "independentPositionSourceCompared": False,
        },
    }


class FacingComparisonTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.docs = [_burst(i) for i in range(5)]
        self.paths = [self.root / f"{phase}.json" for phase in PHASES]
        self.flush()

    def flush(self):
        for path, doc in zip(self.paths, self.docs):
            path.write_text(json.dumps(doc, allow_nan=True), encoding="utf8")

    def assess(self):
        return compare_facing_phases(**{
            "baseline": self.paths[0], "camera_only": self.paths[1],
            "turn_left": self.paths[2], "turn_right": self.paths[3],
            "forward": self.paths[4],
        })

    def test_valid_candidate_comparisons_without_action_or_heading_claim(self):
        report = self.assess()
        self.assertEqual(report["schema"], "taxi.facing-signature-comparison/1")
        self.assertEqual(len(report["phaseFiles"]), 5)
        self.assertEqual(len(report["phaseComparisons"]), 4)
        self.assertEqual(report["source"]["ownerKeyDecimalCandidate"], "777")
        self.assertEqual(report["phaseComparisons"][0]["candidateXzDistance"], 0)
        self.assertFalse(report["phaseComparisons"][0]["actorRawBitsChanged"])
        self.assertAlmostEqual(report["phaseComparisons"][1]["candidateActorMatrixAngleDeltaDegrees"], 30)
        self.assertAlmostEqual(report["phaseComparisons"][2]["candidateActorMatrixAngleDeltaDegrees"], -40)
        self.assertAlmostEqual(report["phaseComparisons"][3]["candidateXzDistance"], 5)
        self.assertAlmostEqual(report["phaseComparisons"][3]["candidateTravelBearingDegrees"],
                               math.degrees(math.atan2(3, 4)))
        for transition in report["phaseComparisons"]:
            self.assertFalse(transition["actionOccurredVerified"])
            self.assertFalse(transition["movementVerified"])
        self.assertFalse(report["qualifications"]["bodyHeadingVerified"])
        self.assertTrue(report["qualifications"]["phaseLabelsUserDeclaredNotObserved"])

    def test_report_source_sha_tracks_original_file_bytes(self):
        report = self.assess()
        for entry, path in zip(report["phaseFiles"], self.paths):
            self.assertEqual(entry["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(entry["samples"], 2)

    def test_cross_phase_owner_process_or_window_drift_rejected(self):
        for field, value in (
            ("ownerKeyDecimalCandidate", "778"), ("pid", 124),
            ("startUtcTicks", 638_000_000_000_000_001),
            ("windowHandle", 10), ("onDiskExecutableSha256", "f" * 64),
            ("host", "AMD-DESKTOP"), ("executablePath", r"C:\other\rift_x64.exe"),
        ):
            self.docs = [_burst(i) for i in range(5)]
            self.docs[2]["source"][field] = value
            self.flush()
            with self.subTest(field=field), self.assertRaisesRegex(
                    FacingSignatureError, "owner changed|process/build/HWND/player owner changed"):
                self.assess()

    def test_reversed_phase_timestamps_rejected(self):
        self.docs[3]["observations"][0]["observationMonotonicSeconds"] = 120.20
        self.docs[3]["observations"][1]["observationMonotonicSeconds"] = 120.40
        self.flush()
        with self.assertRaisesRegex(FacingSignatureError, "overlap"):
            self.assess()

    def test_duplicate_paths_or_not_found_fail_before_comparison(self):
        args = {
            "baseline": self.paths[0], "camera_only": self.paths[0],
            "turn_left": self.paths[2], "turn_right": self.paths[3],
            "forward": self.paths[4],
        }
        with self.assertRaisesRegex(FacingSignatureError, "distinct"):
            compare_facing_phases(**args)
        args["camera_only"] = self.root / "missing.json"
        with self.assertRaises(FileNotFoundError):
            compare_facing_phases(**args)

    def test_invalid_matrix_or_forged_qualification_rejected(self):
        changes = [
            lambda d: d.__setitem__("matrixEvidenceRequested", False),
            lambda d: d["matrixCandidateChanges"].__setitem__("headingVerified", True),
            lambda d: d["candidateChanges"].__setitem__("movementVerified", True),
            lambda d: d["evidence"].__setitem__("inputSent", True),
            lambda d: d["observations"][0]["matrixEvidence"].__setitem__("actorRawBits", [0]),
            lambda d: d["observations"][0]["matrixEvidence"].__setitem__("exactRawBitsMatch", False),
            lambda d: d["observations"][0]["matrixEvidence"].__setitem__("actorHeadingQualified", True),
        ]
        for update in changes:
            self.docs = [_burst(i) for i in range(5)]
            update(self.docs[1])
            self.flush()
            with self.subTest(update=repr(update)), self.assertRaises(FacingSignatureError):
                self.assess()

    def test_missing_samples_nonfinite_and_invalid_order_rejected(self):
        variants = [
            lambda d: d.__setitem__("completedSamples", 3),
            lambda d: d["observations"][1].__setitem__("index", 1),
            lambda d: d["observations"][1].__setitem__("observationMonotonicSeconds", 99),
            lambda d: d["observations"][0].__setitem__("xyzCandidate", [float("nan"), 0, 1]),
            lambda d: d["observations"][0].__setitem__("playerSystemBearingDegreesCandidate", 999.),
        ]
        for change in variants:
            self.docs = [_burst(i) for i in range(5)]
            change(self.docs[0])
            self.flush()
            with self.subTest(case=repr(change)), self.assertRaises(FacingSignatureError):
                self.assess()

    def test_forged_matrix_summary_is_refused(self):
        for name, value in (
            ("allPositionActorRawBitsMatch", False),
            ("anyPositionSecondaryMatrixBitsChanged", True),
            ("anyActorMatrixBitsChanged", True),
            ("firstToLastActorPlanarAngleDegreesDeltaCandidate", 90.),
        ):
            self.docs = [_burst(i) for i in range(5)]
            self.docs[1]["matrixCandidateChanges"][name] = value
            self.flush()
            with self.subTest(name=name), self.assertRaisesRegex(
                FacingSignatureError, "summary contradicts|angle delta contradicts"
            ):
                self.assess()

    def test_nonstructural_matrix_angle_remains_unavailable(self):
        for doc in self.docs:
            for row in doc["observations"]:
                matrix = row["matrixEvidence"]
                matrix["actorMatrixStatus"] = "nonfinite-matrix"
                matrix["positionMatrixStatus"] = "nonfinite-matrix"
                matrix["actorPlanarAngleDegreesCandidate"] = None
                matrix["positionSecondaryPlanarAngleDegreesCandidate"] = None
        for doc in self.docs:
            doc["matrixCandidateChanges"]["firstToLastActorPlanarAngleDegreesDeltaCandidate"] = None
        self.flush()
        report = self.assess()
        self.assertTrue(all(row["candidateActorMatrixAngleDeltaDegrees"] is None
                            for row in report["phaseComparisons"]))
        self.assertFalse(report["qualifications"]["bodyHeadingVerified"])

    def test_nonfinite_json_and_oversize_file_refused(self):
        self.paths[0].write_text('{"bad":NaN}', encoding="utf8")
        with self.assertRaisesRegex(FacingSignatureError, "nonfinite"):
            self.assess()
        self.paths[0].write_text(" " * 1_000_001, encoding="utf8")
        with self.assertRaisesRegex(FacingSignatureError, "exceeds"):
            self.assess()

    def test_cli_offline_report_writes_new_file_only(self):
        output = self.root / "comparison.json"
        argv = [
            "compare-facing-phases",
            "--baseline", str(self.paths[0]),
            "--camera-only", str(self.paths[1]),
            "--turn-left", str(self.paths[2]),
            "--turn-right", str(self.paths[3]),
            "--forward", str(self.paths[4]),
            "--out", str(output),
        ]
        self.assertEqual(main(argv), 0)
        report = json.loads(output.read_text(encoding="utf8"))
        self.assertEqual(report["status"], "offline-candidate-comparison-only")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(argv), 2)

    def test_cli_rejects_unsigned_phase_without_writing(self):
        self.docs[1]["matrixEvidenceRequested"] = False
        self.flush()
        output = self.root / "failed.json"
        argv = [
            "compare-facing-phases", "--baseline", str(self.paths[0]),
            "--camera-only", str(self.paths[1]), "--turn-left", str(self.paths[2]),
            "--turn-right", str(self.paths[3]), "--forward", str(self.paths[4]),
            "--out", str(output),
        ]
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(argv), 2)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
