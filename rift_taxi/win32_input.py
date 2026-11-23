"""Taxi-owned Win32 scan-code key backend (M1; NOT yet live-qualified).

Implements control.KeyBackend using standard SendInput scan codes for W/A/D.
Cannot arm from a raw PositionFacingCandidate. Admission requires a separate
same-session qualified LivePose, exact process/build/HWND/foreground inspection,
and an explicit arm() call. No CLI command arms this backend.

DOWN checks the exact OS process/window immediately before insertion. UP
remains permitted after focus loss, to attempt release of uncertain OS state.
SendInput acceptance is not game-consumed input or released-game-state proof.
No autonomous controller, timed press, key send or RIFT process attach occurs
on module import or during tests with injected fakes.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import ntpath
import socket
import sys
import threading
import time
from typing import Callable, Protocol

from .control import ControlRefused, LivePose, SessionBinding
from .win32_identity import (
    DesktopCandidate, ProcessInfo, Win32DesktopProbe, inspect_desktop,
)

_SCANS = {"W": 0x11, "A": 0x1E, "D": 0x20}
_EVENT_SCAN = 0x0008
_EVENT_KEYUP = 0x0002
_INPUT_KEYBOARD = 1


class _Mouse(ctypes.Structure):
    _fields_ = (("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p))


class _Keyboard(ctypes.Structure):
    _fields_ = (("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p))


class _Hardware(ctypes.Structure):
    _fields_ = (("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD))


class _Payload(ctypes.Union):
    _fields_ = (("mi", _Mouse), ("ki", _Keyboard), ("hi", _Hardware))


class _Input(ctypes.Structure):
    _fields_ = (("type", wintypes.DWORD), ("data", _Payload))


def encode_key_event(key: str, is_down: bool) -> _Input:
    """Produce an ABI-compatible scan-code INPUT with no OS insertion."""
    if type(key) is not str or key not in _SCANS or type(is_down) is not bool:
        raise ValueError("only W/A/D with explicit boolean edge are supported")
    result = _Input()
    result.type = _INPUT_KEYBOARD
    result.data.ki.wVk = 0
    result.data.ki.wScan = _SCANS[key]
    result.data.ki.dwFlags = _EVENT_SCAN | (0 if is_down else _EVENT_KEYUP)
    return result


class ScanSender(Protocol):
    def send(self, key: str, is_down: bool) -> bool: ...


class FastInputProbe(Protocol):
    def host(self) -> str: ...
    def process(self, pid: int) -> ProcessInfo: ...
    def window_ready(self, hwnd: int, pid: int) -> bool: ...
    def foreground_root(self) -> int: ...


class Win32ScanSender:
    """A single native SendInput event; no use occurs until send() is called."""

    def __init__(self) -> None:
        if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
            raise RuntimeError("64-bit Windows Python required for RIFT scan codes")
        self._u32 = ctypes.WinDLL("user32", use_last_error=True)
        self._u32.SendInput.argtypes = (
            wintypes.UINT, ctypes.POINTER(_Input), ctypes.c_int)
        self._u32.SendInput.restype = wintypes.UINT
        if ctypes.sizeof(_Input) != 40 or ctypes.sizeof(_Keyboard) != 24:
            raise RuntimeError("Win32 INPUT/KEYBDINPUT layout mismatch")

    def send(self, key: str, is_down: bool) -> bool:
        packet = encode_key_event(key, is_down)
        return self._u32.SendInput(1, ctypes.byref(packet), ctypes.sizeof(_Input)) == 1


class Win32FastInputProbe:
    """Constant-shape OS metadata check; no executable rehash on every key edge."""

    def __init__(self) -> None:
        self._desktop = Win32DesktopProbe()

    def host(self) -> str:
        return socket.gethostname()

    def process(self, pid: int) -> ProcessInfo:
        return self._desktop.process(pid)

    def window_ready(self, hwnd: int, pid: int) -> bool:
        d = self._desktop
        return (d.window_belongs_to_pid(hwnd, pid)
                and bool(d.u32.IsWindowVisible(hwnd))
                and not bool(d.u32.IsIconic(hwnd))
                and not bool(d.u32.GetWindow(hwnd, 4)))

    def foreground_root(self) -> int:
        return self._desktop.foreground_root()


class WindowsScanKeyBackend:
    """Explicitly armed, same-session scan-code backend for HeldInputController.

    No actor/zone semantics can be inferred here; arm() requires a previously
    independently qualified LivePose (the candidate reader does not provide it).
    Fast per-edge OS checks cannot rule out focus loss *between* check and send.
    UP is best-effort even if focus/owner disappears. Does not provide an
    independently supervised crash-proof release process.
    """

    def __init__(
        self, session: SessionBinding, executable_path: str, *,
        probe: FastInputProbe | None = None,
        sender: ScanSender | None = None,
        admit: Callable = inspect_desktop,
        clock: Callable[[], float] = time.monotonic,
        max_arm_pose_age_s: float = 0.35,
    ) -> None:
        if not isinstance(session, SessionBinding):
            raise ValueError("exact SessionBinding required")
        if not isinstance(executable_path, str) or not ntpath.isabs(executable_path):
            raise ValueError("absolute expected executable path required")
        if not callable(admit) or not callable(clock):
            raise ValueError("admission and clock callbacks required")
        if isinstance(max_arm_pose_age_s, bool) or not isinstance(max_arm_pose_age_s, (int, float)):
            raise ValueError("arm pose age must be finite")
        if not 0.02 <= max_arm_pose_age_s <= 0.5:
            raise ValueError("arm pose age must be within .02..0.5 seconds")
        self.session = session
        self.executable_path = executable_path
        self._probe = probe if probe is not None else Win32FastInputProbe()
        self._sender = sender if sender is not None else Win32ScanSender()
        self._admit = admit
        self._clock = clock
        self._max_age = float(max_arm_pose_age_s)
        self._armed = False
        self._uncertain: set[str] = set()
        self._lock = threading.RLock()

    @property
    def has_native_sender(self) -> bool:
        """Only native sender uses actual Win32 SendInput (not a faked sender)."""
        return isinstance(self._sender, Win32ScanSender)

    @property
    def armed(self) -> bool:
        with self._lock:
            return self._armed

    @property
    def possibly_held(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(k for k in ("W", "A", "D") if k in self._uncertain)

    def _quick_exact_target(self) -> bool:
        try:
            p = self._probe.process(self.session.process_id)
            if (not isinstance(p, ProcessInfo) or p.pid != self.session.process_id
                    or p.start_utc_ticks != self.session.start_ticks
                    or ntpath.normcase(p.executable_path)
                    != ntpath.normcase(self.executable_path)
                    or self._probe.host().casefold() != self.session.host.casefold()
                    or not self._probe.window_ready(
                        self.session.window_handle, self.session.process_id)
                    or self._probe.foreground_root() != self.session.window_handle):
                return False
            return True
        except (OSError, RuntimeError, ValueError):
            return False

    def arm(self, pose: LivePose) -> None:
        """Only a true independently qualified current pose may enable DOWN."""
        if not isinstance(pose, LivePose) or pose.session != self.session \
                or not pose.actor_yaw_verified or not pose.foreground_verified:
            raise ControlRefused("qualified same-session actor pose required before arming")
        with self._lock:
            if self._uncertain:
                raise ControlRefused("uncertain held keys block rearming")
            if self._armed:
                raise ControlRefused("already armed; explicit disarm first")
            if not self._quick_exact_target():
                raise ControlRefused("fast OS process/foreground identity unavailable")
            desktop: DesktopCandidate = self._admit(
                self.session.process_id, expected_executable_path=self.executable_path,
                expected_executable_sha256=self.session.executable_sha256,
                expected_start_utc_ticks=self.session.start_ticks,
                expected_window_handle=self.session.window_handle,
                expected_host=self.session.host, require_foreground=True,
            )
            if not isinstance(desktop, DesktopCandidate) or not desktop.foreground \
                    or desktop.pid != self.session.process_id \
                    or desktop.start_utc_ticks != self.session.start_ticks \
                    or desktop.window_handle != self.session.window_handle \
                    or desktop.executable_sha256.casefold() != self.session.executable_sha256.casefold():
                raise ControlRefused("native input admission identity changed")
            age = self._clock() - pose.observed_monotonic_s
            if not 0 <= age <= self._max_age or not self._quick_exact_target():
                raise ControlRefused("pose stale or focus changed while admitting Windows input")
            self._armed = True

    def write_key(self, key: str, is_down: bool) -> bool:
        """Return OS insertion acceptance only, never game-consumption proof."""
        if type(key) is not str or key not in _SCANS or type(is_down) is not bool:
            return False
        with self._lock:
            if is_down:
                if key in self._uncertain:
                    # An injected key held by this backend must not be pressed
                    # again by a direct caller while the first edge is unresolved.
                    self._armed = False
                    return False
                if not self._armed or not self._quick_exact_target():
                    self._armed = False
                    return False
                self._uncertain.add(key)  # mark uncertainty BEFORE OS call
                try:
                    return self._sender.send(key, True) is True
                except Exception:
                    return False
            if key not in self._uncertain:
                return True
            # Releasing a potentially held key should NOT require foreground,
            # because focus loss is precisely when emergency key-up is needed.
            try:
                inserted = self._sender.send(key, False) is True
            except Exception:
                inserted = False
            if inserted:
                self._uncertain.discard(key)
            return inserted

    def release_all(self) -> dict[str, bool]:
        """Callable without the steering gate; in-process best-effort only."""
        return {key: self.write_key(key, False) for key in ("A", "D", "W")
                if key in self.possibly_held}

    def disarm(self) -> dict[str, bool]:
        with self._lock:
            self._armed = False
        return self.release_all()
