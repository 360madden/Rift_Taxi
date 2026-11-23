"""Explicit, pinned read-only native candidate capture for RIFT Taxi.

No automatic process discovery, background polling, game inputs, pose promotion,
or sibling-runtime use. This is evidence collection, not a game controller.
"""
from __future__ import annotations

import math
from typing import Callable

from .native_candidate import (
    PositionFacingCandidate,
    decode_current_build_candidate,
)
from .native_memory import ProcessPin, ReadOnlyNativeSession
from .win32_identity import DesktopCandidate, inspect_desktop


class CandidateCaptureRefused(RuntimeError):
    """Native evidence capture was not bounded or not tied to one exact owner."""


def _owner(candidate: DesktopCandidate) -> tuple:
    return (
        candidate.host.casefold(), candidate.pid, candidate.start_utc_ticks,
        candidate.executable_path.casefold(), candidate.executable_sha256.casefold(),
        candidate.window_handle,
    )


def capture_native_candidate(
    *,
    pid: int,
    start_utc_ticks: int,
    executable_path: str,
    executable_sha256: str,
    window_handle: int,
    host: str,
    max_capture_s: float = 3.0,
    include_matrix_candidate: bool = False,
    include_refresh_guard_candidate: bool = False,
    include_actor_translation_candidate: bool = False,
    inspect: Callable = inspect_desktop,
    open_session: Callable = ReadOnlyNativeSession.open,
    decode: Callable = decode_current_build_candidate,
) -> dict:
    """Return an unqualified candidate report or refuse without publishing.

    Every target identity dimension is mandatory. The two OS inspections
    bracket a single read-only process session; changed ownership/foreground,
    stale source, or failed candidate decoding aborts the entire report.
    """
    if type(include_matrix_candidate) is not bool:
        raise ValueError("include_matrix_candidate must be bool")
    if type(include_refresh_guard_candidate) is not bool:
        raise ValueError("include_refresh_guard_candidate must be bool")
    if type(include_actor_translation_candidate) is not bool:
        raise ValueError("include_actor_translation_candidate must be bool")
    if type(start_utc_ticks) is not int or start_utc_ticks <= 0:
        raise ValueError("explicit positive process start UTC ticks are required")
    if type(window_handle) is not int or window_handle <= 0:
        raise ValueError("explicit positive window HWND is required")
    if not isinstance(host, str) or not host.strip() or host != host.strip():
        raise ValueError("exact trimmed host identity is required")
    if isinstance(max_capture_s, bool) or not isinstance(max_capture_s, (float, int)):
        raise ValueError("capture budget must be finite and positive")
    if not math.isfinite(max_capture_s) or not 0.05 <= max_capture_s <= 10.0:
        raise ValueError("capture budget must be between 0.05 and 10 seconds")

    options = dict(
        expected_executable_path=executable_path,
        expected_executable_sha256=executable_sha256,
        expected_start_utc_ticks=start_utc_ticks,
        expected_window_handle=window_handle,
        expected_host=host,
        require_foreground=True,
    )
    first: DesktopCandidate = inspect(pid, **options)
    if not isinstance(first, DesktopCandidate):
        raise CandidateCaptureRefused("invalid Windows identity observation")
    pin = ProcessPin(
        pid=first.pid, start_utc_ticks=first.start_utc_ticks,
        executable_path=first.executable_path,
        executable_sha256=first.executable_sha256,
    )
    with open_session(pin) as session:
        decode_options = {}
        if include_matrix_candidate:
            decode_options["include_matrix_candidate"] = True
        if include_refresh_guard_candidate:
            decode_options["include_refresh_guard_candidate"] = True
        if include_actor_translation_candidate:
            decode_options["include_actor_translation_candidate"] = True
        raw: PositionFacingCandidate = decode(session, **decode_options)
    final: DesktopCandidate = inspect(pid, **options)

    if not isinstance(final, DesktopCandidate):
        raise CandidateCaptureRefused("invalid Windows identity observation")
    if not first.foreground or not final.foreground or _owner(first) != _owner(final):
        raise CandidateCaptureRefused("process/window identity changed during native capture")
    if not isinstance(raw, PositionFacingCandidate):
        raise CandidateCaptureRefused("native observation was not an unqualified candidate")
    if (raw.process_id != pin.pid
            or raw.process_start_utc_ticks != pin.start_utc_ticks
            or raw.build_sha256.casefold() != pin.executable_sha256.casefold()):
        raise CandidateCaptureRefused("native candidate source identity mismatch")
    elapsed = final.observed_monotonic_s - first.observed_monotonic_s
    if not math.isfinite(elapsed) or not 0 <= elapsed <= max_capture_s:
        raise CandidateCaptureRefused("native capture exceeded same-clock time budget")
    if not (first.observed_monotonic_s <= raw.observed_monotonic_s
            <= final.observed_monotonic_s):
        raise CandidateCaptureRefused("candidate observation outside OS capture bracket")
    if raw.actor_heading_qualified or raw.passive_position_freshness_qualified:
        raise CandidateCaptureRefused("candidate cannot be advertised as qualified")
    matrix = raw.matrix_copy_candidate
    if include_matrix_candidate and matrix is None:
        raise CandidateCaptureRefused("requested matrix candidate evidence missing")
    if matrix is not None and matrix.body_heading_qualified:
        raise CandidateCaptureRefused("matrix evidence is not qualified body heading")
    matrix_evidence = None
    if matrix is not None:
        matrix_evidence = {
            "positionSecondaryRawBits": list(matrix.position_secondary_raw_bits),
            "actorRawBits": list(matrix.actor_raw_bits),
            "exactRawBitsMatch": matrix.exact_bits_match,
            "positionSecondaryPlanarAngleDegreesCandidate": matrix.position_planar_angle_degrees_candidate,
            "actorPlanarAngleDegreesCandidate": matrix.actor_planar_angle_degrees_candidate,
            "positionMatrixStatus": matrix.position_matrix_status,
            "actorMatrixStatus": matrix.actor_matrix_status,
            "actorHeadingQualified": False,
        }

    guard = raw.refresh_guard_candidate
    if include_refresh_guard_candidate and guard is None:
        raise CandidateCaptureRefused("requested refresh-guard evidence missing")
    if guard is not None and (
        guard.known_writer_executed or guard.passive_xyz_freshness_qualified
    ):
        raise CandidateCaptureRefused("refresh guard cannot establish writer execution")
    guard_evidence = None
    if guard is not None:
        guard_evidence = {
            "refreshHandleDecimal": guard.handle_decimal,
            "refreshHandleHex": guard.handle_hex,
            "refreshFlagRaw": guard.flag_raw,
            "topLevelBranchCandidate": guard.top_level_branch,
            "knownWriterExecuted": False,
            "passiveXyzFreshnessQualified": False,
            "apiGetterMayRefreshCache": True,
        }

    actor_position = raw.actor_translation_candidate
    if include_actor_translation_candidate and actor_position is None:
        raise CandidateCaptureRefused("requested actor-translation evidence missing")
    if actor_position is not None and (
        actor_position.independently_fresh or actor_position.authoritative_player_position
    ):
        raise CandidateCaptureRefused("model translation cannot be verified live player position")
    actor_translation_evidence = None
    if actor_position is not None:
        actor_translation_evidence = {
            "positionSecondaryXyz": list(actor_position.secondary_cache_xyz),
            "actorStoredWorldTranslationCandidate": list(actor_position.actor_stored_xyz),
            "offsetAt04F8": list(actor_position.offset_4f8_xyz),
            "offsetAt0770": list(actor_position.offset_770_xyz),
            "reconstructedActorWorldTranslationCandidate": list(
                actor_position.reconstructed_actor_xyz
            ),
            "reconstructionMaxAbsDelta": actor_position.reconstruction_max_abs_delta,
            "primarySecondaryMaxAbsDelta": actor_position.primary_secondary_max_abs_delta,
            "actorFlagsRaw": actor_position.actor_flags,
            "renderBranchStatus": actor_position.render_status,
            "normalRenderWorldTranslationCandidate": (
                list(actor_position.render_xyz) if actor_position.render_xyz is not None else None
            ),
            "actorRenderMaxAbsDelta": actor_position.actor_render_max_abs_delta,
            "independentlyFresh": False,
            "authoritativePlayerPosition": False,
        }

    # Output is structured metadata, never a LivePose. No game response is inferred.
    return {
        "schema": "taxi.native-candidate/1",
        "status": "candidate-only",
        "qualification": raw.qualification,
        "matrixEvidence": matrix_evidence,
        "refreshGuardEvidence": guard_evidence,
        "actorTranslationEvidence": actor_translation_evidence,
        "runtimeDependencies": "python-stdlib-only",
        "process": {
            "host": first.host,
            "pid": first.pid,
            "startUtcTicks": first.start_utc_ticks,
            "executablePath": first.executable_path,
            "onDiskExecutableSha256": first.executable_sha256,
            "windowHandle": first.window_handle,
            "foregroundAtStartAndEnd": True,
        },
        "candidate": {
            "ownerKeyDecimal": str(raw.owner_key),
            "xyz": list(raw.xyz_candidate),
            "playerSystemYawRadians": raw.yaw_radians_candidate,
            "playerSystemBearingDegrees": raw.yaw_bearing_deg_candidate,
            "observationMonotonicSeconds": raw.observed_monotonic_s,
        },
        "evidence": {
            "captureBracketSeconds": elapsed,
            "actorHeadingQualified": False,
            "matrixEvidenceRequested": include_matrix_candidate,
            "refreshGuardEvidenceRequested": include_refresh_guard_candidate,
            "actorTranslationEvidenceRequested": include_actor_translation_candidate,
            "passivePositionFreshnessQualified": False,
            "liveInGameResponseVerified": False,
            "inputSent": False,
            "loadedModuleBytesHashed": False,
            "arrivalVerified": False,
        },
    }
