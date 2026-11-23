"""Native memory session tests: inert backend plus own-process read-only smoke."""
from __future__ import annotations

import ctypes
from dataclasses import replace
import os
import sys
import unittest

from rift_taxi.native_memory import (
    MainModule, NativeReadUnavailable, ProcessPin, ReadOnlyNativeSession,
)
from rift_taxi.win32_identity import ProcessInfo, Win32DesktopProbe, sha256_file


class MemoryBackend:
    """Injected fake; records calls, never opens a process."""
    def __init__(self) -> None:
        self.pin = ProcessPin(
            71, 638_000_000_000_000_000, r"C:\RIFT\RIFT.exe", "a" * 64
        )
        self.info = ProcessInfo(self.pin.pid, self.pin.start_utc_ticks, self.pin.executable_path)
        self.module = MainModule(0x140000000, 0x4000000, self.pin.executable_path)
        self.read_result = b"ABCD"
        self.close_count = 0
        self.open_count = 0
        self.read_count = 0
        self.change_epoch_on: int | None = None
        self.infos = 0

    def open(self, pid: int) -> int:
        self.open_count += 1
        return 123

    def close(self, handle: int) -> None:
        self.close_count += 1

    def process_info(self, handle: int, pid: int) -> ProcessInfo:
        self.infos += 1
        if self.change_epoch_on is not None and self.infos >= self.change_epoch_on:
            return replace(self.info, start_utc_ticks=self.info.start_utc_ticks + 1)
        return self.info

    def main_module(self, handle: int) -> MainModule:
        return self.module

    def read(self, handle: int, address: int, size: int) -> bytes:
        self.read_count += 1
        return self.read_result


class SessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.driver = MemoryBackend()

    def open(self) -> ReadOnlyNativeSession:
        return ReadOnlyNativeSession.open(
            self.driver.pin, backend=self.driver, hash_file=lambda _: "A" * 64)

    def test_read_exact_and_close(self) -> None:
        with self.open() as session:
            self.assertEqual(session.module.base, 0x140000000)
            self.assertEqual(session.read_exact(0x140000000, 4), b"ABCD")
            self.assertEqual(self.driver.read_count, 1)
        self.assertEqual(self.driver.close_count, 1)
        with self.assertRaisesRegex(NativeReadUnavailable, "closed"):
            session.read_exact(0x140000000, 4)
        session.close()
        self.assertEqual(self.driver.close_count, 1)

    def test_reject_pid_reuse_on_open(self) -> None:
        self.driver.change_epoch_on = 1
        with self.assertRaisesRegex(NativeReadUnavailable, "epoch"):
            self.open()
        self.assertEqual(self.driver.close_count, 1)

    def test_reject_pid_reuse_after_hash(self) -> None:
        self.driver.change_epoch_on = 2
        with self.assertRaisesRegex(NativeReadUnavailable, "epoch"):
            self.open()
        self.assertEqual(self.driver.close_count, 1)

    def test_reject_epoch_change_before_read(self) -> None:
        session = self.open()
        self.driver.change_epoch_on = 3
        with self.assertRaisesRegex(NativeReadUnavailable, "epoch"):
            session.read_exact(0x140000000, 4)
        self.assertEqual(self.driver.read_count, 0)
        session.close()

    def test_reject_epoch_change_after_read(self) -> None:
        session = self.open()
        self.driver.change_epoch_on = 4
        with self.assertRaisesRegex(NativeReadUnavailable, "epoch"):
            session.read_exact(0x140000000, 4)
        self.assertEqual(self.driver.read_count, 1)
        session.close()

    def test_reject_hash_and_main_module_mismatch(self) -> None:
        with self.assertRaisesRegex(NativeReadUnavailable, "hash mismatch"):
            ReadOnlyNativeSession.open(
                self.driver.pin, backend=self.driver, hash_file=lambda _: "b" * 64)
        self.assertEqual(self.driver.close_count, 1)
        self.driver.module = replace(self.driver.module, executable_path=r"C:\Wrong\RIFT.exe")
        with self.assertRaisesRegex(NativeReadUnavailable, "module path"):
            self.open()
        self.assertEqual(self.driver.close_count, 2)

    def test_partial_read_fails_closed(self) -> None:
        self.driver.read_result = b"A"
        with self.open() as session:
            with self.assertRaisesRegex(NativeReadUnavailable, "partial"):
                session.read_exact(0x140000000, 4)

    def test_bounds_and_wrong_types_rejected_without_read(self) -> None:
        with self.open() as session:
            for address, size in (
                (-1, 4), (0, 1), (0x10000, 0), (0x10000, 4097),
                (0x7FFFFFFFFFFF, 2), (0x10000, True), (1.5, 2),
                (0x10000, 4.1),
            ):
                with self.subTest(address=address, size=size):
                    with self.assertRaises(ValueError):
                        session.read_exact(address, size)
            self.assertEqual(self.driver.read_count, 0)

    def test_pin_rejects_bad_identity(self) -> None:
        with self.assertRaises(ValueError):
            replace(self.driver.pin, pid=True)
        with self.assertRaises(ValueError):
            replace(self.driver.pin, start_utc_ticks=0)
        with self.assertRaises(ValueError):
            replace(self.driver.pin, executable_sha256="invalid")
        with self.assertRaises(ValueError):
            replace(self.driver.pin, executable_path="not_absolute.exe")

    def test_module_rejects_bad_bounds(self) -> None:
        with self.assertRaises(ValueError):
            MainModule(0, 100, r"C:\foo.exe")
        with self.assertRaises(ValueError):
            MainModule(0x7FFFFFFFFFFF, 100, r"C:\foo.exe")

    @unittest.skipUnless(sys.platform == "win32", "64-bit Windows smoke test only")
    def test_real_read_only_bytes_from_own_python_process(self) -> None:
        # No game involvement: create and read one local, known buffer.
        own = Win32DesktopProbe().process(os.getpid())
        pin = ProcessPin(
            own.pid, own.start_utc_ticks, own.executable_path,
            sha256_file(own.executable_path)
        )
        original = ctypes.create_string_buffer(b"TaxiReadOnlyTest")
        with ReadOnlyNativeSession.open(pin) as session:
            self.assertEqual(session.read_exact(ctypes.addressof(original), 16), b"TaxiReadOnlyTest")
            self.assertGreater(session.module.size, 0)
            self.assertGreater(session.module.base, 0x10000)


if __name__ == "__main__":
    unittest.main()
