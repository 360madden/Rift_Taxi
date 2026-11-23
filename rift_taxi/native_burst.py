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


def capture_native_burst(
    *, pid: int, start_utc_ticks: int, executable_path: str,
    executable_sha256: str, window_handle: int, host: str,
    samples: int = 4, interval_ms: int = 250, max_total_s: float = 30.0,
    per_capture_s: float = 3.0,
    capture: Callable = capture_native_candidate,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Collect 2..8 independent pinned observations, refusing partial reports.

    The repeated in-file EXE hashes and OS checks add overhead; interval_ms is
    the minimum delay *after* an individual capture, not a promised sample rate.
    """
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
        report = capture(**pinned, max_capture_s=per_capture_s)
        owner, xyz, bearing, ts, bracket = _validate_sample(report, **pinned)
        if owner_key is not None and owner != owner_key:
            raise CandidateCaptureRefused("candidate player owner changed during burst")
        if prior_timestamp is not None and ts <= prior_timestamp:
            raise CandidateCaptureRefused("candidate timestamps failed to advance")
        owner_key, prior_timestamp = owner, ts
        readings.append({
            "index": i + 1, "observationMonotonicSeconds": ts,
            "xyzCandidate": list(xyz), "playerSystemBearingDegreesCandidate": bearing,
            "captureBracketSeconds": bracket,
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
        ],
    }
