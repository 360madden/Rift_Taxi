"""Synthetic capture-bracketing tests; does not inspect any game process."""
from __future__ import annotations

from dataclasses import replace
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rift_taxi.native_capture import CandidateCaptureRefused, capture_native_candidate
from rift_taxi.native_candidate import PositionFacingCandidate, NativeCandidateUnavailable
from rift_taxi.win32_identity import DesktopCandidate
from rift_taxi.cli import main

SHA = "df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01"
EXE = r"C:\Games\RIFT\RIFT.exe"


class CaptureFixture:
    def __init__(self) -> None:
        self.windows: list[DesktopCandidate] = [
            DesktopCandidate("LEGION", 7, 638_000_000_000_000_000,
                             EXE, SHA, 9999, True, 100.0),
            DesktopCandidate("LEGION", 7, 638_000_000_000_000_000,
                             EXE, SHA, 9999, True, 100.5),
        ]
        self.result = PositionFacingCandidate(
            7, self.windows[0].start_utc_ticks, SHA, 12345,
            (1.0, 2.0, 3.0), 0.5, 28.6478897565, 100.25
        )
        self.inspects = 0
        self.opened = 0
        self.closed = 0

    def inspect(self, pid: int, **options: object) -> DesktopCandidate:
        assert pid == 7
        assert options["expected_executable_sha256"] == SHA
        assert options["expected_start_utc_ticks"] == 638_000_000_000_000_000
        assert options["expected_window_handle"] == 9999
        assert options["expected_host"] == "LEGION"
        assert options["require_foreground"] is True
        self.inspects += 1
        return self.windows[min(self.inspects - 1, len(self.windows) - 1)]

    class _Session:
        def __init__(self, parent: "CaptureFixture") -> None:
            self.parent = parent

        def __enter__(self) -> "CaptureFixture._Session":
            return self

        def __exit__(self, *_: object) -> None:
            self.parent.closed += 1

    def open_session(self, pin: object) -> "CaptureFixture._Session":
        assert pin.pid == 7 and pin.executable_path == EXE
        self.opened += 1
        return self._Session(self)

    def decode(self, _: object) -> PositionFacingCandidate:
        return self.result

    def capture(self, **kwargs: object) -> dict:
        return capture_native_candidate(
            pid=7, start_utc_ticks=self.windows[0].start_utc_ticks,
            executable_path=EXE, executable_sha256=SHA,
            window_handle=9999, host="LEGION",
            inspect=self.inspect, open_session=self.open_session,
            decode=self.decode, **kwargs
        )


class ReadOnlyCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = CaptureFixture()

    def test_capture_report_never_promotes_candidate_to_live_pose(self) -> None:
        data = self.fixture.capture()
        self.assertEqual(data["schema"], "taxi.native-candidate/1")
        self.assertEqual(data["status"], "candidate-only")
        self.assertEqual(data["candidate"]["xyz"], [1.0, 2.0, 3.0])
        self.assertEqual(data["candidate"]["ownerKeyDecimal"], "12345")
        self.assertEqual(data["evidence"]["actorHeadingQualified"], False)
        self.assertEqual(data["evidence"]["passivePositionFreshnessQualified"], False)
        self.assertEqual(data["evidence"]["inputSent"], False)
        self.assertEqual(data["evidence"]["liveInGameResponseVerified"], False)
        self.assertEqual(data["evidence"]["captureBracketSeconds"], 0.5)
        self.assertEqual(self.fixture.inspects, 2)
        self.assertEqual(self.fixture.closed, 1)

    def test_window_or_foreground_change_aborts(self) -> None:
        self.fixture.windows[1] = replace(self.fixture.windows[1], window_handle=1234)
        with self.assertRaisesRegex(CandidateCaptureRefused, "identity changed"):
            self.fixture.capture()
        self.fixture = CaptureFixture()
        self.fixture.windows[1] = replace(self.fixture.windows[1], foreground=False)
        with self.assertRaisesRegex(CandidateCaptureRefused, "identity changed"):
            self.fixture.capture()

    def test_process_epoch_change_aborts(self) -> None:
        self.fixture.windows[1] = replace(
            self.fixture.windows[1],
            start_utc_ticks=self.fixture.windows[1].start_utc_ticks + 1,
        )
        with self.assertRaisesRegex(CandidateCaptureRefused, "identity changed"):
            self.fixture.capture()

    def test_candidate_identity_mismatch_aborts(self) -> None:
        self.fixture.result = replace(self.fixture.result, owner_key=12345, process_id=9)
        with self.assertRaisesRegex(CandidateCaptureRefused, "source identity mismatch"):
            self.fixture.capture()

    def test_candidate_observation_outside_bracket_aborts(self) -> None:
        self.fixture.result = replace(self.fixture.result, observed_monotonic_s=102)
        with self.assertRaisesRegex(CandidateCaptureRefused, "outside OS capture bracket"):
            self.fixture.capture()

    def test_expired_capture_bracket_aborts(self) -> None:
        self.fixture.windows[1] = replace(
            self.fixture.windows[1], observed_monotonic_s=105
        )
        with self.assertRaisesRegex(CandidateCaptureRefused, "capture exceeded"):
            self.fixture.capture(max_capture_s=1)

    def test_unexpected_qualified_flag_is_rejected(self) -> None:
        self.fixture.result = replace(self.fixture.result, actor_heading_qualified=True)
        with self.assertRaisesRegex(CandidateCaptureRefused, "cannot be advertised"):
            self.fixture.capture()

    def test_decoder_failure_closes_session_without_report(self) -> None:
        def refuse(_: object) -> PositionFacingCandidate:
            raise NativeCandidateUnavailable("unrecognized build")
        self.fixture.decode = refuse
        with self.assertRaisesRegex(NativeCandidateUnavailable, "unrecognized"):
            self.fixture.capture()
        self.assertEqual(self.fixture.closed, 1)
        self.assertEqual(self.fixture.inspects, 1)

    def test_invalid_explicit_pins_rejected_before_inspection(self) -> None:
        for args in (
            {"host": " "}, {"start_utc_ticks": 0}, {"window_handle": 0},
            {"max_capture_s": float("inf")}, {"max_capture_s": 100},
        ):
            fixture = CaptureFixture()
            kwargs = dict(
                pid=7, start_utc_ticks=fixture.windows[0].start_utc_ticks,
                executable_path=EXE, executable_sha256=SHA,
                window_handle=9999, host="LEGION", max_capture_s=3,
            )
            kwargs.update(args)
            with self.subTest(args=args), self.assertRaises(ValueError):
                capture_native_candidate(
                    **kwargs, inspect=fixture.inspect,
                    open_session=fixture.open_session, decode=fixture.decode
                )
            self.assertEqual(fixture.inspects, 0)

    def test_invalid_desktop_inspector_output_refused_before_memory_read(self) -> None:
        with self.assertRaisesRegex(CandidateCaptureRefused, "invalid Windows identity"):
            capture_native_candidate(
                pid=7, start_utc_ticks=self.fixture.windows[0].start_utc_ticks,
                executable_path=EXE, executable_sha256=SHA,
                window_handle=9999, host="LEGION",
                inspect=lambda *_args, **_kwargs: None,
                open_session=self.fixture.open_session, decode=self.fixture.decode
            )
        self.assertEqual(self.fixture.opened, 0)

    def test_cli_writes_new_report_with_explicit_arguments(self) -> None:
        payload = self.fixture.capture()
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "native.json"
            argv = [
                "inspect-native-candidate", "--pid", "7",
                "--start-ticks", str(self.fixture.windows[0].start_utc_ticks),
                "--exe-path", EXE, "--sha256", SHA, "--hwnd", "0x270f",
                "--host", "LEGION", "--out", str(report)
            ]
            with patch("rift_taxi.cli.capture_native_candidate", return_value=payload):
                self.assertEqual(main(argv), 0)
                self.assertEqual(json.loads(report.read_text())["status"], "candidate-only")
                # Never overwrite an existing capture, even with the same path.
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(argv), 2)

    def test_cli_doctor_still_does_not_auto_select_game(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["doctor"]), 0)
        doc = json.loads(output.getvalue())
        self.assertFalse(doc["gameInputEnabled"])
        self.assertFalse(doc["nativeReaderImplemented"])
        self.assertTrue(doc["nativeCandidateCaptureAvailable"])
        self.assertFalse(doc["nativeCandidateQualifiedForMovement"])


if __name__ == "__main__":
    unittest.main()
