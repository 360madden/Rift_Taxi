"""Bounded A/D turn and W-only *calibration probes*, separate from Taxi navigation.

Purpose: learn whether current native yaw and actor matrix candidates respond
to one short physical turn or forward pulse. It NEVER runs route navigation.

The production WindowsScanKeyBackend still requires independently qualified
LivePose. This diagnostic does not fake one. It requires exact OS PID/epoch/
exe/hash/HWND, source-owned self actor, a current scene-image SHA and a live
external release-only child before attempting any physical key DOWN.

The probe rechecks a renewed lease around the sender call; these observations
are not atomic with SendInput or child expiry. A stalled or crashed sender can
still require independent release recovery; no universal fault proof is granted.
"""
from __future__ import annotations

import math
import ntpath
from pathlib import Path
import re
import time
from typing import Callable, Protocol

from .key_observation import Win32KeySnapshot, validate_key_snapshot
from .native_capture import capture_native_candidate
from .release_supervisor import (
    ExternalReleaseSupervisor, ReleaseLeasePin, SupervisorUnavailable,
)
from .win32_identity import DesktopCandidate, inspect_desktop
from .win32_input import Win32ScanSender

_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
_PROBE_LEASE_SECONDS = .6


class TurnProbeRefused(RuntimeError):
    """A bounded physical turn could not retain admission or release proof."""


class _DryRunSender:
    """Test-mode sink, never linked to user32 SendInput."""

    def send(self, key: str, is_down: bool) -> bool:
        return True


def _identity(pin: ReleaseLeasePin, inspect: Callable) -> DesktopCandidate:
    candidate = inspect(
        pin.pid, expected_executable_path=pin.executable_path,
        expected_executable_sha256=pin.sha256,
        expected_start_utc_ticks=pin.start_utc_ticks,
        expected_window_handle=pin.hwnd, expected_host=pin.host,
        require_foreground=True,
    )
    if (not isinstance(candidate, DesktopCandidate)
            or not candidate.foreground or candidate.pid != pin.pid
            or candidate.start_utc_ticks != pin.start_utc_ticks
            or candidate.window_handle != pin.hwnd
            or candidate.host.casefold() != pin.host.casefold()
            or candidate.executable_sha256.casefold() != pin.sha256.casefold()
            or ntpath.normcase(candidate.executable_path)
            != ntpath.normcase(pin.executable_path)):
        raise TurnProbeRefused("exact foreground RIFT process admission refused")
    return candidate


def _capture(pin: ReleaseLeasePin, expected_owner_key: int, read: Callable) -> dict:
    data = read(
        pid=pin.pid, start_utc_ticks=pin.start_utc_ticks,
        executable_path=pin.executable_path,
        executable_sha256=pin.sha256, window_handle=pin.hwnd, host=pin.host,
        include_matrix_candidate=True,
    )
    if not isinstance(data, dict) or data.get("schema") != "taxi.native-candidate/1" \
            or data.get("status") != "candidate-only":
        raise TurnProbeRefused("native turn probe source is not an unqualified candidate")
    process, sample, evidence, matrices = (
        data.get("process"), data.get("candidate"),
        data.get("evidence"), data.get("matrixEvidence"),
    )
    if not all(isinstance(part, dict) for part in (process, sample, evidence, matrices)):
        raise TurnProbeRefused("native turn probe report missing source evidence")
    if (type(process.get("pid")) is not int or process["pid"] != pin.pid
            or type(process.get("startUtcTicks")) is not int
            or process["startUtcTicks"] != pin.start_utc_ticks
            or type(process.get("windowHandle")) is not int
            or process["windowHandle"] != pin.hwnd
            or process.get("host", "").casefold() != pin.host.casefold()
            or process.get("onDiskExecutableSha256", "").casefold() != pin.sha256.casefold()
            or not isinstance(process.get("executablePath"), str)
            or ntpath.normcase(process["executablePath"]) != ntpath.normcase(pin.executable_path)
            or not isinstance(sample.get("ownerKeyDecimal"), str)
            or sample["ownerKeyDecimal"] != str(expected_owner_key)
            or evidence.get("actorHeadingQualified") is not False
            or evidence.get("passivePositionFreshnessQualified") is not False
            or evidence.get("liveInGameResponseVerified") is not False
            or evidence.get("inputSent") is not False
            or matrices.get("actorHeadingQualified") is not False):
        raise TurnProbeRefused("native turn probe actor, session or qualification changed")
    xyz = sample.get("xyz")
    yaw = sample.get("playerSystemBearingDegrees")
    matrix_angle = matrices.get("actorPlanarAngleDegreesCandidate")
    if (not isinstance(xyz, list) or len(xyz) != 3
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) for v in xyz)
            or isinstance(yaw, bool) or not isinstance(yaw, (int, float))
            or not math.isfinite(yaw)
            or matrix_angle is None or isinstance(matrix_angle, bool)
            or not isinstance(matrix_angle, (int, float))
            or not math.isfinite(matrix_angle)):
        raise TurnProbeRefused("native turn probe XYZ or angle candidates unavailable")
    return {
        "ownerKeyDecimal": str(expected_owner_key),
        "xyzCandidate": list(xyz),
        "playerSystemBearingDegreesCandidate": yaw,
        "actorMatrixPlanarAngleDegreesCandidate": matrix_angle,
        "observedMonotonicSeconds": sample.get("observationMonotonicSeconds"),
        "actorHeadingVerified": False,
        "passivePositionFreshnessVerified": False,
    }


def _wrap(delta: float) -> float:
    return (delta + 180) % 360 - 180


def _probe_clock(clock: Callable[[], float], previous: float | None = None) -> float:
    """Read a finite same-host monotonic time without letting faults skip UP.

    The release child uses this clock domain too. Reject booleans, invalid
    numeric values and rollback; cleanup catches this refusal before sending UP.
    """
    try:
        value = clock()
        if (type(value) not in (int, float) or not 0 <= value <= 1e15
                or not math.isfinite(value)
                or (previous is not None and value < previous)):
            raise ValueError("invalid or backward monotonic sample")
        return float(value)
    except Exception as error:
        raise TurnProbeRefused("diagnostic monotonic clock invalid or moved backward") from error


def _probe_deadline(lease: object, key: str, now: float, hold_s: float) -> float:
    """Admit one live reservation with enough remaining time for this hold.

    ACK arrival can be delayed past child expiry. The deadline must be in the
    parent's monotonic domain, no further ahead than this diagnostic's fixed
    TTL, and strictly beyond the requested hold. This is a snapshot, not an
    atomic handoff between the separate release process and the native sender.
    """
    if (not isinstance(lease, dict) or lease.get("stopped") is not False
            or lease.get("possibleHeld") != [key]):
        raise TurnProbeRefused("diagnostic release lease was not live for requested key")
    deadline = lease.get("deadlineMonotonicSeconds")
    if (type(deadline) not in (int, float) or not 0 <= deadline <= 1e15
            or not math.isfinite(deadline)
            or deadline > now + _PROBE_LEASE_SECONDS
            or now + hold_s >= deadline):
        raise TurnProbeRefused("diagnostic release deadline invalid or insufficient for hold")
    return float(deadline)


def _run_calibration_probe(
    *, probe_kind: str, pin: ReleaseLeasePin, expected_owner_key: int,
    key: str, hold_ms: int = 100, audit_path: str,
    scene_image_sha256: str | None = None,
    dry_run: bool = True,
    inspect: Callable = inspect_desktop,
    capture: Callable = capture_native_candidate,
    key_factory: Callable = Win32KeySnapshot,
    sender_factory: Callable = Win32ScanSender,
    release_start: Callable = ExternalReleaseSupervisor.start_turn_probe,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict:
    """One strictly scoped W/A/D diagnostic pulse, always attempts UP.

    Dry-run is the default. In physical mode an actual JPEG/PNG source SHA is
    required for the already inspected open-ground scene. The image must be
    independently reviewed; this function checks only the receipt format.
    """
    if not isinstance(pin, ReleaseLeasePin):
        raise ValueError("ReleaseLeasePin required")
    if type(expected_owner_key) is not int or expected_owner_key <= 0:
        raise ValueError("explicit positive self owner key required")
    if probe_kind not in ("turn", "forward"):
        raise ValueError("unknown calibration probe kind")
    permitted = ("A", "D") if probe_kind == "turn" else ("W",)
    if type(key) is not str or key not in permitted:
        raise ValueError("only A or D is permitted in the calibration probe" if probe_kind == "turn"
                         else "forward calibration permits W only")
    if type(hold_ms) is not int or not 60 <= hold_ms <= 160:
        raise ValueError("single diagnostic hold must be 60..160 ms")
    if type(dry_run) is not bool:
        raise ValueError("dry_run must be bool")
    if not isinstance(audit_path, str) or not audit_path.strip():
        raise ValueError("new audit path required")
    audit = Path(audit_path)
    if audit.exists() or not audit.parent.is_dir():
        raise ValueError("audit path must be new and its parent must exist")
    if not dry_run and (
            not isinstance(scene_image_sha256, str) or not _SHA.fullmatch(scene_image_sha256)):
        raise ValueError("physical probe requires an independently reviewed current-scene SHA-256")
    if not all(callable(x) for x in (
            inspect, capture, key_factory, sender_factory,
            release_start, clock, sleeper)):
        raise ValueError("turn probe dependencies must be callable")

    last_clock = _probe_clock(clock)
    _identity(pin, inspect)
    key_reader = key_factory()
    if any(validate_key_snapshot(key_reader.snapshot()).values()):
        raise TurnProbeRefused("W/A/D key already down before turn probe")
    before = _capture(pin, expected_owner_key, capture)
    _identity(pin, inspect)
    sender = _DryRunSender() if dry_run else sender_factory()
    physical_down = None
    physical_up = None
    down_at = None
    up_at = None
    sampled_down = None
    helper_armed = False
    release_state = None
    cleanup_clock_error = None
    deadline = None
    hold_s = hold_ms / 1000.
    with release_start(
        pin, ttl_s=_PROBE_LEASE_SECONDS, dry_run=dry_run, audit_path=str(audit),
        admit=inspect,
    ) as worker:
        if not worker.alive or worker.dry_run != dry_run:
            raise TurnProbeRefused("external release helper unavailable")
        reserved = worker.reserve(key)
        if (not isinstance(reserved, dict) or reserved.get("stopped") is not False
                or reserved.get("possibleHeld") != [key]):
            raise TurnProbeRefused("external key release reservation not acknowledged")
        helper_armed = True
        try:
            # Recheck after the release child has reserved the key. A lost
            # foreground or stale epoch must refuse the actual key DOWN.
            _identity(pin, inspect)
            if any(validate_key_snapshot(key_reader.snapshot()).values()):
                raise TurnProbeRefused("W/A/D changed before diagnostic DOWN")
            # Full identity admission may outlast the original reservation.
            # A/D needs the same fresh renewal as W; an expired child must not
            # be followed by a new DOWN based on its earlier reserve ACK.
            last_clock = _probe_clock(clock, last_clock)
            try:
                lease = worker.renew()
            except SupervisorUnavailable as error:
                raise TurnProbeRefused("diagnostic release lease expired before DOWN") from error
            down_at = last_clock = _probe_clock(clock, last_clock)
            deadline = _probe_deadline(lease, key, down_at, hold_s)
            if not worker.alive:
                raise TurnProbeRefused("external release helper unavailable before DOWN")
            physical_down = sender.send(key, True) is True
            if not physical_down:
                raise TurnProbeRefused("calibration key DOWN not accepted")
            # A native sender may return late, after the child has already
            # released. Compensate immediately via finally rather than adding
            # another requested hold. Check/send still has a non-atomic race.
            last_clock = _probe_clock(clock, last_clock)
            _probe_deadline(lease, key, last_clock, hold_s)
            if not worker.alive:
                raise TurnProbeRefused("external release helper unavailable after DOWN")
            sleeper(hold_s)
            sampled_down = validate_key_snapshot(key_reader.snapshot())
        finally:
            if helper_armed:
                # Timestamp failure must never prevent explicit UP or STOP.
                # Preserve a refusal for later, but release first; an original
                # body exception continues propagating after this cleanup.
                try:
                    up_at = last_clock = _probe_clock(clock, last_clock)
                except TurnProbeRefused as error:
                    cleanup_clock_error = error
                # The external child also attempts UP on EOF/TTL.
                try:
                    physical_up = sender.send(key, False) is True
                except Exception:
                    physical_up = False
                if physical_up:
                    try:
                        worker.clear(key)
                    except SupervisorUnavailable:
                        pass  # child STOP/expiry is a fallback
                try:
                    release_state = worker.stop()
                except SupervisorUnavailable:
                    release_state = None
    if not physical_up:
        raise TurnProbeRefused("turn key UP not accepted; release state uncertain")
    if not isinstance(release_state, dict) or release_state.get("stopped") is not True \
            or release_state.get("possibleHeld") != []:
        raise TurnProbeRefused("external turn release has not confirmed a clear ledger")
    if cleanup_clock_error is not None:
        raise cleanup_clock_error
    if up_at is None or deadline is None or up_at >= deadline:
        raise TurnProbeRefused("diagnostic hold outlasted release deadline")
    _identity(pin, inspect)
    post_key_states = validate_key_snapshot(key_reader.snapshot())
    if any(post_key_states.values()):
        raise TurnProbeRefused("W/A/D high bit remains down after calibration probe")
    after = _capture(pin, expected_owner_key, capture)
    _identity(pin, inspect)
    # Forward calibration includes an additional read after an explicit pause.
    # A delayed candidate is not proof that RIFT consumed release or updated
    # native XYZ passively; no pose qualification is granted here.
    settled = None
    if probe_kind == "forward":
        sleeper(.20)
        _identity(pin, inspect)
        if any(validate_key_snapshot(key_reader.snapshot()).values()):
            raise TurnProbeRefused("W/A/D re-engaged after forward key release")
        settled = _capture(pin, expected_owner_key, capture)
        _identity(pin, inspect)
    xdelta = [
        to - fr for fr, to in zip(before["xyzCandidate"], after["xyzCandidate"])
    ]
    return {
        "schema": ("taxi.m1-bounded-turn-probe/1" if probe_kind == "turn"
                   else "taxi.m1-bounded-forward-probe/1"),
        "probeKind": probe_kind,
        "status": "calibration-candidate-only",
        "dryRun": dry_run,
        "source": {
            "host": pin.host, "pid": pin.pid,
            "startUtcTicks": pin.start_utc_ticks,
            "executablePath": pin.executable_path,
            "onDiskExecutableSha256": pin.sha256,
            "windowHandle": pin.hwnd,
            "ownerKeyDecimalCandidate": str(expected_owner_key),
            "reviewedSceneImageSha256": scene_image_sha256,
        },
        "action": {
            "requestedKey": key, "requestedHoldMilliseconds": hold_ms,
            "keyDownAtMonotonicSeconds": down_at,
            "keyUpAtMonotonicSeconds": up_at,
            "downAcceptedBySender": physical_down,
            "upAcceptedBySender": physical_up,
            "osKeyDownAccepted": bool(not dry_run and physical_down),
            "osKeyUpAccepted": bool(not dry_run and physical_up),
            "externalLeaseClearObserved": True,
            "sampledDuringHeldKey": sampled_down,
            "sampledAfterKeyUp": post_key_states,
            "inputInjectedByTaxi": not dry_run,
            "gameInputConsumptionVerified": False,
            "physicalKeyReleaseConsumedByGameVerified": False,
        },
        "candidateBefore": before,
        "candidateAfter": after,
        "candidateSettledAfterRelease": settled,
        "candidateChanges": {
            "planarDistanceXZCandidate": math.hypot(xdelta[0], xdelta[2]),
            "settledDeltaXYZCandidate": (
                [to - fr for fr, to in zip(before["xyzCandidate"], settled["xyzCandidate"])]
                if settled is not None else None
            ),
            "deltaXYZ": xdelta,
            "playerSystemYawDeltaDegrees": _wrap(
                after["playerSystemBearingDegreesCandidate"]
                - before["playerSystemBearingDegreesCandidate"]
            ),
            "actorMatrixAngleDeltaDegrees": _wrap(
                after["actorMatrixPlanarAngleDegreesCandidate"]
                - before["actorMatrixPlanarAngleDegreesCandidate"]
            ),
            "nativeXYZChanged": before["xyzCandidate"] != after["xyzCandidate"],
            "nativeYawChanged": before["playerSystemBearingDegreesCandidate"]
                                   != after["playerSystemBearingDegreesCandidate"],
            "bodyHeadingQualified": False,
            "passiveXYZFreshnessQualified": False,
            "gameMotionIndependentlyVerified": False,
        },
        "limitations": [
            "This diagnostic is not a qualified navigation LivePose or route run.",
            "SendInput OS acceptance and key-state polling are not game-consumption proof.",
            "Separate-process release ledger clear does not prove RIFT consumed key-up.",
            "Lease checks and input insertion are not atomic; universal late-DOWN/crash release is unverified.",
            "The scene screenshot SHA is supplied by the runner, not inspected by this Python function.",
            "Actual on-screen player orientation must be independently compared.",
            "Native XYZ can be refreshed by installed addon Inspect.Unit.Detail polling.",
        ],
    }


def run_turn_probe(
    *, pin: ReleaseLeasePin, expected_owner_key: int,
    key: str, hold_ms: int = 100, audit_path: str,
    scene_image_sha256: str | None = None,
    dry_run: bool = True,
    inspect: Callable = inspect_desktop,
    capture: Callable = capture_native_candidate,
    key_factory: Callable = Win32KeySnapshot,
    sender_factory: Callable = Win32ScanSender,
    release_start: Callable = ExternalReleaseSupervisor.start_turn_probe,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict:
    """Strictly A/D only; no W or navigation can be requested via this entry."""
    return _run_calibration_probe(
        probe_kind="turn", pin=pin, expected_owner_key=expected_owner_key,
        key=key, hold_ms=hold_ms, audit_path=audit_path,
        scene_image_sha256=scene_image_sha256, dry_run=dry_run,
        inspect=inspect, capture=capture, key_factory=key_factory,
        sender_factory=sender_factory, release_start=release_start,
        clock=clock, sleeper=sleeper,
    )


def run_forward_probe(
    *, pin: ReleaseLeasePin, expected_owner_key: int,
    hold_ms: int = 100, audit_path: str,
    scene_image_sha256: str | None = None,
    dry_run: bool = True,
    inspect: Callable = inspect_desktop,
    capture: Callable = capture_native_candidate,
    key_factory: Callable = Win32KeySnapshot,
    sender_factory: Callable = Win32ScanSender,
    release_start: Callable = ExternalReleaseSupervisor.start_turn_probe,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict:
    """One W-only pulse, with external release and 200ms delayed readback.

    This is a candidate acquisition experiment, never a qualified LivePose
    and never an autonomously repeated forward action.
    """
    return _run_calibration_probe(
        probe_kind="forward", pin=pin, expected_owner_key=expected_owner_key,
        key="W", hold_ms=hold_ms, audit_path=audit_path,
        scene_image_sha256=scene_image_sha256, dry_run=dry_run,
        inspect=inspect, capture=capture, key_factory=key_factory,
        sender_factory=sender_factory, release_start=release_start,
        clock=clock, sleeper=sleeper,
    )
