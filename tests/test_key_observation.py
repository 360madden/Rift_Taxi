"""Passive W/A/D key-state observation tests; never synthesize OS input."""
from __future__ import annotations

import sys
import unittest

from rift_taxi.key_observation import (
    KeyObservationUnavailable, Win32KeySnapshot, validate_key_snapshot,
)


class KeySnapshotTests(unittest.TestCase):
    def test_only_three_named_keys_are_queried(self):
        called: list[int] = []
        states = {0x57: -32768, 0x41: 0, 0x44: 1}

        def read(code: int) -> int:
            called.append(code)
            return states[code]

        result = Win32KeySnapshot(read_virtual_key=read).snapshot()
        self.assertEqual(called, [0x57, 0x41, 0x44])
        self.assertEqual(result, {"W": True, "A": False, "D": False})

    def test_ignores_shared_low_pressed_since_last_call_bit(self):
        observed = Win32KeySnapshot(read_virtual_key=lambda _: 1).snapshot()
        self.assertEqual(observed, {"W": False, "A": False, "D": False})

    def test_high_bit_on_signed_or_unsigned_return_is_down(self):
        for raw in (-32768, -32767, 32768, 65535):
            with self.subTest(raw=raw):
                result = Win32KeySnapshot(read_virtual_key=lambda _: raw).snapshot()
                self.assertTrue(all(result.values()))

    def test_rejects_missing_extra_or_nonboolean_states(self):
        for state in (
            None, [], {}, {"W": False, "A": False},
            {"W": False, "A": False, "D": False, "S": False},
            {"W": 0, "A": False, "D": False},
            {"W": False, "A": False, "D": None},
        ):
            with self.subTest(state=state), self.assertRaises(KeyObservationUnavailable):
                validate_key_snapshot(state)

    def test_rejects_bad_win32_read_results(self):
        for raw in (True, "0", None, -32769, 65536):
            with self.subTest(raw=raw), self.assertRaises(KeyObservationUnavailable):
                Win32KeySnapshot(read_virtual_key=lambda _: raw).snapshot()

    def test_probe_os_read_failure_is_unavailable(self):
        def fail(_):
            raise OSError("injected passive read failure")
        with self.assertRaises(KeyObservationUnavailable):
            Win32KeySnapshot(read_virtual_key=fail).snapshot()
        with self.assertRaises(ValueError):
            Win32KeySnapshot(read_virtual_key=42)

    @unittest.skipUnless(sys.platform == "win32", "read-only Windows smoke test")
    def test_real_win32_keyboard_state_query_without_input(self):
        # Whatever keys the user is currently holding, type/shape must be
        # correct. This test does not press, release, or identify input owner.
        result = Win32KeySnapshot().snapshot()
        self.assertEqual(set(result), {"W", "A", "D"})
        self.assertTrue(all(type(v) is bool for v in result.values()))


if __name__ == "__main__":
    unittest.main()
