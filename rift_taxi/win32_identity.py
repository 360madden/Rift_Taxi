"""Taxi-owned read-only Windows process/window identity probe.

OS identity is not player/zone identity or native XYZ/yaw evidence. This module
does not open RIFT, read game memory, send input, or call sibling repositories.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import math
import ntpath
import re
import sys
import time
from typing import Callable, Protocol

_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
_DOTNET_EPOCH_OFFSET = 504_911_232_000_000_000  # FILETIME -> .NET DateTime UTC ticks
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class IdentityUnavailable(RuntimeError):
    """Exact Windows identity could not be confirmed."""


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    start_utc_ticks: int
    executable_path: str


@dataclass(frozen=True)
class DesktopCandidate:
    """Verified OS candidate; actor, zone, yaw and movement remain unverified."""

    host: str
    pid: int
    start_utc_ticks: int
    executable_path: str
    executable_sha256: str
    window_handle: int
    foreground: bool
    observed_monotonic_s: float


class DesktopProbeApi(Protocol):
    def host(self) -> str: ...
    def process(self, pid: int) -> ProcessInfo: ...
    def windows_for_pid(self, pid: int) -> tuple[int, ...]: ...
    def window_belongs_to_pid(self, hwnd: int, pid: int) -> bool: ...
    def foreground_root(self) -> int: ...


def sha256_file(path: str) -> str:
    """Hash executable bytes on disk (not loaded process memory)."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_key(path: str) -> str:
    if not isinstance(path, str) or not ntpath.isabs(path):
        raise ValueError("executable requires an absolute Windows path")
    return ntpath.normcase(ntpath.normpath(path))


def inspect_desktop(
    pid: int, *, expected_executable_path: str, expected_executable_sha256: str,
    expected_start_utc_ticks: int | None = None,
    expected_window_handle: int | None = None,
    expected_host: str | None = None,
    require_foreground: bool = True,
    api: DesktopProbeApi | None = None,
    hash_file: Callable[[str], str] = sha256_file,
    clock: Callable[[], float] = time.monotonic,
) -> DesktopCandidate:
    """Read one explicit PID, never silently select a replacement process/window.

    Initial observations without epoch/window pins are only OS candidates.
    No result from this function can independently establish an active RIFT actor.
    """
    if type(pid) is not int or pid <= 0:
        raise ValueError("pid must be a positive integer")
    expected_path = _path_key(expected_executable_path)
    if not isinstance(expected_executable_sha256, str) or not _SHA.fullmatch(expected_executable_sha256):
        raise ValueError("expected_executable_sha256 must be 64 hex characters")
    expected_sha = expected_executable_sha256.lower()
    if expected_start_utc_ticks is not None and (
        type(expected_start_utc_ticks) is not int or expected_start_utc_ticks <= 0
    ):
        raise ValueError("expected_start_utc_ticks must be positive")
    if expected_window_handle is not None and (
        type(expected_window_handle) is not int or expected_window_handle <= 0
    ):
        raise ValueError("expected_window_handle must be positive")
    if expected_host is not None and (
        not isinstance(expected_host, str) or not expected_host.strip()
    ):
        raise ValueError("expected_host must be nonempty")
    provider = api if api is not None else Win32DesktopProbe()
    host = provider.host()
    if not isinstance(host, str) or not host.strip():
        raise IdentityUnavailable("machine identity unavailable")
    if expected_host is not None and host.casefold() != expected_host.casefold():
        raise IdentityUnavailable("host identity mismatch")

    def check_process(info: ProcessInfo) -> ProcessInfo:
        if not isinstance(info, ProcessInfo) or info.pid != pid or info.start_utc_ticks <= 0:
            raise IdentityUnavailable("process information missing or invalid")
        if _path_key(info.executable_path) != expected_path:
            raise IdentityUnavailable("process executable path mismatch")
        if expected_start_utc_ticks is not None and info.start_utc_ticks != expected_start_utc_ticks:
            raise IdentityUnavailable("process start epoch mismatch")
        return info

    try:
        first = check_process(provider.process(pid))
        actual_sha = hash_file(first.executable_path)
        if not isinstance(actual_sha, str) or actual_sha.lower() != expected_sha:
            raise IdentityUnavailable("process executable SHA-256 mismatch")
        after_hash = check_process(provider.process(pid))
        if after_hash != first:
            raise IdentityUnavailable("process changed while hashing executable")
        windows = provider.windows_for_pid(pid)
        if any(type(hwnd) is not int or hwnd <= 0 for hwnd in windows):
            raise IdentityUnavailable("invalid window candidate")
        if expected_window_handle is None:
            if len(windows) != 1:
                raise IdentityUnavailable("window selection ambiguous or unavailable")
            hwnd = windows[0]
        else:
            if expected_window_handle not in windows:
                raise IdentityUnavailable("pinned window missing")
            hwnd = expected_window_handle
        if not provider.window_belongs_to_pid(hwnd, pid):
            raise IdentityUnavailable("window no longer belongs to target process")
        foreground = provider.foreground_root() == hwnd
        if require_foreground and not foreground:
            raise IdentityUnavailable("target window not foreground")
        final = check_process(provider.process(pid))
        if final != first or not provider.window_belongs_to_pid(hwnd, pid):
            raise IdentityUnavailable("process/window identity changed during inspection")
        observed = float(clock())
        if not math.isfinite(observed) or observed < 0:
            raise IdentityUnavailable("monotonic observation clock invalid")
        return DesktopCandidate(host, pid, first.start_utc_ticks, first.executable_path,
                                actual_sha.lower(), hwnd, foreground, observed)
    except (OSError, OverflowError) as error:
        raise IdentityUnavailable("Windows identity inspection failed") from error


class _FileTime(ctypes.Structure):
    _fields_ = (("low", wintypes.DWORD), ("high", wintypes.DWORD))

    def dotnet_ticks(self) -> int:
        return ((int(self.high) << 32) | int(self.low)) + _DOTNET_EPOCH_OFFSET


class Win32DesktopProbe:
    """Only process information and GUI observation; zero input or memory reads."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise IdentityUnavailable("Win32 identity observation requires Windows")
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.u32 = ctypes.WinDLL("user32", use_last_error=True)
        self.k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.k32.OpenProcess.restype = wintypes.HANDLE
        self.k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.k32.CloseHandle.restype = wintypes.BOOL
        self.k32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(_FileTime),) * 4
        self.k32.GetProcessTimes.restype = wintypes.BOOL
        self.k32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
        )
        self.k32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.u32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        self.u32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.u32.GetForegroundWindow.argtypes = ()
        self.u32.GetForegroundWindow.restype = wintypes.HWND
        self.u32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        self.u32.GetAncestor.restype = wintypes.HWND
        self.u32.IsWindow.argtypes = (wintypes.HWND,)
        self.u32.IsWindow.restype = wintypes.BOOL
        self.u32.IsWindowVisible.argtypes = (wintypes.HWND,)
        self.u32.IsWindowVisible.restype = wintypes.BOOL
        self.u32.IsIconic.argtypes = (wintypes.HWND,)
        self.u32.IsIconic.restype = wintypes.BOOL
        self.u32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
        self.u32.GetWindow.restype = wintypes.HWND
        self._callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.u32.EnumWindows.argtypes = (self._callback_type, wintypes.LPARAM)
        self.u32.EnumWindows.restype = wintypes.BOOL

    def host(self) -> str:
        import socket
        return socket.gethostname()

    def process(self, pid: int) -> ProcessInfo:
        handle = self.k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            raise IdentityUnavailable(f"OpenProcess failed (Win32 {ctypes.get_last_error()})")
        try:
            created, exited, kernel, user = (_FileTime() for _ in range(4))
            if not self.k32.GetProcessTimes(
                handle, ctypes.byref(created), ctypes.byref(exited),
                ctypes.byref(kernel), ctypes.byref(user)
            ):
                raise IdentityUnavailable("GetProcessTimes failed")
            path = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(path))
            if not self.k32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
                raise IdentityUnavailable("QueryFullProcessImageNameW failed")
            return ProcessInfo(pid, created.dotnet_ticks(), path.value)
        finally:
            self.k32.CloseHandle(handle)

    def _window_pid(self, hwnd: int) -> int:
        result = wintypes.DWORD()
        thread = self.u32.GetWindowThreadProcessId(hwnd, ctypes.byref(result))
        return int(result.value) if thread else 0

    def window_belongs_to_pid(self, hwnd: int, pid: int) -> bool:
        return bool(self.u32.IsWindow(hwnd)) and self._window_pid(hwnd) == pid

    def windows_for_pid(self, pid: int) -> tuple[int, ...]:
        found: list[int] = []

        def record(hwnd: int, _: int) -> bool:
            if (self._window_pid(hwnd) == pid and self.u32.IsWindowVisible(hwnd)
                    and not self.u32.IsIconic(hwnd) and not self.u32.GetWindow(hwnd, 4)):
                found.append(int(hwnd))
            return True

        callback = self._callback_type(record)
        if not self.u32.EnumWindows(callback, 0):
            raise IdentityUnavailable("EnumWindows failed")
        return tuple(sorted(set(found)))

    def foreground_root(self) -> int:
        foreground = self.u32.GetForegroundWindow()
        return int(self.u32.GetAncestor(foreground, 2) or 0) if foreground else 0
