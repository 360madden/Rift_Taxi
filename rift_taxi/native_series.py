"""Bounded high-cadence, same-handle read-only native candidate time series.

Unlike the original 'burst', each series pins the exact process/build/HWND
once, opens ONE read-only process handle, and performs fast OS identity/foreground
checks before and after EVERY separately owner-resolved native candidate.
A full executable-SHA/window admission brackets the entire series.

No key/mouse input, injected movement, native writes, Lua calls, auto-selection,
or promotion to a qualified actor pose. Original samples remain candidate-only.
"""
from __future__ import annotations

import math
import ntpath
import statistics
import time
from typing import Callable, Protocol

from .native_candidate import PositionFacingCandidate, decode_current_build_candidate
from .native_capture import CandidateCaptureRefused
from .native_memory import ProcessPin, MainModule, ReadOnlyNativeSession
from .key_observation import (
    KeyObservationUnavailable, KeySnapshotSource, Win32KeySnapshot,
    validate_key_snapshot,
)
from .win32_identity import (
    DesktopCandidate, DesktopProbeApi, ProcessInfo, Win32DesktopProbe, inspect_desktop,
)

_MAX_SAMPLES = 128


class SeriesUnavailable(CandidateCaptureRefused):
    """A read-only native series could not retain exact source qualification."""


class FastProbe(DesktopProbeApi, Protocol):
    """Read-only Windows process/window metadata; never uses input."""


def _path(path: str) -> str:
    if not isinstance(path, str) or not ntpath.isabs(path):
        raise ValueError("executable path must be absolute")
    return ntpath.normcase(ntpath.normpath(path))


def _valid_clock(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SeriesUnavailable("monotonic clock is not numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise SeriesUnavailable("monotonic clock invalid")
    return result


def _same_desktop(
    first: DesktopCandidate, other: DesktopCandidate,
    *, host: str, pid: int, ticks: int, path: str, sha: str, hwnd: int,
) -> bool:
    return (
        isinstance(first, DesktopCandidate) and isinstance(other, DesktopCandidate)
        and first.foreground and other.foreground
        and all(
            x.host.casefold() == host.casefold()
            and x.pid == pid and x.start_utc_ticks == ticks
            and _path(x.executable_path) == _path(path)
            and x.executable_sha256.casefold() == sha.casefold()
            and x.window_handle == hwnd
            for x in (first, other)
        )
    )


def _fast_pin(
    api: FastProbe, *, host: str, pid: int, ticks: int, path: str, hwnd: int,
) -> None:
    """Read-only short per-sample check. Disk SHA is pinned at both series ends."""
    try:
        process = api.process(pid)
        ok = (
            isinstance(process, ProcessInfo)
            and process.pid == pid and process.start_utc_ticks == ticks
            and _path(process.executable_path) == _path(path)
            and api.host().casefold() == host.casefold()
            and api.window_belongs_to_pid(hwnd, pid)
            # windows_for_pid excludes hidden/minimized/owned windows.
            and hwnd in api.windows_for_pid(pid)
            and api.foreground_root() == hwnd
        )
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
        ok = False
    if not ok:
        raise SeriesUnavailable("process epoch, exact window or foreground changed during series")


def _row(raw: PositionFacingCandidate, index: int, *,
         matrix: bool, guard: bool, translation: bool, zone: bool = False) -> dict:
    if not isinstance(raw, PositionFacingCandidate):
        raise SeriesUnavailable("native reader did not return a candidate")
    if (raw.actor_heading_qualified is not False
            or raw.passive_position_freshness_qualified is not False
            or type(raw.owner_key) is not int or raw.owner_key <= 0
            or len(raw.xyz_candidate) != 3
            or not all(math.isfinite(float(v)) for v in raw.xyz_candidate)
            or not math.isfinite(raw.yaw_bearing_deg_candidate)):
        raise SeriesUnavailable("native reader returned unqualified or invalid fields")
    record = {
        "index": index,
        "ownerKeyDecimal": str(raw.owner_key),
        "observedMonotonicSeconds": raw.observed_monotonic_s,
        "xyzCandidate": list(raw.xyz_candidate),
        "playerSystemBearingDegreesCandidate": raw.yaw_bearing_deg_candidate,
        "actorHeadingVerified": False, "positionFreshnessVerified": False,
    }
    if matrix:
        m = raw.matrix_copy_candidate
        if (m is None or m.body_heading_qualified is not False
                or len(m.actor_raw_bits) != 9 or len(m.position_secondary_raw_bits) != 9
                or type(m.exact_bits_match) is not bool
                or m.exact_bits_match != (m.actor_raw_bits == m.position_secondary_raw_bits)):
            raise SeriesUnavailable("optional matrix evidence missing or contradictory")
        record["matrixEvidence"] = {
            "actorRawBits": list(m.actor_raw_bits),
            "positionSecondaryRawBits": list(m.position_secondary_raw_bits),
            "rawBitsMatch": m.exact_bits_match,
            "actorPlanarAngleDegreesCandidate": m.actor_planar_angle_degrees_candidate,
            "positionPlanarAngleDegreesCandidate": m.position_planar_angle_degrees_candidate,
            "actorHeadingVerified": False,
        }
    if guard:
        g = raw.refresh_guard_candidate
        if g is None or g.known_writer_executed or g.passive_xyz_freshness_qualified:
            raise SeriesUnavailable("optional refresh-guard evidence invalid")
        record["refreshGuardEvidence"] = {
            "handleDecimal": g.handle_decimal,
            "flagRaw": g.flag_raw,
            "topLevelBranchCandidate": g.top_level_branch,
            "knownWriterExecuted": False, "passiveFreshnessVerified": False,
        }
    if translation:
        t = raw.actor_translation_candidate
        if t is None or t.independently_fresh or t.authoritative_player_position:
            raise SeriesUnavailable("optional actor-world translation evidence invalid")
        record["actorTranslationEvidence"] = {
            "actorStoredXYZCandidate": list(t.actor_stored_xyz),
            "secondaryXYZCandidate": list(t.secondary_cache_xyz),
            "reconstructionResidual": t.reconstruction_max_abs_delta,
            "renderBranch": t.render_status,
            "independentlyFresh": False,
        }
    if zone:
        z = raw.zone_key_candidate
        if (z is None or type(z.raw_zone_key) is not int
                or not 0 <= z.raw_zone_key <= 0xFFFFFFFF
                or z.authoritative_zone_qualified is not False
                or z.source_status != "same-owner-typed-raw-zone-key-candidate"
                or z.public_zone_id_status != "not-derived"
                or z.world_instance_status != "unavailable"):
            raise SeriesUnavailable("optional raw same-owner zone key missing/invalid")
        record["zoneKeyEvidence"] = {
            "rawSelfZoneKey": z.raw_zone_key,
            "rawSelfZoneKeyHex": f"0x{z.raw_zone_key:08X}",
            "sourceStatus": z.source_status,
            "publicZoneIdStatus": "not-derived",
            "worldInstanceStatus": "unavailable",
            "authoritativeZoneQualified": False,
        }
    return record



def _poll_keys(keyboard: KeySnapshotSource, clock: Callable[[], float]) -> dict:
    started = _valid_clock(clock())
    try:
        states = validate_key_snapshot(keyboard.snapshot())
    except (KeyObservationUnavailable, OSError) as error:
        raise SeriesUnavailable("read-only W/A/D key polling unavailable") from error
    ended = _valid_clock(clock())
    # A slow or paused keyboard probe breaks the timing interpretation.
    if not 0 <= ended - started <= 0.05:
        raise SeriesUnavailable("read-only W/A/D key snapshot exceeded 50 ms budget")
    return {"keys": states, "atMonotonicSeconds": ended}


def summarize_key_snapshots(rows: list[dict]) -> dict:
    """Summarize *sampled* OS key bits, never inferred key-send or game events."""
    names = ("W", "A", "D")
    down_counts = {name: 0 for name in names}
    transitions: list[dict] = []
    previous: dict | None = None
    unstable = 0
    for row in rows:
        state = row["manualWindowsKeyStates"]
        if not state["unchangedDuringNativeRead"]:
            unstable += 1
        for phase in ("beforeNativeRead", "afterNativeRead"):
            snapshot = state[phase]
            now = snapshot["atMonotonicSeconds"]
            for key in names:
                current_down = snapshot["keys"][key]
                down_counts[key] += int(current_down)
                if previous is not None and previous["keys"][key] != current_down:
                    transitions.append({
                        "key": key,
                        "previousSampleIndex": previous["sampleIndex"],
                        "currentSampleIndex": row["index"],
                        "previousPollPhase": previous["phase"],
                        "currentPollPhase": phase,
                        "fromDown": previous["keys"][key],
                        "toDown": current_down,
                        "earliestObservedBoundaryMonotonicSeconds": previous["time"],
                        "latestObservedBoundaryMonotonicSeconds": now,
                        "transitionInstantVerified": False,
                        "gameInputConsumptionVerified": False,
                    })
            previous = {
                "keys": snapshot["keys"], "time": now,
                "phase": phase, "sampleIndex": row["index"],
            }
    return {
        "samples": len(rows),
        "pollsPerKey": 2 * len(rows),
        "observedDownPollsByKey": down_counts,
        "nativeReadBracketsWithChangingKeys": unstable,
        "sampledStateTransitionWindows": transitions,
        "continuousKeyStateTracking": False,
        "shortPressesCanBeMissed": True,
        "source": "Win32 GetAsyncKeyState high-bit read-only polling",
        "operatorActionVerified": False,
        "gameInputConsumptionVerified": False,
        "inputInjectedByTaxi": False,
    }


def observe_native_series(
    *, pid: int, start_utc_ticks: int, executable_path: str,
    executable_sha256: str, window_handle: int, host: str,
    samples: int = 16, interval_ms: int = 150, max_total_s: float = 20.,
    include_matrix_candidate: bool = True,
    include_refresh_guard_candidate: bool = True,
    include_actor_translation_candidate: bool = False,
    include_zone_key_candidate: bool = False,
    observe_manual_keys: bool = False,
    inspect: Callable = inspect_desktop,
    api_factory: Callable[[], FastProbe] = Win32DesktopProbe,
    open_session: Callable = ReadOnlyNativeSession.open,
    keyboard_factory: Callable[[], KeySnapshotSource] = Win32KeySnapshot,
    decode: Callable = decode_current_build_candidate,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Return all complete same-owner observations or raise without a report.

    Interval is requested *start-to-start* spacing, not guaranteed cadence.
    Samples may take longer; no catch-up burst or synthetic timestamps.
    """
    if type(samples) is not int or not 3 <= samples <= _MAX_SAMPLES:
        raise ValueError("samples must be 3..128")
    if type(interval_ms) is not int or not 25 <= interval_ms <= 2000:
        raise ValueError("interval_ms must be 25..2000")
    if (isinstance(max_total_s, bool) or not isinstance(max_total_s, (int, float))
            or not math.isfinite(max_total_s) or not 2 <= max_total_s <= 60):
        raise ValueError("max_total_s must be finite, 2..60 seconds")
    if any(type(b) is not bool for b in (include_matrix_candidate,
                                        include_refresh_guard_candidate,
                                        include_actor_translation_candidate,
                                        include_zone_key_candidate, observe_manual_keys)):
        raise ValueError("optional native field switches must be boolean")
    if (type(pid) is not int or pid <= 0
            or type(start_utc_ticks) is not int or start_utc_ticks <= 0
            or type(window_handle) is not int or window_handle <= 0):
        raise ValueError("explicit positive PID, epoch and HWND required")
    _path(executable_path)
    if (not isinstance(executable_sha256, str) or len(executable_sha256) != 64
            or any(char not in "0123456789abcdefABCDEF" for char in executable_sha256)):
        raise ValueError("trusted executable SHA-256 must contain 64 hex characters")
    if not isinstance(host, str) or not host.strip() or host != host.strip():
        raise ValueError("exact nonempty machine name required")
    if not all(callable(fn) for fn in (inspect, api_factory, open_session,
                                      keyboard_factory, decode, clock, sleep)):
        raise ValueError("native observation callbacks must be callable")

    entered = _valid_clock(clock())
    options = {
        "expected_executable_path": executable_path,
        "expected_executable_sha256": executable_sha256,
        "expected_start_utc_ticks": start_utc_ticks,
        "expected_window_handle": window_handle,
        "expected_host": host,
        "require_foreground": True,
    }
    first = inspect(pid, **options)
    if not _same_desktop(first, first, host=host, pid=pid, ticks=start_utc_ticks,
                         path=executable_path, sha=executable_sha256, hwnd=window_handle):
        raise SeriesUnavailable("initial full process/build/window identity admission failed")

    pin = ProcessPin(pid, start_utc_ticks, executable_path, executable_sha256)
    api = api_factory()
    keyboard = keyboard_factory() if observe_manual_keys else None
    rows: list[dict] = []
    previous_owner: str | None = None
    previous_zone_key: int | None = None
    previous_sample_time: float | None = None
    opts = {}
    if include_matrix_candidate:
        opts["include_matrix_candidate"] = True
    if include_refresh_guard_candidate:
        opts["include_refresh_guard_candidate"] = True
    if include_actor_translation_candidate:
        opts["include_actor_translation_candidate"] = True
    if include_zone_key_candidate:
        opts["include_zone_key_candidate"] = True

    with open_session(pin) as session:
        if (not isinstance(session.pin, ProcessPin)
                or session.pin.pid != pin.pid or session.pin.start_utc_ticks != pin.start_utc_ticks
                or _path(session.pin.executable_path) != _path(pin.executable_path)
                or session.pin.executable_sha256.casefold() != pin.executable_sha256.casefold()
                or not isinstance(session.module, MainModule)
                or _path(session.module.executable_path) != _path(executable_path)):
            raise SeriesUnavailable("opened native memory handle does not match pinned executable")
        # Anchor sample cadence AFTER the initial process/file admissions,
        # which can consume hundreds of ms. Never bunch the early samples to
        # catch up with the pre-admission clock.
        schedule_started = _valid_clock(clock())
        for i in range(samples):
            now = _valid_clock(clock())
            target = schedule_started + (i * interval_ms / 1000.)
            if target > now:
                sleep(target - now)
            start = _valid_clock(clock())
            if start - entered > max_total_s:
                raise SeriesUnavailable("series exceeded total observation budget")
            _fast_pin(api, host=host, pid=pid, ticks=start_utc_ticks,
                      path=executable_path, hwnd=window_handle)
            before_keys = None
            if keyboard is not None:
                before_keys = _poll_keys(keyboard, clock)
            raw = decode(session, clock=clock, **opts)
            if (not isinstance(raw, PositionFacingCandidate)
                    or raw.process_id != pid
                    or raw.process_start_utc_ticks != start_utc_ticks
                    or not isinstance(raw.build_sha256, str)
                    or raw.build_sha256.casefold() != executable_sha256.casefold()):
                raise SeriesUnavailable("native candidate source PID, epoch or build mismatch")
            after_keys = None
            if keyboard is not None:
                after_keys = _poll_keys(keyboard, clock)
            _fast_pin(api, host=host, pid=pid, ticks=start_utc_ticks,
                      path=executable_path, hwnd=window_handle)
            end = _valid_clock(clock())
            record = _row(raw, i + 1, matrix=include_matrix_candidate,
                          guard=include_refresh_guard_candidate,
                          translation=include_actor_translation_candidate,
                           zone=include_zone_key_candidate)
            timestamp = _valid_clock(record["observedMonotonicSeconds"])
            if (not start <= timestamp <= end
                    or (previous_sample_time is not None and timestamp <= previous_sample_time)
                    or end - entered > max_total_s):
                raise SeriesUnavailable("native source timestamp invalid or series time budget exceeded")
            if previous_owner is not None and record["ownerKeyDecimal"] != previous_owner:
                raise SeriesUnavailable("player owner changed during native series")
            previous_owner = record["ownerKeyDecimal"]
            if include_zone_key_candidate:
                current_zone_key = record["zoneKeyEvidence"]["rawSelfZoneKey"]
                if previous_zone_key is not None and current_zone_key != previous_zone_key:
                    raise SeriesUnavailable("raw self-zone key changed during pinned series; no coherent zone report")
                previous_zone_key = current_zone_key
            previous_sample_time = timestamp
            record["captureBracketSeconds"] = end - start
            if keyboard is not None:
                if not (start <= before_keys["atMonotonicSeconds"]
                        <= timestamp <= after_keys["atMonotonicSeconds"] <= end):
                    raise SeriesUnavailable("Windows key snapshot outside native observation bracket")
                record["manualWindowsKeyStates"] = {
                    "beforeNativeRead": before_keys,
                    "afterNativeRead": after_keys,
                    "unchangedDuringNativeRead": (
                        before_keys["keys"] == after_keys["keys"]
                    ),
                    "gameInputConsumptionVerified": False,
                }
            rows.append(record)

    final = inspect(pid, **options)
    if not _same_desktop(first, final, host=host, pid=pid, ticks=start_utc_ticks,
                         path=executable_path, sha=executable_sha256, hwnd=window_handle):
        raise SeriesUnavailable("final full process/build/window identity admission failed")
    elapsed = _valid_clock(clock()) - entered
    if not 0 <= elapsed <= max_total_s:
        raise SeriesUnavailable("final full identity check exceeded series budget")
    deltas = [
        b["observedMonotonicSeconds"] - a["observedMonotonicSeconds"]
        for a, b in zip(rows, rows[1:])
    ]
    starts, ends = rows[0], rows[-1]
    diff = [y-x for x,y in zip(starts["xyzCandidate"], ends["xyzCandidate"])]
    keyboard_summary = summarize_key_snapshots(rows) if observe_manual_keys else None
    return {
        "schema": "taxi.native-candidate-series/1",
        "status": "candidate-only",
        "source": {
            "host": first.host, "pid": pid, "startUtcTicks": start_utc_ticks,
            "executablePath": first.executable_path,
            "onDiskExecutableSha256": first.executable_sha256,
            "windowHandle": window_handle, "ownerKeyDecimalCandidate": previous_owner,
        },
        "requestedSamples": samples, "completedSamples": len(rows),
        "requestedStartSpacingMs": interval_ms,
        "maxTotalSeconds": float(max_total_s),
        "elapsedSecondsIncludingAdmissions": elapsed,
        "observedSampleGapSeconds": {
            "minimum": min(deltas), "median": statistics.median(deltas),
            "maximum": max(deltas),
        },
        "observations": rows,
        "manualWindowsKeyObservationRequested": observe_manual_keys,
        "manualWindowsKeyObservation": keyboard_summary,
        "candidateChanges": {
            "anyXYZChanged": any(r["xyzCandidate"] != starts["xyzCandidate"] for r in rows[1:]),
            "anyYawChanged": any(
                r["playerSystemBearingDegreesCandidate"]
                != starts["playerSystemBearingDegreesCandidate"] for r in rows[1:]
            ),
            "firstToLastDeltaXYZ": diff,
            "firstToLastHorizontalXZDistanceSourceUnits": math.hypot(diff[0], diff[2]),
            "firstToLastYawDeltaDegrees": (
                (ends["playerSystemBearingDegreesCandidate"] -
                 starts["playerSystemBearingDegreesCandidate"] + 180) % 360 - 180
            ),
            "freshPositionVerified": False, "bodyHeadingVerified": False,
        },
        "optionalEvidenceRequested": {
            "actorMatrix": include_matrix_candidate,
            "refreshGuard": include_refresh_guard_candidate,
            "actorTranslation": include_actor_translation_candidate,
            "zoneKey": include_zone_key_candidate,
            "manualWindowsKeys": observe_manual_keys,
        },
        "qualifications": {
            "fullExecutableIdentityChecks": 2,
            "singleReadOnlyProcessHandle": True,
            "perSampleProcessWindowChecks": True,
            "addonApiProducerQuietVerified": False,
            "externalActionReceiptsProvided": False,
            "readOnlyWindowsKeyPollingUsed": observe_manual_keys,
            "windowsKeyPollsAreNotGameInputProof": True,
            "physicalMovementVerified": False,
            "gameInputSent": False,
            "playerBodyHeadingVerified": False,
            "nativeXYZPassiveFreshnessVerified": False,
            "publicZoneIdVerified": False,
            "worldInstanceVerified": False,
            "liveJourneyVerified": False,
        },
        "limitations": [
            "Samples are consecutive owner-resolved native candidates, not independent game positions.",
            "Per-read process epoch and per-sample HWND checks cannot make sequential reads atomic.",
            "The on-disk executable is checked before/after; loaded module bytes are not hashed.",
            "Foreground changes, process replacement, owner replacement or incomplete samples abort.",
            "Configured addon Inspect.Unit.Detail polling may refresh cached XYZ during sampling.",
            "Optional raw self-zone key is not a public zone ID or same-world-instance proof.",
            "Even observed XYZ/yaw changes are not causally tied to an input without separate receipts.",
            "Optional Windows W/A/D polling reads GetAsyncKeyState; no key is inserted.",
            "Windows key-state snapshots may miss taps and cannot prove RIFT consumed input.",
            "No W/A/D or camera command is issued by this observer.",
        ],
    }
