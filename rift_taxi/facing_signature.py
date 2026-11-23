"""Offline comparison of five manually labeled native candidate bursts.

The labels (baseline, camera-only, turn-left, turn-right, forward) are supplied
by the operator and NOT verified action receipts. Even good correlations cannot
promote candidate matrices/XYZ to qualified body yaw or game-consumed input.

No RIFT process is opened, no network calls, no input, no sibling dependency.
"""
from __future__ import annotations

import hashlib
import json
import math
import ntpath
from pathlib import Path
import re

from .native_burst import _validate_matrix_evidence
from .native_capture import CandidateCaptureRefused

_PHASES = ("baseline", "camera-only", "turn-left", "turn-right", "forward")
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.IGNORECASE)
_OWNER = re.compile(r"[1-9][0-9]*\Z")
_MAX_FILE = 1_000_000


class FacingSignatureError(ValueError):
    """A report cannot support the requested offline candidate comparison."""


def _finite(value: object, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FacingSignatureError(f"{what} must be numeric")
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise FacingSignatureError(f"{what} cannot be represented as float") from error
    if not math.isfinite(number):
        raise FacingSignatureError(f"{what} must be finite")
    return number


def _read_json(path: Path) -> tuple[dict, str]:
    try:
        if not path.is_file() or path.stat().st_size > _MAX_FILE:
            raise FacingSignatureError("input missing or exceeds 1,000,000 bytes")
        raw = path.read_bytes()
        if len(raw) > _MAX_FILE:
            raise FacingSignatureError("input exceeds 1,000,000 bytes")
        document = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda _: (_ for _ in ()).throw(
                FacingSignatureError("nonfinite JSON constant refused")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise FacingSignatureError("invalid UTF-8 candidate burst JSON") from error
    if not isinstance(document, dict):
        raise FacingSignatureError("candidate burst root must be an object")
    return document, hashlib.sha256(raw).hexdigest()


def _source_identity(doc: dict) -> tuple:
    src = doc.get("source")
    if not isinstance(src, dict):
        raise FacingSignatureError("candidate burst source identity missing")
    host, path, sha, owner = (
        src.get("host"), src.get("executablePath"),
        src.get("onDiskExecutableSha256"), src.get("ownerKeyDecimalCandidate"),
    )
    pid, ticks, hwnd = (
        src.get("pid"), src.get("startUtcTicks"), src.get("windowHandle"),
    )
    if (not isinstance(host, str) or not host.strip()
            or not isinstance(path, str) or not ntpath.isabs(path)
            or not isinstance(sha, str) or not _SHA.fullmatch(sha)
            or not isinstance(owner, str) or not _OWNER.fullmatch(owner)
            or any(type(value) is not int or value <= 0 for value in (pid, ticks, hwnd))):
        raise FacingSignatureError("invalid exact process, window, build, or owner identity")
    return (host.casefold(), pid, ticks, ntpath.normcase(path),
            sha.casefold(), hwnd, owner)


def _burst(doc: dict, phase: str) -> dict:
    if (doc.get("schema") != "taxi.native-candidate-burst/1"
            or doc.get("status") != "candidate-only"
            or doc.get("matrixEvidenceRequested") is not True):
        raise FacingSignatureError(f"{phase}: matrix-enabled candidate burst required")
    source = _source_identity(doc)
    evidence, changes, rows = (
        doc.get("evidence"), doc.get("candidateChanges"), doc.get("observations"),
    )
    matrices = doc.get("matrixCandidateChanges")
    if not all(isinstance(section, dict) for section in (evidence, changes, matrices)):
        raise FacingSignatureError(f"{phase}: incomplete evidence sections")
    for field in ("inputSent", "gameResponseVerified", "liveArrivalVerified",
                  "independentPositionSourceCompared"):
        if evidence.get(field) is not False:
            raise FacingSignatureError(f"{phase}: {field} must remain unverified")
    for field in ("movementVerified", "freshnessVerified", "actorHeadingVerified"):
        if changes.get(field) is not False:
            raise FacingSignatureError(f"{phase}: candidate data incorrectly claims {field}")
    for field in ("headingVerified", "sourceFreshnessVerified"):
        if matrices.get(field) is not False:
            raise FacingSignatureError(f"{phase}: matrix evidence incorrectly claims {field}")
    count = doc.get("completedSamples")
    if (type(count) is not int or not 2 <= count <= 8
            or type(doc.get("requestedSamples")) is not int
            or doc["requestedSamples"] != count
            or not isinstance(rows, list) or len(rows) != count):
        raise FacingSignatureError(f"{phase}: incomplete or unbounded sample count")
    result = []
    prior_ts = None
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or type(row.get("index")) is not int or row["index"] != index:
            raise FacingSignatureError(f"{phase}: missing/out-of-order observation")
        t = _finite(row.get("observationMonotonicSeconds"), "sample timestamp")
        if t < 0 or prior_ts is not None and t <= prior_ts:
            raise FacingSignatureError(f"{phase}: nonadvancing monotonic observation")
        prior_ts = t
        xyz = row.get("xyzCandidate")
        if not isinstance(xyz, list) or len(xyz) != 3:
            raise FacingSignatureError(f"{phase}: missing XYZ candidate")
        x, y, z = (_finite(v, "XYZ") for v in xyz)
        system = _finite(row.get("playerSystemBearingDegreesCandidate"), "yaw")
        if not -180 <= system <= 180:
            raise FacingSignatureError(f"{phase}: yaw outside wrapped degree convention")
        if _finite(row.get("captureBracketSeconds"), "capture bracket") < 0:
            raise FacingSignatureError(f"{phase}: negative capture bracket")
        try:
            matrix = _validate_matrix_evidence(
                {"evidence": {"matrixEvidenceRequested": True},
                 "matrixEvidence": row.get("matrixEvidence")}, requested=True
            )
        except (ValueError, CandidateCaptureRefused) as error:
            raise FacingSignatureError(f"{phase}: {error}") from error
        result.append({
            "timestamp": t, "xyz": (x, y, z),
            "playerSystemYaw": system, "matrix": matrix,
        })
    first_matrix, last_matrix = result[0]["matrix"], result[-1]["matrix"]
    expected = {
        "allPositionActorRawBitsMatch": all(
            row["matrix"]["exactRawBitsMatch"] for row in result
        ),
        "anyPositionSecondaryMatrixBitsChanged": any(
            row["matrix"]["positionSecondaryRawBits"]
            != first_matrix["positionSecondaryRawBits"] for row in result[1:]
        ),
        "anyActorMatrixBitsChanged": any(
            row["matrix"]["actorRawBits"] != first_matrix["actorRawBits"]
            for row in result[1:]
        ),
    }
    for key, value in expected.items():
        if type(matrices.get(key)) is not bool or matrices[key] != value:
            raise FacingSignatureError(f"{phase}: matrix summary contradicts samples: {key}")
    expected_angle_delta = _angle_delta(
        first_matrix["actorPlanarAngleDegreesCandidate"],
        last_matrix["actorPlanarAngleDegreesCandidate"],
    )
    reported_delta = matrices.get("firstToLastActorPlanarAngleDegreesDeltaCandidate")
    if expected_angle_delta is None:
        if reported_delta is not None:
            raise FacingSignatureError(f"{phase}: missing matrix angle contradicts summary")
    elif (reported_delta is None
          or abs(_wrap(_finite(reported_delta, "summary matrix angle")
                       - expected_angle_delta)) > 0.00001):
        raise FacingSignatureError(f"{phase}: matrix angle delta contradicts samples")
    return {"source": source, "first": result[0], "last": result[-1],
            "count": count,
            "everyPositionActorRawMatch": expected["allPositionActorRawBitsMatch"]}


def _wrap(delta: float) -> float:
    return ((delta + 180) % 360) - 180


def _angle_delta(left: object, right: object) -> float | None:
    if left is None or right is None:
        return None
    return _wrap(float(right) - float(left))


def compare_facing_phases(*, baseline: str | Path, camera_only: str | Path,
                          turn_left: str | Path, turn_right: str | Path,
                          forward: str | Path) -> dict:
    """Compare five distinct complete locally saved bursts; no action verification."""
    paths = tuple(Path(p) for p in (baseline, camera_only, turn_left, turn_right, forward))
    resolved = [p.resolve(strict=True) for p in paths]
    if len(set(resolved)) != len(resolved):
        raise FacingSignatureError("five distinct source files are required")
    loaded = []
    for phase, path in zip(_PHASES, resolved):
        document, sha = _read_json(path)
        data = _burst(document, phase)
        loaded.append((phase, path.name, sha, data))
    baseline_identity = loaded[0][3]["source"]
    prior_last_timestamp = None
    for phase, _, _, phase_data in loaded:
        if phase_data["source"] != baseline_identity:
            raise FacingSignatureError(f"{phase}: process/build/HWND/player owner changed")
        if (prior_last_timestamp is not None
                and phase_data["first"]["timestamp"] <= prior_last_timestamp):
            raise FacingSignatureError(f"{phase}: phase observations overlap or run backward")
        prior_last_timestamp = phase_data["last"]["timestamp"]

    comparisons = []
    for (a_phase, _, _, a), (b_phase, _, _, b) in zip(loaded, loaded[1:]):
        a_last, b_last = a["last"], b["last"]
        m_a, m_b = a_last["matrix"], b_last["matrix"]
        dx = b_last["xyz"][0] - a_last["xyz"][0]
        dy = b_last["xyz"][1] - a_last["xyz"][1]
        dz = b_last["xyz"][2] - a_last["xyz"][2]
        dist = math.hypot(dx, dz)
        if not all(math.isfinite(v) for v in (dx, dy, dz, dist)):
            raise FacingSignatureError("candidate displacement arithmetic overflowed")
        comparisons.append({
            "from": a_phase,
            "to": b_phase,
            "candidateXzDistance": dist,
            "candidateDeltaXYZ": [dx, dy, dz],
            "candidateTravelBearingDegrees": (
                math.degrees(math.atan2(dx, dz)) if dist > 0 else None
            ),
            "candidatePlayerSystemYawDeltaDegrees": _angle_delta(
                a_last["playerSystemYaw"], b_last["playerSystemYaw"]),
            "candidateActorMatrixAngleDeltaDegrees": _angle_delta(
                m_a["actorPlanarAngleDegreesCandidate"],
                m_b["actorPlanarAngleDegreesCandidate"]),
            "candidatePositionMatrixAngleDeltaDegrees": _angle_delta(
                m_a["positionSecondaryPlanarAngleDegreesCandidate"],
                m_b["positionSecondaryPlanarAngleDegreesCandidate"]),
            "actorRawBitsChanged": (
                m_a["actorRawBits"] != m_b["actorRawBits"]),
            "positionRawBitsChanged": (
                m_a["positionSecondaryRawBits"] != m_b["positionSecondaryRawBits"]),
            "positionActorRawBitsMatchAtBothEndpoints": (
                m_a["exactRawBitsMatch"] and m_b["exactRawBitsMatch"]),
            "actionOccurredVerified": False,
            "movementVerified": False,
        })
    return {
        "schema": "taxi.facing-signature-comparison/1",
        "status": "offline-candidate-comparison-only",
        "source": {
            "host": baseline_identity[0],
            "pid": baseline_identity[1],
            "startUtcTicks": baseline_identity[2],
            "executablePath": baseline_identity[3],
            "onDiskExecutableSha256": baseline_identity[4],
            "windowHandle": baseline_identity[5],
            "ownerKeyDecimalCandidate": baseline_identity[6],
        },
        "phaseFiles": [{
            "phase": name, "sourceFile": filename, "sha256": sha,
            "samples": data["count"],
            "everyPositionActorRawBitsMatch": data["everyPositionActorRawMatch"],
        } for name, filename, sha, data in loaded],
        "phaseComparisons": comparisons,
        "qualifications": {
            "phaseLabelsUserDeclaredNotObserved": True,
            "inputActionReceiptsProvided": False,
            "cameraOnlyNegativeControlVerified": False,
            "bodyHeadingVerified": False,
            "passivePositionFreshnessVerified": False,
            "liveGameMovementVerified": False,
        },
        "limitations": [
            "Phase labels alone cannot establish that camera-only, turn or W actions occurred.",
            "Raw matrix consistency is a source relationship, not independent body-heading evidence.",
            "XZ displacement candidates alone do not prove a live RIFT movement response.",
            "Input receipts, visuals/game UI and exact same-clock qualification are still required.",
        ],
    }
