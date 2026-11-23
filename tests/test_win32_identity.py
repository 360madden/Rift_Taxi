"""M1 read-only desktop identity admission tests (no RIFT input or memory)."""
from __future__ import annotations

from dataclasses import replace
import os
import sys
import unittest

from rift_taxi.win32_identity import (
    DesktopCandidate, IdentityUnavailable, ProcessInfo,
    Win32DesktopProbe, inspect_desktop,
)


class FakeApi:
    def __init__(self) -> None:
        self.record = ProcessInfo(41, 638_000_000_000_000_000, r"C:\Games\RIFT\RIFT.exe")
        self.windows = (1234,)
        self.foreground = 1234
        self.owner = 41
        self.calls = 0
        self.change_epoch_on: int | None = None

    def host(self) -> str:
        return "LEGION"

    def process(self, pid: int) -> ProcessInfo:
        self.calls += 1
        if self.change_epoch_on is not None and self.calls >= self.change_epoch_on:
            return replace(self.record, start_utc_ticks=self.record.start_utc_ticks + 1)
        return self.record

    def windows_for_pid(self, pid: int) -> tuple[int, ...]:
        return self.windows

    def window_belongs_to_pid(self, hwnd: int, pid: int) -> bool:
        return self.owner == pid

    def foreground_root(self) -> int:
        return self.foreground


class DesktopIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = FakeApi()

    def inspect(self, **kwargs: object) -> DesktopCandidate:
        return inspect_desktop(
            41, expected_executable_path=r"C:\Games\RIFT\RIFT.exe",
            expected_executable_sha256="a" * 64, api=self.api,
            hash_file=lambda _: "a" * 64, clock=lambda: 123.5,
            **kwargs,
        )

    def test_exact_identity_with_no_actor_pose_claim(self) -> None:
        receipt = self.inspect(
            expected_start_utc_ticks=self.api.record.start_utc_ticks,
            expected_window_handle=1234, expected_host="LEGION",
        )
        self.assertEqual(receipt.window_handle, 1234)
        self.assertEqual(receipt.start_utc_ticks, self.api.record.start_utc_ticks)
        self.assertEqual(receipt.executable_sha256, "a" * 64)
        self.assertTrue(receipt.foreground)
        self.assertFalse(hasattr(receipt, "actor_yaw_deg"))
        self.assertEqual(receipt.observed_monotonic_s, 123.5)
        self.assertEqual(self.api.calls, 3)

    def test_path_case_insensitive_and_absolute(self) -> None:
        self.assertEqual(self.inspect().executable_path, r"C:\Games\RIFT\RIFT.exe")
        with self.assertRaisesRegex(ValueError, "absolute"):
            inspect_desktop(41, expected_executable_path="RIFT.exe",
                            expected_executable_sha256="a" * 64, api=self.api)

    def test_invalid_expected_hash_and_pid(self) -> None:
        with self.assertRaisesRegex(ValueError, "pid"):
            inspect_desktop(True, expected_executable_path=r"C:\RIFT.exe",
                            expected_executable_sha256="a" * 64, api=self.api)
        with self.assertRaisesRegex(ValueError, "sha256"):
            inspect_desktop(41, expected_executable_path=r"C:\RIFT.exe",
                            expected_executable_sha256="bad", api=self.api)

    def test_wrong_executable_hash_rejected(self) -> None:
        with self.assertRaisesRegex(IdentityUnavailable, "SHA-256"):
            inspect_desktop(
                41, expected_executable_path=self.api.record.executable_path,
                expected_executable_sha256="b" * 64, api=self.api,
                hash_file=lambda _: "a" * 64,
            )

    def test_wrong_path_and_start_epoch_rejected(self) -> None:
        self.api.record = replace(self.api.record, executable_path=r"C:\Fake\RIFT.exe")
        with self.assertRaisesRegex(IdentityUnavailable, "path mismatch"):
            self.inspect()
        self.api.record = replace(self.api.record, executable_path=r"C:\Games\RIFT\RIFT.exe")
        with self.assertRaisesRegex(IdentityUnavailable, "epoch mismatch"):
            self.inspect(expected_start_utc_ticks=123)

    def test_pid_recycling_during_hashing_rejected(self) -> None:
        self.api.change_epoch_on = 2
        with self.assertRaisesRegex(IdentityUnavailable, "changed while hashing"):
            self.inspect()

    def test_pid_recycling_after_window_probe_rejected(self) -> None:
        self.api.change_epoch_on = 3
        with self.assertRaisesRegex(IdentityUnavailable, "changed during inspection"):
            self.inspect()

    def test_zero_or_many_windows_require_explicit_pin(self) -> None:
        self.api.windows = ()
        with self.assertRaisesRegex(IdentityUnavailable, "window selection"):
            self.inspect()
        self.api.windows = (1234, 5678)
        with self.assertRaisesRegex(IdentityUnavailable, "window selection"):
            self.inspect()
        self.assertEqual(self.inspect(expected_window_handle=1234).window_handle, 1234)
        with self.assertRaisesRegex(IdentityUnavailable, "pinned window"):
            self.inspect(expected_window_handle=1111)

    def test_foreground_and_window_owner_refused(self) -> None:
        self.api.owner = 99
        with self.assertRaisesRegex(IdentityUnavailable, "no longer belongs"):
            self.inspect()
        self.api.owner = 41
        self.api.foreground = 5678
        with self.assertRaisesRegex(IdentityUnavailable, "not foreground"):
            self.inspect()
        self.assertFalse(self.inspect(require_foreground=False).foreground)

    def test_wrong_machine_and_clock_refused(self) -> None:
        with self.assertRaisesRegex(IdentityUnavailable, "host"):
            self.inspect(expected_host="AMD-DESKTOP")
        with self.assertRaisesRegex(IdentityUnavailable, "clock"):
            inspect_desktop(
                41, expected_executable_path=self.api.record.executable_path,
                expected_executable_sha256="a" * 64, api=self.api,
                hash_file=lambda _: "a" * 64, clock=lambda: float("nan"),
            )

    @unittest.skipUnless(sys.platform == "win32", "requires Windows")
    def test_read_own_python_process_epoch_and_executable(self) -> None:
        """Real Win32 observation, scoped to the test runner, never to RIFT."""
        own = Win32DesktopProbe().process(os.getpid())
        self.assertEqual(own.pid, os.getpid())
        self.assertGreater(own.start_utc_ticks, 600_000_000_000_000_000)
        self.assertTrue(os.path.isfile(own.executable_path))


if __name__ == "__main__":
    unittest.main()
