"""Bounded Win32 left-mouse and relative-motion packets for camera-only research.

No OS input is sent on import or sender construction. This module is separate
from Taxi's production W/A/D controller. Mouse-button release is independently
supervised by release_supervisor for physical calibration use.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys

from .win32_input import _Input

_INPUT_MOUSE = 0
_MOUSE_MOVE = 0x0001
_MOUSE_LEFTDOWN = 0x0002
_MOUSE_LEFTUP = 0x0004
_VK_LBUTTON = 0x01
_VK_RBUTTON = 0x02


class _Point(ctypes.Structure):
    _fields_ = (("x", wintypes.LONG), ("y", wintypes.LONG))


class _Rect(ctypes.Structure):
    _fields_ = (("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG))


def encode_left_edge(is_down: bool) -> _Input:
    """Produce an inert Win32 INPUT packet, without sending it."""
    if type(is_down) is not bool:
        raise ValueError("explicit left-mouse boolean edge required")
    packet = _Input()
    packet.type = _INPUT_MOUSE
    packet.data.mi.dwFlags = _MOUSE_LEFTDOWN if is_down else _MOUSE_LEFTUP
    return packet


def encode_relative_motion(dx: int, dy: int = 0) -> _Input:
    """Inert bounded relative mouse-motion packet; calibration only."""
    if (type(dx) is not int or type(dy) is not int
            or abs(dx) > 100 or abs(dy) > 100
            or (dx == 0 and dy == 0)):
        raise ValueError("relative mouse step must be nonzero and <=100 px per axis")
    packet = _Input()
    packet.type = _INPUT_MOUSE
    packet.data.mi.dx = dx
    packet.data.mi.dy = dy
    packet.data.mi.dwFlags = _MOUSE_MOVE
    return packet


class Win32MouseSender:
    """Raw OS packet adapter; not a navigation actuator or game receipt."""

    def __init__(self) -> None:
        if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
            raise RuntimeError("64-bit Windows required for camera mouse diagnostic")
        self._u = ctypes.WinDLL("user32", use_last_error=True)
        self._u.SendInput.argtypes = (
            wintypes.UINT, ctypes.POINTER(_Input), ctypes.c_int)
        self._u.SendInput.restype = wintypes.UINT
        self._u.GetCursorPos.argtypes = (ctypes.POINTER(_Point),)
        self._u.GetCursorPos.restype = wintypes.BOOL
        self._u.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
        self._u.SetCursorPos.restype = wintypes.BOOL
        self._u.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(_Rect))
        self._u.GetWindowRect.restype = wintypes.BOOL
        self._u.GetAsyncKeyState.argtypes = (ctypes.c_int,)
        self._u.GetAsyncKeyState.restype = wintypes.SHORT
        if ctypes.sizeof(_Input) != 40:
            raise RuntimeError("Windows mouse INPUT ABI does not match")

    def _send(self, packet: _Input) -> bool:
        return self._u.SendInput(1, ctypes.byref(packet), ctypes.sizeof(_Input)) == 1

    def send(self, key: str, is_down: bool) -> bool:
        if type(key) is not str or key != "MOUSE_LEFT":
            raise ValueError("mouse diagnostic permits left button only")
        return self._send(encode_left_edge(is_down))

    def move_relative(self, dx: int, dy: int = 0) -> bool:
        return self._send(encode_relative_motion(dx, dy))

    def cursor_position(self) -> tuple[int, int]:
        point = _Point()
        if not self._u.GetCursorPos(ctypes.byref(point)):
            raise RuntimeError("GetCursorPos failed")
        return int(point.x), int(point.y)

    def position_cursor(self, x: int, y: int) -> bool:
        if type(x) is not int or type(y) is not int:
            raise ValueError("integer screen cursor position required")
        return bool(self._u.SetCursorPos(x, y))

    def window_rect(self, hwnd: int) -> tuple[int, int, int, int]:
        if type(hwnd) is not int or hwnd <= 0:
            raise ValueError("current positive HWND required")
        rect = _Rect()
        if not self._u.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise RuntimeError("GetWindowRect failed")
        return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)

    def left_pressed(self) -> bool:
        return bool(self._u.GetAsyncKeyState(_VK_LBUTTON) & 0x8000)

    def right_pressed(self) -> bool:
        return bool(self._u.GetAsyncKeyState(_VK_RBUTTON) & 0x8000)
