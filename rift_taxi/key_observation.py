"""Read-only polling of Windows W/A/D key states during an admitted RIFT series.

GetAsyncKeyState only observes an OS key-down bit at the sampling instant.
It NEVER inserts a key, records arbitrary keys, installs a keyboard hook,
or establishes that RIFT consumed a command. Fast taps can be missed.
"""
from __future__ import annotations

import ctypes
import sys
from typing import Callable, Protocol

_VIRTUAL_KEYS = (("W", 0x57), ("A", 0x41), ("D", 0x44))
_DOWN_BIT = 0x8000


class KeyObservationUnavailable(RuntimeError):
    """The passive W/A/D observation could not be collected."""


class KeySnapshotSource(Protocol):
    def snapshot(self) -> dict[str, bool]: ...


def validate_key_snapshot(value: object) -> dict[str, bool]:
    """Reject incomplete/forged key snapshots without inferring UP states."""
    if not isinstance(value, dict) or set(value) != {"W", "A", "D"}:
        raise KeyObservationUnavailable("W/A/D snapshot must contain exactly three keys")
    if any(type(value[k]) is not bool for k, _ in _VIRTUAL_KEYS):
        raise KeyObservationUnavailable("W/A/D snapshot states must be bool")
    return {key: value[key] for key, _ in _VIRTUAL_KEYS}


class Win32KeySnapshot:
    """A read-only Windows key snapshot provider; no input API is declared."""

    def __init__(self, *, read_virtual_key: Callable[[int], int] | None = None):
        if read_virtual_key is None:
            if sys.platform != "win32":
                raise KeyObservationUnavailable("Windows required for passive key polling")
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
            # The Win32 API returns a 16-bit signed SHORT.
            user32.GetAsyncKeyState.restype = ctypes.c_short
            self._user32 = user32
            self._read = user32.GetAsyncKeyState
        else:
            if not callable(read_virtual_key):
                raise ValueError("read_virtual_key must be callable")
            self._user32 = None
            self._read = read_virtual_key

    def snapshot(self) -> dict[str, bool]:
        state: dict[str, bool] = {}
        try:
            for name, virtual_key in _VIRTUAL_KEYS:
                raw = self._read(virtual_key)
                if type(raw) is not int or not -32768 <= raw <= 65535:
                    raise KeyObservationUnavailable("invalid Win32 key-state word")
                # Ignore the low bit: it is an unreliable 'pressed since last
                # call' flag shared with other applications.
                state[name] = bool(raw & _DOWN_BIT)
        except (OSError, RuntimeError, ValueError, TypeError) as error:
            raise KeyObservationUnavailable("W/A/D key polling unavailable") from error
        return state
