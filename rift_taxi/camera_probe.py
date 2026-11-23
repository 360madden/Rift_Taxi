"""One bounded left-mouse camera orbit diagnostic; NEVER navigation.

RIFT's default orbit-camera gesture is left-mouse drag. It must be separated
from W/A/D and from right-mouse steering. An external process ACKs release of
MOUSE_LEFT before DOWN. Physical action is opt-in, short and source-pinned;
all native yaw/matrix/XYZ readings remain candidates until independently
checked against actual screen images and zone/actor evidence.
"""
from __future__ import annotations

import math
from pathlib import Path
import re
import time
from typing import Callable

from .key_observation import Win32KeySnapshot, validate_key_snapshot
from .native_capture import capture_native_candidate
from .release_supervisor import ExternalReleaseSupervisor, ReleaseLeasePin, SupervisorUnavailable
from .turn_probe import TurnProbeRefused, _identity, _capture, _wrap
from .win32_identity import inspect_desktop
from .win32_mouse import Win32MouseSender

_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")


class CameraProbeRefused(TurnProbeRefused):
    """Camera-only probe failed admission, action or release."""


def _camera_capture(pin: ReleaseLeasePin, owner: int, read: Callable) -> dict:
    try:
        return _capture(pin, owner, read)
    except TurnProbeRefused as error:
        raise CameraProbeRefused(str(error)) from error


class _InertMouse:
    """No OS input, cursor read, or movement in diagnostic dry-run."""
    def left_pressed(self) -> bool:
        return False
    def right_pressed(self) -> bool:
        return False
    def cursor_position(self) -> tuple[int, int]:
        return 0, 0
    def position_cursor(self, x: int, y: int) -> bool:
        return True
    def window_rect(self, hwnd: int) -> tuple[int, int, int, int]:
        return 0, 0, 1920, 1080
    def send(self, key: str, is_down: bool) -> bool:
        return True
    def move_relative(self, dx: int, dy: int = 0) -> bool:
        return True


def run_camera_orbit_probe(
    *, pin: ReleaseLeasePin, expected_owner_key: int,
    horizontal_drag_px: int, cursor_x_fraction: float,
    cursor_y_fraction: float, audit_path: str,
    hold_ms: int = 100, scene_image_sha256: str | None = None,
    dry_run: bool = True,
    inspect: Callable = inspect_desktop,
    capture: Callable = capture_native_candidate,
    key_factory: Callable = Win32KeySnapshot,
    mouse_factory: Callable = Win32MouseSender,
    release_start: Callable = ExternalReleaseSupervisor.start_turn_probe,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict:
    """One left-mouse-only orbit, with separately supervised UP and return.

    The source screenshot and chosen safe-ground cursor fraction must be
    independently reviewed outside this function, before any real input.
    """
    if not isinstance(pin, ReleaseLeasePin):
        raise ValueError("exact ReleaseLeasePin required")
    if type(expected_owner_key) is not int or expected_owner_key <= 0:
        raise ValueError("current native owner key required")
    if type(horizontal_drag_px) is not int or not 30 <= horizontal_drag_px <= 90:
        raise ValueError("horizontal drag must be 30..90 pixels")
    if type(hold_ms) is not int or not 80 <= hold_ms <= 160:
        raise ValueError("camera drag must be 80..160 ms")
    if type(dry_run) is not bool:
        raise ValueError("explicit dry_run boolean required")
    for fraction, low, high in (
        (cursor_x_fraction, .2, .7), (cursor_y_fraction, .25, .65)
    ):
        if (type(fraction) not in (float, int) or not math.isfinite(fraction)
                or not low <= fraction <= high):
            raise ValueError("cursor fraction must target reviewed central ground")
    if not isinstance(audit_path, str) or not audit_path.strip():
        raise ValueError("new external release audit path required")
    audit = Path(audit_path)
    if audit.exists() or not audit.parent.is_dir():
        raise ValueError("external release audit path must be NEW with existing parent")
    if not dry_run and (
        not isinstance(scene_image_sha256, str) or not _SHA.fullmatch(scene_image_sha256)
    ):
        raise ValueError("physical camera orbit requires independently reviewed scene SHA")
    if not all(callable(x) for x in (
        inspect, capture, key_factory, mouse_factory, release_start, clock, sleeper
    )):
        raise ValueError("missing camera diagnostic dependency")

    _identity(pin, inspect)
    keys = key_factory()
    if any(validate_key_snapshot(keys.snapshot()).values()):
        raise CameraProbeRefused("W/A/D already held before camera orbit")
    before = _camera_capture(pin, expected_owner_key, capture)
    _identity(pin, inspect)

    mouse = _InertMouse() if dry_run else mouse_factory()
    if mouse.left_pressed() or mouse.right_pressed():
        raise CameraProbeRefused("mouse button already down before camera-only orbit")
    start_cursor = mouse.cursor_position()
    if (not isinstance(start_cursor, tuple) or len(start_cursor) != 2
            or any(type(n) is not int for n in start_cursor)):
        raise CameraProbeRefused("cursor coordinate unavailable")
    left, top, right, bottom = mouse.window_rect(pin.hwnd)
    if any(type(n) is not int for n in (left, top, right, bottom)):
        raise CameraProbeRefused("window geometry not integer")
    width, height = right - left, bottom - top
    if not (500 <= width <= 8000 and 300 <= height <= 5000):
        raise CameraProbeRefused("game window geometry unreasonable")
    click_x = left + round(width * cursor_x_fraction)
    click_y = top + round(height * cursor_y_fraction)

    down_at = up_at = None
    os_down = os_up = None
    moved = []
    state = None
    moved_cursor = False
    restore_ok = True
    try:
        with release_start(
            pin, ttl_s=.6, dry_run=dry_run, audit_path=str(audit), admit=inspect
        ) as worker:
            if not worker.alive or worker.dry_run != dry_run:
                raise CameraProbeRefused("independent mouse release process unavailable")
            reserved = worker.reserve("MOUSE_LEFT")
            if (not isinstance(reserved, dict) or reserved.get("stopped") is not False
                    or "MOUSE_LEFT" not in reserved.get("possibleHeld", ())):
                raise CameraProbeRefused("mouse release reservation not acknowledged")
            try:
                _identity(pin, inspect)
                if (mouse.left_pressed() or mouse.right_pressed()
                        or any(validate_key_snapshot(keys.snapshot()).values())):
                    raise CameraProbeRefused("input state changed before camera gesture")
                if not mouse.position_cursor(click_x, click_y):
                    raise CameraProbeRefused("cannot place cursor on reviewed ground")
                moved_cursor = True
                try:
                    lease = worker.renew()
                except SupervisorUnavailable as error:
                    raise CameraProbeRefused("mouse release lease expired") from error
                if (not isinstance(lease, dict) or lease.get("stopped") is not False
                        or "MOUSE_LEFT" not in lease.get("possibleHeld", ())):
                    raise CameraProbeRefused("mouse lease not live before DOWN")
                _identity(pin, inspect)
                if mouse.right_pressed():
                    raise CameraProbeRefused("right-mouse steering held at camera DOWN")
                down_at = float(clock())
                os_down = mouse.send("MOUSE_LEFT", True) is True
                if not os_down:
                    raise CameraProbeRefused("left mouse DOWN not accepted")
                steps = [horizontal_drag_px // 3, horizontal_drag_px // 3]
                steps.append(horizontal_drag_px - sum(steps))
                for step in steps:
                    if not mouse.move_relative(step, 0):
                        raise CameraProbeRefused("relative mouse motion not accepted")
                    moved.append(step)
                    if mouse.right_pressed():
                        raise CameraProbeRefused("right mouse co-pressed during camera orbit")
                    sleeper(.02)
                sleeper(max(0., hold_ms / 1000. - .06))
            finally:
                # Always send UP, even if DOWN or motion fails, and retain the
                # separate process release reservation until UP was accepted.
                up_at = float(clock())
                try:
                    os_up = mouse.send("MOUSE_LEFT", False) is True
                except Exception:
                    os_up = False
                if os_up:
                    try:
                        worker.clear("MOUSE_LEFT")
                    except SupervisorUnavailable:
                        pass
                try:
                    state = worker.stop()
                except SupervisorUnavailable:
                    state = None
    finally:
        if moved_cursor:
            try:
                restore_ok = mouse.position_cursor(*start_cursor) is True
            except Exception:
                restore_ok = False

    if not os_up:
        raise CameraProbeRefused("left mouse UP not accepted; release uncertain")
    if (not isinstance(state, dict) or state.get("stopped") is not True
            or state.get("possibleHeld") != []):
        raise CameraProbeRefused("independent mouse release ledger not clear")
    if not restore_ok:
        raise CameraProbeRefused("original cursor position could not be restored")
    _identity(pin, inspect)
    if mouse.left_pressed() or mouse.right_pressed():
        raise CameraProbeRefused("mouse button remains held after camera orbit")
    if any(validate_key_snapshot(keys.snapshot()).values()):
        raise CameraProbeRefused("W/A/D changed during camera-only diagnostic")
    after = _camera_capture(pin, expected_owner_key, capture)
    _identity(pin, inspect)
    sleeper(.20)
    _identity(pin, inspect)
    if (mouse.left_pressed() or mouse.right_pressed()
            or any(validate_key_snapshot(keys.snapshot()).values())):
        raise CameraProbeRefused("input re-engaged after camera release")
    later = _camera_capture(pin, expected_owner_key, capture)
    _identity(pin, inspect)

    return {
        "schema": "taxi.m1-camera-only-orbit-probe/1",
        "status": "camera-only-candidate-not-qualified",
        "dryRun": dry_run,
        "source": {
            "host": pin.host, "pid": pin.pid,
            "startUtcTicks": pin.start_utc_ticks,
            "onDiskExecutableSha256": pin.sha256,
            "windowHandle": pin.hwnd,
            "ownerKeyDecimalCandidate": str(expected_owner_key),
            "reviewedSceneImageSha256": scene_image_sha256,
        },
        "action": {
            "requestedButton": "MOUSE_LEFT",
            "requestedDragPixels": horizontal_drag_px,
            "requestedHoldMilliseconds": hold_ms,
            "cursorFraction": [cursor_x_fraction, cursor_y_fraction],
            "cursorRestored": restore_ok,
            "downAtMonotonicSeconds": down_at,
            "upAtMonotonicSeconds": up_at,
            "mouseDownAcceptedByOS": bool(os_down and not dry_run),
            "mouseUpAcceptedByOS": bool(os_up and not dry_run),
            "mouseMovementPacketsAccepted": len(moved),
            "releaseSupervisorStoppedAndClear": True,
            "noWADInputSent": True,
            "gameCameraOrbitIndependentlyVerified": False,
        },
        "candidateBefore": before,
        "candidateAfter": after,
        "candidateSettledAfterRelease": later,
        "candidateChanges": {
            "deltaXYZ": [a - b for a, b in zip(after["xyzCandidate"], before["xyzCandidate"])],
            "playerSystemYawDeltaDegreesCandidate": _wrap(
                after["playerSystemBearingDegreesCandidate"]
                - before["playerSystemBearingDegreesCandidate"]
            ),
            "actorMatrixAngleDeltaDegreesCandidate": _wrap(
                after["actorMatrixPlanarAngleDegreesCandidate"]
                - before["actorMatrixPlanarAngleDegreesCandidate"]
            ),
            "actorHeadingQualified": False,
            "cameraOnlyVerified": False,
            "passiveXYZFreshnessQualified": False,
        },
        "limitations": [
            "A labeled mouse orbit is not proof the game interpreted the action as camera-only.",
            "Screen frames must be independently reviewed and matched to native samples.",
            "OS mouse release and child ledger clear are not game-consumed-release proof.",
            "This is not a qualified body yaw, LivePose or autonomous navigation receipt.",
            "Installed addon API polling can refresh the native XYZ cache.",
        ],
    }
