"""Inert unit tests for Taxi-owned Win32 scan-code adapter. Never send OS input."""
from __future__ import annotations

import ctypes
from dataclasses import replace
import math
import sys
import unittest

from rift_taxi.control import (
    ControlRefused, HeldInputController, LivePose, SessionBinding,
)
from rift_taxi.win32_identity import DesktopCandidate, ProcessInfo
from rift_taxi.win32_input import (
    WindowsScanKeyBackend, Win32ScanSender, _Input, _Keyboard, encode_key_event,
)

EXE = r"C:\Games\RIFT\Live\rift_x64.exe"
SHA = "a" * 64


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value


class FakeProbe:
    def __init__(self, binding: SessionBinding):
        self.binding = binding
        self.process_info = ProcessInfo(binding.process_id, binding.start_ticks, EXE)
        self.hostname = binding.host
        self.ready = True
        self.foreground = binding.window_handle
        self.process_calls = 0

    def host(self):
        return self.hostname

    def process(self, pid):
        self.process_calls += 1
        return self.process_info

    def window_ready(self, hwnd, pid):
        return self.ready and hwnd == self.binding.window_handle and pid == self.binding.process_id

    def foreground_root(self):
        return self.foreground


class FakeSender:
    def __init__(self):
        self.events = []
        self.fail = set()
        self.throw = set()

    def send(self, key, down):
        self.events.append((key, down))
        if (key, down) in self.throw:
            raise OSError("injected SendInput failure")
        return (key, down) not in self.fail


class ScanInputTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.binding = SessionBinding(
            host="LEGION", process_id=2312, start_ticks=638_000_000_000_000_000,
            executable_sha256=SHA, window_handle=789, actor_id="Atank",
            zone_id="SanctumWatch",
        )
        self.probe = FakeProbe(self.binding)
        self.sender = FakeSender()
        self.admits = 0

    def candidate(self) -> DesktopCandidate:
        self.admits += 1
        return DesktopCandidate(
            self.binding.host, self.binding.process_id, self.binding.start_ticks,
            EXE, SHA, self.binding.window_handle, True, self.clock(),
        )

    def pose(self, **kwargs) -> LivePose:
        base = LivePose(
            self.binding, 1, self.clock(), (1.0, 2.0, 3.0), 43.0,
            True, True,
        )
        return replace(base, **kwargs)

    def backend(self) -> WindowsScanKeyBackend:
        def admit(pid, **kwargs):
            self.assertEqual(pid, self.binding.process_id)
            self.assertEqual(kwargs["expected_start_utc_ticks"], self.binding.start_ticks)
            self.assertEqual(kwargs["expected_window_handle"], self.binding.window_handle)
            self.assertTrue(kwargs["require_foreground"])
            return self.candidate()
        return WindowsScanKeyBackend(
            self.binding, EXE, probe=self.probe, sender=self.sender,
            admit=admit, clock=self.clock,
        )

    def test_scancode_packet_layout_and_flags_are_not_real_input(self):
        for key, scan in (("W", 0x11), ("A", 0x1E), ("D", 0x20)):
            down, up = encode_key_event(key, True), encode_key_event(key, False)
            self.assertEqual(down.type, 1)
            self.assertEqual(down.data.ki.wVk, 0)
            self.assertEqual(down.data.ki.wScan, scan)
            self.assertEqual(down.data.ki.dwFlags, 0x0008)
            self.assertEqual(up.data.ki.dwFlags, 0x000A)
            self.assertEqual(up.data.ki.wScan, scan)
        with self.assertRaises(ValueError):
            encode_key_event("SPACE", True)
        with self.assertRaises(ValueError):
            encode_key_event("W", 1)
        if sys.platform == "win32" and ctypes.sizeof(ctypes.c_void_p) == 8:
            self.assertEqual(ctypes.sizeof(_Input), 40)
            self.assertEqual(ctypes.sizeof(_Keyboard), 24)
            # Construction of user32 sender alone never calls SendInput.
            self.assertIsInstance(Win32ScanSender(), Win32ScanSender)

    def test_unarmed_backend_cannot_send_key_down(self):
        b = self.backend()
        self.assertFalse(b.armed)
        self.assertFalse(b.write_key("W", True))
        self.assertTrue(b.write_key("W", False))  # no potentially held key
        self.assertEqual(self.sender.events, [])
        self.assertEqual(self.admits, 0)

    def test_arm_requires_qualified_same_session_fresh_pose(self):
        b = self.backend()
        for bad in (
            self.pose(actor_yaw_verified=False),
            self.pose(foreground_verified=False),
            self.pose(session=replace(self.binding, zone_id="OTHER")),
            self.pose(observed_monotonic_s=self.clock.value - 1),
        ):
            with self.subTest(bad=bad), self.assertRaises(ControlRefused):
                b.arm(bad)
        self.assertFalse(b.armed)
        self.assertEqual(self.sender.events, [])

    def test_successful_arm_press_and_release_is_only_os_acceptance(self):
        b = self.backend()
        b.arm(self.pose())
        self.assertTrue(b.armed)
        self.assertTrue(b.write_key("W", True))
        self.assertTrue(b.write_key("D", True))
        self.assertEqual(b.possibly_held, ("W", "D"))
        self.probe.foreground = 123  # window loses focus
        self.assertTrue(b.write_key("D", False))
        self.assertTrue(b.write_key("W", False))
        self.assertEqual(b.possibly_held, ())
        self.assertEqual(self.sender.events, [
            ("W", True), ("D", True), ("D", False), ("W", False)
        ])

    def test_direct_duplicate_down_fails_closed_and_does_not_repeat(self):
        b = self.backend()
        b.arm(self.pose())
        self.assertTrue(b.write_key("W", True))
        self.assertFalse(b.write_key("W", True))
        self.assertFalse(b.armed)
        self.assertEqual(self.sender.events, [("W", True)])
        self.assertEqual(b.possibly_held, ("W",))
        self.assertEqual(b.disarm(), {"W": True})

    def test_pose_expiring_during_admission_refused_before_any_send(self):
        def slow_admit(*args, **kwargs):
            candidate = self.candidate()
            self.clock.value += .4
            return candidate
        b = WindowsScanKeyBackend(
            self.binding, EXE, probe=self.probe, sender=self.sender,
            admit=slow_admit, clock=self.clock,
        )
        with self.assertRaisesRegex(ControlRefused, "pose stale"):
            b.arm(self.pose())
        self.assertFalse(b.armed)
        self.assertEqual(self.sender.events, [])

    def test_no_new_key_down_after_focus_loss(self):
        b = self.backend()
        b.arm(self.pose())
        self.assertTrue(b.write_key("W", True))
        self.probe.foreground = 123
        self.assertFalse(b.write_key("A", True))
        self.assertFalse(b.armed)
        self.assertEqual(b.possibly_held, ("W",))
        self.assertTrue(b.write_key("W", False))

    def test_no_new_key_down_after_pid_reuse_or_window_hidden(self):
        for mode in ("epoch", "path", "window", "host"):
            self.probe = FakeProbe(self.binding)
            self.sender = FakeSender()
            b = self.backend()
            b.arm(self.pose())
            if mode == "epoch":
                self.probe.process_info = replace(
                    self.probe.process_info, start_utc_ticks=self.binding.start_ticks + 1)
            elif mode == "path":
                self.probe.process_info = replace(
                    self.probe.process_info, executable_path=r"C:\Wrong\RIFT.exe")
            elif mode == "window":
                self.probe.ready = False
            else:
                self.probe.hostname = "AMD-DESKTOP"
            with self.subTest(mode=mode):
                self.assertFalse(b.write_key("W", True))
                self.assertFalse(b.armed)
                self.assertEqual(self.sender.events, [])

    def test_failed_sendinput_down_keeps_uncertainty_for_release(self):
        self.sender.fail.add(("W", True))
        b = self.backend()
        b.arm(self.pose())
        self.assertFalse(b.write_key("W", True))
        self.assertEqual(b.possibly_held, ("W",))
        self.probe.foreground = 123
        self.sender.fail.add(("W", False))
        self.assertFalse(b.write_key("W", False))
        self.assertEqual(b.possibly_held, ("W",))
        self.sender.fail.clear()
        self.assertEqual(b.release_all(), {"W": True})
        self.assertEqual(b.possibly_held, ())

    def test_sender_exception_keeps_uncertainty_and_release_retries(self):
        self.sender.throw.add(("D", True))
        b = self.backend()
        b.arm(self.pose())
        self.assertFalse(b.write_key("D", True))
        self.assertIn("D", b.possibly_held)
        self.sender.throw.add(("D", False))
        self.assertEqual(b.release_all(), {"D": False})
        self.assertIn("D", b.possibly_held)
        self.sender.throw.clear()
        self.assertEqual(b.disarm(), {"D": True})
        self.assertFalse(b.armed)

    def test_invalid_input_values_do_not_send(self):
        b = self.backend()
        b.arm(self.pose())
        for key, down in (
            ("w", True), ("S", True), ("SPACE", True), (None, True),
            ("W", 1), ("W", None),
        ):
            with self.subTest(key=key, down=down):
                self.assertFalse(b.write_key(key, down))
        self.assertEqual(self.sender.events, [])

    def test_rearm_denied_while_key_uncertain(self):
        b = self.backend()
        b.arm(self.pose())
        b.write_key("W", True)
        with self.assertRaises(ControlRefused):
            b.arm(self.pose())
        b.disarm()
        self.assertEqual(b.possibly_held, ())
        b.arm(self.pose())
        self.assertTrue(b.armed)

    def test_admission_fails_when_os_identity_or_sha_wrong(self):
        self.probe.foreground = 777
        b = self.backend()
        with self.assertRaisesRegex(ControlRefused, "OS process"):
            b.arm(self.pose())
        self.probe.foreground = self.binding.window_handle
        b = WindowsScanKeyBackend(
            self.binding, EXE, probe=self.probe, sender=self.sender,
            admit=lambda *_a, **_kw: replace(self.candidate(), executable_sha256="b" * 64),
            clock=self.clock,
        )
        with self.assertRaisesRegex(ControlRefused, "admission identity"):
            b.arm(self.pose())

    def test_controller_gate_composes_with_inert_scan_backend(self):
        b = self.backend()
        b.arm(self.pose())
        with HeldInputController(
            self.binding, b, clock=self.clock,
            max_pose_age_s=.2, max_hold_s=.4,
        ) as controller:
            controller.apply(("W",), self.pose(sequence=1))
            self.clock.value += .05
            controller.apply(("W", "D"), self.pose(sequence=2))
            self.clock.value += .05
            controller.apply(("W", "A"), self.pose(sequence=3))
            self.assertEqual(self.sender.events[:4], [
                ("W", True), ("D", True), ("D", False), ("A", True)
            ])
            controller.stop("test")
            self.assertEqual(b.possibly_held, ())
            self.assertFalse(controller.status.game_response_verified)

    def test_invalid_backend_configuration_rejected(self):
        for invalid_session, invalid_path in (
            (None, EXE), (self.binding, "relative.exe"),
        ):
            with self.assertRaises(ValueError):
                WindowsScanKeyBackend(
                    invalid_session, invalid_path,
                    probe=self.probe, sender=self.sender,
                )


if __name__ == "__main__":
    unittest.main()
