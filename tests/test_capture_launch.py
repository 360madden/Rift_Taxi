"""CLI preflight/delayed capture tests; all target functions injected and inert."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rift_taxi.cli import main


class CaptureLaunchTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def args(self, kind: str, target: Path, *, delay: str = "0") -> list[str]:
        return [
            kind, "--pid", "123", "--start-ticks", "638000000000000000",
            "--exe-path", r"C:\RIFT\rift_x64.exe", "--sha256", "a" * 64,
            "--hwnd", "12345", "--host", "LEGION",
            "--start-delay-seconds", delay, "--out", str(target),
        ]

    def test_existing_report_is_refused_before_any_live_capture(self) -> None:
        destination = self.folder / "existing.json"
        destination.write_text("old evidence", encoding="utf8")
        for kind, function in (
            ("inspect-native-candidate", "capture_native_candidate"),
            ("inspect-native-burst", "capture_native_burst"),
        ):
            with self.subTest(kind=kind):
                with patch("rift_taxi.cli." + function) as capture:
                    with patch("rift_taxi.cli.time.sleep") as sleep:
                        with contextlib.redirect_stderr(io.StringIO()):
                            self.assertEqual(main(self.args(kind, destination, delay="3")), 2)
                    capture.assert_not_called()
                    sleep.assert_not_called()
        self.assertEqual(destination.read_text(), "old evidence")

    def test_missing_parent_is_rejected_before_inspection(self) -> None:
        target = self.folder / "nonexistent" / "output.json"
        for kind, fn in (
            ("inspect-native-candidate", "capture_native_candidate"),
            ("inspect-native-burst", "capture_native_burst"),
        ):
            with patch("rift_taxi.cli." + fn) as capture:
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(self.args(kind, target)), 2)
                capture.assert_not_called()

    def test_invalid_launch_delay_rejected_without_sleep_or_capture(self) -> None:
        for bad in ("-1", "16", "nan", "inf"):
            for kind, fn in (
                ("inspect-native-candidate", "capture_native_candidate"),
                ("inspect-native-burst", "capture_native_burst"),
            ):
                with self.subTest(kind=kind, bad=bad):
                    with patch("rift_taxi.cli." + fn) as capture, \
                         patch("rift_taxi.cli.time.sleep") as sleep:
                        with contextlib.redirect_stderr(io.StringIO()):
                            self.assertEqual(
                                main(self.args(kind, self.folder / "result.json", delay=bad)), 2
                            )
                        capture.assert_not_called()
                        sleep.assert_not_called()

    def test_launch_delay_precedes_capture_and_new_json_write(self) -> None:
        for index, (kind, fn) in enumerate((
            ("inspect-native-candidate", "capture_native_candidate"),
            ("inspect-native-burst", "capture_native_burst"),
        )):
            destination = self.folder / f"new-{index}.json"
            order: list[str] = []

            def sleep(seconds: float) -> None:
                self.assertEqual(seconds, 0.2)
                order.append("delay")

            def capture(**kwargs: object) -> dict:
                self.assertEqual(order, ["delay"])
                order.append("capture")
                return {"schema": "simulated-only", "inputSent": False}

            with patch("rift_taxi.cli." + fn, side_effect=capture) as mocked_capture, \
                 patch("rift_taxi.cli.time.sleep", side_effect=sleep) as mocked_sleep:
                self.assertEqual(main(self.args(kind, destination, delay="0.2")), 0)
            self.assertEqual(order, ["delay", "capture"])
            self.assertTrue(destination.is_file())
            self.assertFalse(json.loads(destination.read_text())["inputSent"])
            self.assertEqual(mocked_capture.call_count, 1)
            mocked_sleep.assert_called_once_with(0.2)


if __name__ == "__main__":
    unittest.main()
