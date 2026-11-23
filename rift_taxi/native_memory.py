"""Taxi-owned, read-only bounded Win32 process memory session.

No memory writes, game inputs, process discovery, sibling-repo imports or
dynamic executable offsets. A pinned OS process identity is mandatory. Native
field interpretation is handled separately and remains candidate-only.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import ntpath
import re
import sys
import threading
from typing import Callable

from .win32_identity import ProcessInfo, sha256_file

_MIN_USER = 0x10000
_MAX_USER = 0x00007FFF_FFFF_FFFF
_SHA256 = re.compile(r"[a-fA-F0-9]{64}\Z")
_READ_RIGHTS = 0x0410  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
_LIST_MODULES_ALL = 3


class NativeReadUnavailable(RuntimeError):
    """The exact read-only native session or requested bytes are unavailable."""


def _checked_path(path: str) -> str:
    if not isinstance(path, str) or not ntpath.isabs(path):
        raise ValueError("executable path must be absolute")
    return ntpath.normcase(ntpath.normpath(path))


@dataclass(frozen=True)
class ProcessPin:
    pid: int
    start_utc_ticks: int
    executable_path: str
    executable_sha256: str

    def __post_init__(self) -> None:
        if type(self.pid) is not int or self.pid <= 0:
            raise ValueError("pid must be positive")
        if type(self.start_utc_ticks) is not int or self.start_utc_ticks <= 0:
            raise ValueError("start_utc_ticks must be positive")
        _checked_path(self.executable_path)
        if not isinstance(self.executable_sha256, str) or not _SHA256.fullmatch(self.executable_sha256):
            raise ValueError("executable_sha256 must be 64 hex characters")


@dataclass(frozen=True)
class MainModule:
    base: int
    size: int
    executable_path: str

    def __post_init__(self) -> None:
        if type(self.base) is not int or type(self.size) is not int:
            raise ValueError("module bounds must be integers")
        if self.base < _MIN_USER or self.size <= 0 or self.base > _MAX_USER - self.size:
            raise ValueError("module bounds outside canonical user address range")


class _FileTime(ctypes.Structure):
    _fields_ = (("low", wintypes.DWORD), ("high", wintypes.DWORD))

    def utc_ticks(self) -> int:
        return ((int(self.high) << 32) | int(self.low)) + 504_911_232_000_000_000


class _ModuleInfo(ctypes.Structure):
    _fields_ = (
        ("base", ctypes.c_void_p),
        ("size", wintypes.DWORD),
        ("entry", ctypes.c_void_p),
    )


class Win32ReadBackend:
    """Low-level Win32 calls, permanently read-only."""

    def __init__(self) -> None:
        if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
            raise NativeReadUnavailable("64-bit Windows Python is required")
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.psapi = ctypes.WinDLL("psapi", use_last_error=True)
        self.k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self.k32.OpenProcess.restype = wintypes.HANDLE
        self.k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        self.k32.CloseHandle.restype = wintypes.BOOL
        self.k32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(_FileTime),) * 4
        self.k32.GetProcessTimes.restype = wintypes.BOOL
        self.k32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
        self.k32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.k32.ReadProcessMemory.argtypes = (
            wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t))
        self.k32.ReadProcessMemory.restype = wintypes.BOOL
        self.psapi.EnumProcessModulesEx.argtypes = (
            wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), wintypes.DWORD)
        self.psapi.EnumProcessModulesEx.restype = wintypes.BOOL
        self.psapi.GetModuleInformation.argtypes = (
            wintypes.HANDLE, wintypes.HMODULE, ctypes.POINTER(_ModuleInfo), wintypes.DWORD)
        self.psapi.GetModuleInformation.restype = wintypes.BOOL
        self.psapi.GetModuleFileNameExW.argtypes = (
            wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD)
        self.psapi.GetModuleFileNameExW.restype = wintypes.DWORD

    @staticmethod
    def _failure(action: str) -> NativeReadUnavailable:
        return NativeReadUnavailable(f"{action} failed (Win32 {ctypes.get_last_error()})")

    def open(self, pid: int) -> int:
        h = self.k32.OpenProcess(_READ_RIGHTS, False, pid)
        if not h:
            raise self._failure("OpenProcess read-only")
        return int(h)

    def close(self, handle: int) -> None:
        if handle:
            self.k32.CloseHandle(handle)

    def process_info(self, handle: int, pid: int) -> ProcessInfo:
        created, exited, kernel, user = (_FileTime() for _ in range(4))
        if not self.k32.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited),
            ctypes.byref(kernel), ctypes.byref(user)
        ):
            raise self._failure("GetProcessTimes")
        if ((int(exited.high) << 32) | int(exited.low)) != 0:
            raise NativeReadUnavailable("pinned process has exited")
        path = ctypes.create_unicode_buffer(32768)
        capacity = wintypes.DWORD(len(path))
        if not self.k32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(capacity)):
            raise self._failure("QueryFullProcessImageNameW")
        return ProcessInfo(pid, created.utc_ticks(), path.value)

    def main_module(self, handle: int) -> MainModule:
        # The first enumerated HMODULE is the process main executable, but
        # its path is *also* checked against the pinned process path.
        mods = (wintypes.HMODULE * 32)()
        needed = wintypes.DWORD()
        if not self.psapi.EnumProcessModulesEx(
            handle, mods, ctypes.sizeof(mods), ctypes.byref(needed), _LIST_MODULES_ALL
        ):
            raise self._failure("EnumProcessModulesEx")
        if needed.value < ctypes.sizeof(wintypes.HMODULE):
            raise NativeReadUnavailable("process main module unavailable")
        info = _ModuleInfo()
        if not self.psapi.GetModuleInformation(
            handle, mods[0], ctypes.byref(info), ctypes.sizeof(info)
        ):
            raise self._failure("GetModuleInformation")
        path = ctypes.create_unicode_buffer(32768)
        count = self.psapi.GetModuleFileNameExW(handle, mods[0], path, len(path))
        if count == 0 or count >= len(path):
            raise self._failure("GetModuleFileNameExW")
        return MainModule(int(info.base), int(info.size), path.value)

    def read(self, handle: int, address: int, size: int) -> bytes:
        output = ctypes.create_string_buffer(size)
        received = ctypes.c_size_t(0)
        ok = self.k32.ReadProcessMemory(
            handle, ctypes.c_void_p(address), output, size, ctypes.byref(received))
        if not ok or received.value != size:
            raise NativeReadUnavailable(
                f"ReadProcessMemory incomplete ({received.value}/{size}; Win32 {ctypes.get_last_error()})")
        return output.raw


class ReadOnlyNativeSession:
    """Exact-process, bounded 1..4096 byte reads, with epoch revalidation."""

    def __init__(self, pin: ProcessPin, backend: Win32ReadBackend,
                 handle: int, module: MainModule):
        self.pin = pin
        self.module = module
        self._backend = backend
        self._handle = handle
        self._lock = threading.RLock()
        self._closed = False

    @classmethod
    def open(cls, pin: ProcessPin, *, backend: Win32ReadBackend | None = None,
             hash_file: Callable[[str], str] = sha256_file) -> "ReadOnlyNativeSession":
        if not isinstance(pin, ProcessPin):
            raise ValueError("a validated ProcessPin is mandatory")
        driver = backend if backend is not None else Win32ReadBackend()
        handle = driver.open(pin.pid)
        try:
            cls._check_epoch(pin, driver.process_info(handle, pin.pid))
            sha = hash_file(pin.executable_path)
            if not isinstance(sha, str) or sha.casefold() != pin.executable_sha256.casefold():
                raise NativeReadUnavailable("pinned executable hash mismatch")
            module = driver.main_module(handle)
            if _checked_path(module.executable_path) != _checked_path(pin.executable_path):
                raise NativeReadUnavailable("main module path mismatch")
            cls._check_epoch(pin, driver.process_info(handle, pin.pid))
            return cls(pin, driver, handle, module)
        except Exception:
            driver.close(handle)
            raise

    @staticmethod
    def _check_epoch(pin: ProcessPin, observed: ProcessInfo) -> None:
        if not isinstance(observed, ProcessInfo) or observed.pid != pin.pid:
            raise NativeReadUnavailable("process PID changed")
        if observed.start_utc_ticks != pin.start_utc_ticks:
            raise NativeReadUnavailable("process epoch changed")
        if _checked_path(observed.executable_path) != _checked_path(pin.executable_path):
            raise NativeReadUnavailable("process path changed")

    def read_exact(self, address: int, size: int) -> bytes:
        if type(address) is not int or type(size) is not int or not 1 <= size <= 4096:
            raise ValueError("read requires integer address and 1..4096 bytes")
        if address < _MIN_USER or address > _MAX_USER - size:
            raise ValueError("native read outside canonical user memory")
        with self._lock:
            if self._closed:
                raise NativeReadUnavailable("read-only session closed")
            self._check_epoch(self.pin, self._backend.process_info(self._handle, self.pin.pid))
            value = self._backend.read(self._handle, address, size)
            if not isinstance(value, bytes) or len(value) != size:
                raise NativeReadUnavailable("native read partial or unavailable")
            self._check_epoch(self.pin, self._backend.process_info(self._handle, self.pin.pid))
            return value

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._closed = True
                self._backend.close(self._handle)

    def __enter__(self) -> "ReadOnlyNativeSession":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
