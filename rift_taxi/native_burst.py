"""Bounded read-only XYZ/yaw *candidate* burst for manual live qualification.

Repeated full OS-identity-bracketed captures, no game input and no promotion to
LivePose. Changes in cached XYZ/yaw do not prove passive freshness, actor
heading or observed in-game movement.
"""
from __future__ import annotations

import math
import ntpath
import re
import time
from typing import Callable

from .native_capture import capture_native_candidate, CandidateCaptureRefused


_POSITIVE_DECIMAL = re.compile(r"[1-9][0-9]*\Z")


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CandidateCaptureRefused(f"{name} is not numeric")
    x = float(value)
    if not math.isfinite(x):
        raise CandidateCaptureRefused(f"{name} is not finite")
    return x


def _validate_sample(doc: dict, *, pid: int, start_utc_ticks: int,
                     executable_path: str, executable_sha256: str,
                     window_handle: int, host: str) -> tuple:
    if not isinstance(doc, dict) or doc.get("schema") != "taxi.native-candidate/1" \
            or doc.get("status") != "candidate-only":
        raise CandidateCaptureRefused("unexpected candidate capture schema or status")
    process, raw, evidence = doc.get("process"), doc.get("candidate"), doc.get("evidence")
    if not all(isinstance(obj, dict) for obj in (process, raw, evidence)):
        raise CandidateCaptureRefused("candidate capture lacks required sections")
    if (type(process.get("pid")) is not int or process["pid"] != pid
            or type(process.get("startUtcTicks")) is not int
            or process["startUtcTicks"] != start_utc_ticks
            or type(process.get("windowHandle")) is not int
            or process["windowHandle"] != window_handle
            or not isinstance(process.get("host"), str)
            or process["host"].casefold() != host.casefold()
            or not isinstance(process.get("executablePath"), str)
            or ntpath.normcase(process["executablePath"]) != ntpath.normcase(executable_path)
            or not isinstance(process.get("onDiskExecutableSha256"), str)
            or process["onDiskExecutableSha256"].casefold() != executable_sha256.casefold()):
        raise CandidateCaptureRefused("candidate burst process/window/build identity changed")

    if (process.get("foregroundAtStartAndEnd") is not True
            or evidence.get("actorHeadingQualified") is not False
            or evidence.get("passivePositionFreshnessQualified") is not False
            or evidence.get("liveInGameResponseVerified") is not False
            or evidence.get("inputSent") is not False
            or evidence.get("arrivalVerified") is not False):
        raise CandidateCaptureRefused("capture flags unexpectedly claim qualification or input")
    owner = raw.get("ownerKeyDecimal")
    if not isinstance(owner, str) or not _POSITIVE_DECIMAL.fullmatch(owner):
        raise CandidateCaptureRefused("candidate player owner is missing")
    xyz = raw.get("xyz")
    if not isinstance(xyz, list) or len(xyz) != 3:
        raise CandidateCaptureRefused("candidate XYZ is missing")
    x, y, z = (_number(v, "XYZ") for v in xyz)
    yaw = _number(raw.get("playerSystemBearingDegrees"), "yaw")
    ts = _number(raw.get("observationMonotonicSeconds"), "timestamp")
    bracket = _number(evidence.get("captureBracketSeconds"), "capture bracket")
    if ts < 0 or bracket < 0:
        raise CandidateCaptureRefused("candidate clock or bracket is negative")
    return (owner, (x, y, z), yaw, ts, bracket)


def _validate_matrix_evidence(doc: dict, *, requested: bool) -> dict | None:
    """Validate raw evidence consistency; never infer verified actor heading."""
    evidence = doc["evidence"]
    matrix = doc.get("matrixEvidence")
    request_flag = evidence.get("matrixEvidenceRequested", False)
    if type(request_flag) is not bool or request_flag != requested:
        raise CandidateCaptureRefused("matrix evidence request flag mismatch")
    if not requested:
        if matrix is not None:
            raise CandidateCaptureRefused("unsolicited matrix evidence in ordinary burst")
        return None
    if not isinstance(matrix, dict) or matrix.get("actorHeadingQualified") is not False:
        raise CandidateCaptureRefused("requested unqualified matrix evidence missing")
    fields = ("positionSecondaryRawBits", "actorRawBits")
    normalized = {}
    for field in fields:
        bits = matrix.get(field)
        if (not isinstance(bits, list) or len(bits) != 9
                or any(type(x) is not int or not 0 <= x <= 0xFFFFFFFF for x in bits)):
            raise CandidateCaptureRefused(f"{field} must have 9 unsigned float32 bit patterns")
        normalized[field] = bits[:]
    same = matrix.get("exactRawBitsMatch")
    if type(same) is not bool or same != (normalized[fields[0]] == normalized[fields[1]]):
        raise CandidateCaptureRefused("matrix raw-bit match flag contradicts source bytes")
    normalized["exactRawBitsMatch"] = same
    for prefix, status_field, angle_field in (
        ("position", "positionMatrixStatus", "positionSecondaryPlanarAngleDegreesCandidate"),
        ("actor", "actorMatrixStatus", "actorPlanarAngleDegreesCandidate"),
    ):
        status = matrix.get(status_field)
        if status not in (
            "structural-y-planar-matrix-candidate", "unqualified-matrix-shape", "nonfinite-matrix"
        ):
            raise CandidateCaptureRefused(f"{prefix} matrix status unrecognized")
        angle = matrix.get(angle_field)
        if status == "structural-y-planar-matrix-candidate":
            if angle is None or not -180 <= _number(angle, f"{prefix} planar angle") <= 180:
                raise CandidateCaptureRefused(f"{prefix} structural matrix requires bounded planar angle")
        elif angle is not None:
            raise CandidateCaptureRefused(f"{prefix} unqualified matrix cannot claim planar angle")
        normalized[status_field] = status
        normalized[angle_field] = angle
    if same and (normalized["positionMatrixStatus"] != normalized["actorMatrixStatus"]
                 or normalized["positionSecondaryPlanarAngleDegreesCandidate"]
                 != normalized["actorPlanarAngleDegreesCandidate"]):
        raise CandidateCaptureRefused("identical raw matrix bits contradict matrix interpretation")
    normalized["actorHeadingQualified"] = False
    return normalized


def _validate_refresh_guard(doc: dict, *, requested: bool) -> dict | None:
    """Validate co-sampled branch inputs, never promote writer/freshness claims."""
    evidence = doc["evidence"]
    payload = doc.get("refreshGuardEvidence")
    request_flag = evidence.get("refreshGuardEvidenceRequested", False)
    if type(request_flag) is not bool or request_flag != requested:
        raise CandidateCaptureRefused("refresh guard request flag mismatch")
    if not requested:
        if payload is not None:
            raise CandidateCaptureRefused("unsolicited refresh guard evidence")
        return None
    if not isinstance(payload, dict) or payload.get("knownWriterExecuted") is not False \
            or payload.get("passiveXyzFreshnessQualified") is not False \
            or payload.get("apiGetterMayRefreshCache") is not True:
        raise CandidateCaptureRefused("refresh guard cannot claim writer execution or freshness")
    decimal, hex_text, flag = (
        payload.get("refreshHandleDecimal"), payload.get("refreshHandleHex"),
        payload.get("refreshFlagRaw")
    )
    if (not isinstance(decimal, str) or not re.fullmatch(r"0|[1-9][0-9]*", decimal)
            or not isinstance(hex_text, str)
            or not re.fullmatch(r"0x[0-9A-F]{16}", hex_text)
            or type(flag) is not int or not 0 <= flag <= 255):
        raise CandidateCaptureRefused("invalid cached position refresh guard format")
    handle = int(decimal)
    if handle > 0xFFFFFFFFFFFFFFFF or f"0x{handle:016X}" != hex_text:
        raise CandidateCaptureRefused("refresh guard handle/hex inconsistency")
    expected = ("handle-present-guard-candidate" if handle != 0
                else "alternate-flag-guard-candidate" if flag != 0
                else "both-known-top-level-routes-ineligible-candidate")
    if payload.get("topLevelBranchCandidate") != expected:
        raise CandidateCaptureRefused("refresh guard status contradicts raw source bytes")
    return {
        "refreshHandleDecimal": decimal,
        "refreshHandleHex": hex_text,
        "refreshFlagRaw": flag,
        "topLevelBranchCandidate": expected,
        "knownWriterExecuted": False,
        "passiveXyzFreshnessQualified": False,
        "apiGetterMayRefreshCache": True,
    }


def capture_native_burst(
    *, pid: int, start_utc_ticks: int, executable_path: str,
    executable_sha256: str, window_handle: int, host: str,
    samples: int = 4, interval_ms: int = 250, max_total_s: float = 30.0,
    per_capture_s: float = 3.0,
    include_matrix_candidate: bool = False,
    include_refresh_guard_candidate: bool = False,
    capture: Callable = capture_native_candidate,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Collect 2..8 independent pinned observations, refusing partial reports.

    The repeated in-file EXE hashes and OS checks add overhead; interval_ms is
    the minimum delay *after* an individual capture, not a promised sample rate.
    """
    if type(include_matrix_candidate) is not bool:
        raise ValueError("include_matrix_candidate must be bool")
    if type(include_refresh_guard_candidate) is not bool:
        raise ValueError("include_refresh_guard_candidate must be bool")
    if type(samples) is not int or not 2 <= samples <= 8:
        raise ValueError("samples must be between 2 and 8")
    if type(interval_ms) is not int or not 0 <= interval_ms <= 1500:
        raise ValueError("interval_ms must be between 0 and 1500")
    if isinstance(max_total_s, bool) or not isinstance(max_total_s, (float, int)) \
            or not math.isfinite(max_total_s) or not 2 <= max_total_s <= 60:
        raise ValueError("max_total_s must be finite and between 2 and 60")
    if isinstance(per_capture_s, bool) or not isinstance(per_capture_s, (float, int)) \
            or not math.isfinite(per_capture_s) or not .05 <= per_capture_s <= 10:
        raise ValueError("per_capture_s must be finite and between .05 and 10")
    if not callable(clock) or not callable(sleep) or not callable(capture):
        raise ValueError("capture, clock and sleep must be callable")

    # Basic pin shape is validated before attempting the first capture.
    if type(pid) is not int or pid <= 0 or type(start_utc_ticks) is not int or start_utc_ticks <= 0 \
            or type(window_handle) is not int or window_handle <= 0:
        raise ValueError("positive PID, start-ticks, and HWND are required")
    if not isinstance(executable_path, str) or not ntpath.isabs(executable_path) \
            or not isinstance(executable_sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", executable_sha256) \
            or not isinstance(host, str) or not host.strip() or host != host.strip():
        raise ValueError("absolute executable, SHA-256, and exact host required")

    begin = _number(clock(), "burst clock")
    readings: list[dict] = []
    owner_key: str | None = None
    prior_timestamp: float | None = None
    pinned = dict(pid=pid, start_utc_ticks=start_utc_ticks,
                  executable_path=executable_path, executable_sha256=executable_sha256,
                  window_handle=window_handle, host=host)
    for i in range(samples):
        if _number(clock(), "burst clock") - begin > max_total_s:
            raise CandidateCaptureRefused("native burst duration exceeded budget")
        decode_options = {}
        if include_matrix_candidate:
            decode_options["include_matrix_candidate"] = True
        if include_refresh_guard_candidate:
            decode_options["include_refresh_guard_candidate"] = True
        report = capture(**pinned, max_capture_s=per_capture_s, **decode_options)
        owner, xyz, bearing, ts, bracket = _validate_sample(report, **pinned)
        matrix = _validate_matrix_evidence(report, requested=include_matrix_candidate)
        guard = _validate_refresh_guard(report, requested=include_refresh_guard_candidate)
        if owner_key is not None and owner != owner_key:
            raise CandidateCaptureRefused("candidate player owner changed during burst")
        if prior_timestamp is not None and ts <= prior_timestamp:
            raise CandidateCaptureRefused("candidate timestamps failed to advance")
        owner_key, prior_timestamp = owner, ts
        readings.append({
            "index": i + 1, "observationMonotonicSeconds": ts,
            "xyzCandidate": list(xyz), "playerSystemBearingDegreesCandidate": bearing,
            "captureBracketSeconds": bracket,
            **({"matrixEvidence": matrix} if matrix is not None else {}),
            **({"refreshGuardEvidence": guard} if guard is not None else {}),
        })
        if _number(clock(), "burst clock") - begin > max_total_s:
            raise CandidateCaptureRefused("native burst duration exceeded budget")
        if i + 1 < samples and interval_ms:
            sleep(interval_ms / 1000)

    a, b = readings[0], readings[-1]
    xyz_a, xyz_b = a["xyzCandidate"], b["xyzCandidate"]
    delta = tuple(r - l for l, r in zip(xyz_a, xyz_b))
    bearing_delta = ((b["playerSystemBearingDegreesCandidate"]
                      - a["playerSystemBearingDegreesCandidate"] + 180) % 360) - 180
    total = _number(clock(), "burst clock") - begin
    if not 0 <= total <= max_total_s:
        raise CandidateCaptureRefused("native burst duration exceeded budget")
    matrix_changes = None
    if include_matrix_candidate:
        raw_matrices = [row["matrixEvidence"] for row in readings]
        a_matrix, b_matrix = raw_matrices[0], raw_matrices[-1]
        angle_a = a_matrix["actorPlanarAngleDegreesCandidate"]
        angle_b = b_matrix["actorPlanarAngleDegreesCandidate"]
        matrix_changes = {
            "allPositionActorRawBitsMatch": all(row["exactRawBitsMatch"] for row in raw_matrices),
            "anyPositionSecondaryMatrixBitsChanged": any(
                row["positionSecondaryRawBits"] != a_matrix["positionSecondaryRawBits"]
                for row in raw_matrices[1:]
            ),
            "anyActorMatrixBitsChanged": any(
                row["actorRawBits"] != a_matrix["actorRawBits"] for row in raw_matrices[1:]
            ),
            "firstToLastActorPlanarAngleDegreesDeltaCandidate": (
                ((angle_b - angle_a + 180) % 360) - 180
                if angle_a is not None and angle_b is not None else None
            ),
            "headingVerified": False,
            "sourceFreshnessVerified": False,
        }
    refresh_changes = None
    if include_refresh_guard_candidate:
        records = [row["refreshGuardEvidence"] for row in readings]
        reference = records[0]
        refresh_changes = {
            "allKnownTopLevelRoutesIneligible": all(
                row["topLevelBranchCandidate"]
                == "both-known-top-level-routes-ineligible-candidate" for row in records
            ),
            "anyRefreshHandleChanged": any(
                row["refreshHandleDecimal"] != reference["refreshHandleDecimal"]
                for row in records[1:]
            ),
            "anyRefreshFlagChanged": any(
                row["refreshFlagRaw"] != reference["refreshFlagRaw"]
                for row in records[1:]
            ),
            "knownWriterExecutionVerified": False,
            "passiveXyzFreshnessVerified": False,
        }
    return {
        "schema": "taxi.native-candidate-burst/1",
        "status": "candidate-only",
        "source": {
            "host": host, "pid": pid, "startUtcTicks": start_utc_ticks,
            "windowHandle": window_handle, "executablePath": executable_path,
            "onDiskExecutableSha256": executable_sha256.lower(),
            "ownerKeyDecimalCandidate": owner_key,
        },
        "requestedSamples": samples,
        "completedSamples": len(readings),
        "requestedMinGapMs": interval_ms,
        "totalElapsedSeconds": total,
        "matrixEvidenceRequested": include_matrix_candidate,
        "matrixCandidateChanges": matrix_changes,
        "refreshGuardEvidenceRequested": include_refresh_guard_candidate,
        "refreshGuardChanges": refresh_changes,
        "observations": readings,
        "candidateChanges": {
            "firstToLastXzDistanceSourceUnits": math.hypot(delta[0], delta[2]),
            "firstToLast3dDistanceSourceUnits": math.hypot(*delta),
            "firstToLastYawDeltaDegrees": bearing_delta,
            "anyXyzChanged": any(readings[i]["xyzCandidate"] != readings[0]["xyzCandidate"]
                                 for i in range(1, samples)),
            "anyYawChanged": any(readings[i]["playerSystemBearingDegreesCandidate"]
                                 != readings[0]["playerSystemBearingDegreesCandidate"]
                                 for i in range(1, samples)),
            "movementVerified": False,
            "freshnessVerified": False,
            "actorHeadingVerified": False,
        },
        "evidence": {
            "captureBracketsPerSample": samples, "inputSent": False,
            "gameResponseVerified": False, "liveArrivalVerified": False,
            "independentPositionSourceCompared": False,
        },
        "limitations": [
            "Candidate change alone does not establish RIFT player motion or cache freshness.",
            "Unchanged values can mean stationary gameplay OR stale cached values.",
            "Observed yaw is player-system candidate, not qualified actor-facing yaw.",
            "Each capture independently rechecks executable, PID epoch and HWND; no atomic multi-frame guarantee.",
            "Samples may be spaced farther apart than requested due to repeated hash/read overhead.",
            "Optional actor/position matrix bit agreement is not independently verified body heading.",
            "Cached XYZ guard eligibility does not prove writer execution or passive freshness.",
        ],
    }
