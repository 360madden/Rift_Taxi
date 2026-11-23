"""Pinned high-cadence read-only series tests; no game access or input."""
from __future__ import annotations

from dataclasses import replace
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rift_taxi.cli import main
from rift_taxi.native_candidate import (
    ActorWorldTranslationCandidate, MatrixCopyCandidate,
    PositionFacingCandidate, RefreshGuardCandidate,
)
from rift_taxi.native_memory import MainModule, ProcessPin
from rift_taxi.native_series import SeriesUnavailable, observe_native_series
from rift_taxi.win32_identity import DesktopCandidate, ProcessInfo

PATH = r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"
SHA = "df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01"
PID = 31684
TICKS = 639310312490361378
HWND = 22022232


class Clock:
    def __init__(self):
        self.time = 100.

    def __call__(self):
        return self.time

    def sleep(self, seconds):
        self.time += seconds


class FakeAPI:
    def __init__(self):
        self.front = HWND
        self.windows = (HWND,)
        self.owner = PID
        self.epoch = TICKS
        self.host_value = "LEGION"
        self.calls = 0

    def host(self):
        return self.host_value

    def process(self, pid):
        self.calls += 1
        return ProcessInfo(PID, self.epoch, PATH)

    def windows_for_pid(self, pid):
        return self.windows

    def window_belongs_to_pid(self, hwnd, pid):
        return self.owner == pid and hwnd == HWND

    def foreground_root(self):
        return self.front


class FakeSession:
    def __init__(self, pin):
        self.pin = pin
        self.module = MainModule(0x140000000, 0x4000000, PATH)
        self.opened = 0
        self.closed = 0

    def __enter__(self):
        self.opened += 1
        return self

    def __exit__(self, *_):
        self.closed += 1


class SeriesHarness:
    def __init__(self):
        self.clock = Clock()
        self.api = FakeAPI()
        self.opens = 0
        self.inspections = 0
        self.decodes = 0
        self.owner_changes_at = 0
        self.stale_clock_at = 0
        self.fail_decode_at = 0
        self.fail_fast_at = 0
        self.final_bad = False
        self.session = None
        self.options_seen = []
        self.pins = {
            "pid": PID, "start_utc_ticks": TICKS,
            "executable_path": PATH, "executable_sha256": SHA,
            "window_handle": HWND, "host": "LEGION",
        }

    def inspect(self, pid, **options):
        self.inspections += 1
        assert pid == PID
        assert options["expected_executable_sha256"] == self.pins["executable_sha256"]
        assert options["expected_start_utc_ticks"] == TICKS
        return DesktopCandidate(
            "AMD-DESKTOP" if self.final_bad and self.inspections == 2 else "LEGION",
            PID, TICKS, PATH, SHA, HWND, True, self.clock()
        )

    def open_session(self, pin):
        self.opens += 1
        self.session = FakeSession(pin)
        return self.session

    def decode(self, session, *, clock, **options):
        self.decodes += 1
        self.options_seen.append(options)
        if self.fail_decode_at == self.decodes:
            raise SeriesUnavailable("synthetic pointer changed during read")
        if self.fail_fast_at == self.decodes:
            self.api.front = 0
        x = float(self.decodes)
        m = MatrixCopyCandidate(
            tuple(range(9)), tuple(range(9)), True, 30., 30.,
            "structural-y-planar-matrix-candidate",
            "structural-y-planar-matrix-candidate",
        )
        g = RefreshGuardCandidate(
            "0", "0x0000000000000000", 0,
            "both-known-top-level-routes-ineligible-candidate",
        )
        t = ActorWorldTranslationCandidate(
            (x, 2., 3.), (x, 2., 3.),
            (0., 0., 0.), (0., 0., 0.), (x, 2., 3.),
            0., 0., 0, "normal-render-pointer-absent",
        )
        return PositionFacingCandidate(
            PID, TICKS, SHA,
            900 if self.owner_changes_at == self.decodes else 123,
            (x, 2., 3.), 0., x * 3.,
            clock() + (1. if self.stale_clock_at == self.decodes else 0.),
            matrix_copy_candidate=m if options.get("include_matrix_candidate") else None,
            refresh_guard_candidate=g if options.get("include_refresh_guard_candidate") else None,
            actor_translation_candidate=t if options.get("include_actor_translation_candidate") else None,
        )

    def run(self, **options):
        args = dict(
            **self.pins,
            samples=4, interval_ms=100, max_total_s=6.,
            inspect=self.inspect, api_factory=lambda: self.api,
            open_session=self.open_session, decode=self.decode,
            clock=self.clock, sleep=self.clock.sleep,
        )
        args.update(options)
        return observe_native_series(**args)


class SeriesTests(unittest.TestCase):
    def setUp(self):
        self.harness = SeriesHarness()

    def test_single_pinned_handle_and_two_full_hash_admissions(self):
        report = self.harness.run()
        self.assertEqual(report["schema"], "taxi.native-candidate-series/1")
        self.assertEqual(report["completedSamples"], 4)
        self.assertEqual(self.harness.inspections, 2)
        self.assertEqual(self.harness.opens, 1)
        self.assertEqual(self.harness.decodes, 4)
        self.assertEqual(self.harness.session.closed, 1)
        self.assertEqual(self.harness.api.calls, 8)  # pre+post each sample
        self.assertEqual(report["candidateChanges"]["firstToLastDeltaXYZ"], [3., 0., 0.])
        self.assertTrue(report["candidateChanges"]["anyXYZChanged"])
        self.assertEqual(report["candidateChanges"]["firstToLastYawDeltaDegrees"], 9.)
        self.assertAlmostEqual(report["observedSampleGapSeconds"]["median"], .1)
        self.assertFalse(report["qualifications"]["nativeXYZPassiveFreshnessVerified"])
        self.assertFalse(report["qualifications"]["gameInputSent"])

    def test_slow_initial_sha_admission_does_not_bunch_first_samples(self):
        original = self.harness.inspect
        def slow_initial_admission(pid, **options):
            if self.harness.inspections == 0:
                self.harness.clock.time += 0.48  # rehash/desktop admission overhead
            return original(pid, **options)
        self.harness.inspect = slow_initial_admission
        report = self.harness.run(samples=5, interval_ms=100)
        gaps = [
            b["observedMonotonicSeconds"] - a["observedMonotonicSeconds"]
            for a, b in zip(report["observations"], report["observations"][1:])
        ]
        self.assertEqual(len(gaps), 4)
        self.assertTrue(all(gap >= .099 for gap in gaps))
        self.assertAlmostEqual(report["observedSampleGapSeconds"]["minimum"], .1)
        self.assertEqual(self.harness.opens, 1)
        self.assertEqual(self.harness.inspections, 2)

    def test_slow_midseries_decode_does_not_cause_catchup_burst(self):
        original = self.harness.decode
        def slow_decode(session, *, clock, **options):
            # Model a nonzero decode duration, including a single overrun.
            self.harness.clock.time += .35 if self.harness.decodes == 1 else .001
            return original(session, clock=clock, **options)
        self.harness.decode = slow_decode
        report = self.harness.run(samples=6, interval_ms=100)
        rows = report["observations"]
        starts = [row["captureStartMonotonicSeconds"] for row in rows]
        gaps = [b-a for a,b in zip(starts,starts[1:])]
        self.assertTrue(all(gap >= .099999 for gap in gaps), gaps)
        self.assertAlmostEqual(max(gaps), .35)
        self.assertAlmostEqual(report["observedCaptureStartGapSeconds"]["minimum"], .1)
        self.assertEqual(report["sampleSchedule"], "actual-start-relative-no-catch-up")
        for row in rows:
            self.assertLessEqual(row["captureStartMonotonicSeconds"],
                                 row["observedMonotonicSeconds"])
            self.assertLessEqual(row["observedMonotonicSeconds"],
                                 row["captureEndMonotonicSeconds"])
            self.assertAlmostEqual(row["captureBracketSeconds"],
                row["captureEndMonotonicSeconds"]-row["captureStartMonotonicSeconds"])
        self.assertFalse(report["qualifications"]["nativeXYZPassiveFreshnessVerified"])

    def test_short_sleep_refuses_instead_of_bunching_samples(self):
        def undersleep(seconds):
            self.harness.clock.time += seconds * .5
        with self.assertRaisesRegex(SeriesUnavailable, "requested sample spacing invalid"):
            self.harness.run(sleep=undersleep)
        self.assertEqual(self.harness.decodes, 1)
        self.assertEqual(self.harness.session.closed, 1)

    def test_clock_rollback_between_samples_is_refused(self):
        original = self.harness.decode
        state = {"rollback_pending": False, "reads": 0}
        def decode(session, *, clock, **options):
            row = original(session, clock=clock, **options)
            state["rollback_pending"] = True
            state["reads"] = 0
            return row
        def clock():
            if state["rollback_pending"]:
                state["reads"] += 1
                if state["reads"] == 2:
                    self.harness.clock.time -= .01
            return self.harness.clock()
        self.harness.decode = decode
        with self.assertRaisesRegex(SeriesUnavailable, "clock moved backward between samples"):
            self.harness.run(clock=clock)
        self.assertEqual(self.harness.session.closed, 1)

    def test_final_clock_rollback_is_refused(self):
        original = self.harness.inspect
        def inspect(pid, **options):
            result = original(pid, **options)
            if self.harness.inspections == 2:
                self.harness.clock.time -= .05
            return result
        self.harness.inspect = inspect
        with self.assertRaisesRegex(SeriesUnavailable, "final full identity check"):
            self.harness.run()
        self.assertEqual(self.harness.session.closed, 1)

    def test_unrepresentable_clock_value_is_controlled_refusal(self):
        with self.assertRaisesRegex(SeriesUnavailable, "monotonic clock invalid"):
            self.harness.run(clock=lambda: 10**1000)
        self.assertEqual(self.harness.opens, 0)

    def test_manual_keys_are_not_read_without_explicit_opt_in(self):
        def fail_on_use():
            raise AssertionError("keyboard factory must not run")
        report = self.harness.run(keyboard_factory=fail_on_use)
        self.assertFalse(report["manualWindowsKeyObservationRequested"])
        self.assertIsNone(report["manualWindowsKeyObservation"])
        self.assertNotIn("manualWindowsKeyStates", report["observations"][0])

    def test_manual_windows_key_snapshots_correlate_without_claiming_consumption(self):
        states = [
            {"W": False, "A": False, "D": False},
            {"W": False, "A": False, "D": False},
            {"W": True, "A": False, "D": False},
            {"W": True, "A": False, "D": False},
            {"W": True, "A": False, "D": False},
            {"W": False, "A": False, "D": False},
            {"W": False, "A": False, "D": False},
            {"W": False, "A": False, "D": False},
        ]
        counter = [0]
        def key_reader():
            class PassiveFake:
                def snapshot(self_inner):
                    index = counter[0]
                    counter[0] += 1
                    self.harness.clock.time += .001
                    return states[index]
            return PassiveFake()
        report = self.harness.run(
            observe_manual_keys=True, keyboard_factory=key_reader,
        )
        self.assertEqual(counter[0], 8)
        self.assertTrue(report["manualWindowsKeyObservationRequested"])
        summary = report["manualWindowsKeyObservation"]
        self.assertEqual(summary["pollsPerKey"], 8)
        self.assertEqual(summary["observedDownPollsByKey"], {"W": 3, "A": 0, "D": 0})
        self.assertEqual(summary["nativeReadBracketsWithChangingKeys"], 1)
        edges = summary["sampledStateTransitionWindows"]
        self.assertEqual(len(edges), 2)
        self.assertEqual([(e["fromDown"], e["toDown"]) for e in edges],
                         [(False, True), (True, False)])
        self.assertEqual(edges[0]["previousSampleIndex"], 1)
        self.assertEqual(edges[0]["currentSampleIndex"], 2)
        self.assertEqual(edges[1]["previousSampleIndex"], 3)
        self.assertEqual(edges[1]["currentSampleIndex"], 3)
        self.assertFalse(summary["operatorActionVerified"])
        self.assertFalse(summary["gameInputConsumptionVerified"])
        self.assertFalse(summary["inputInjectedByTaxi"])
        self.assertFalse(report["qualifications"]["externalActionReceiptsProvided"])
        self.assertFalse(report["qualifications"]["gameInputSent"])

    def test_manual_key_snapshot_failure_closes_native_session(self):
        class InvalidKeyboard:
            def snapshot(self):
                return {"W": False, "A": False, "D": 0}
        with self.assertRaisesRegex(SeriesUnavailable, "key polling unavailable"):
            self.harness.run(
                observe_manual_keys=True, keyboard_factory=InvalidKeyboard,
            )
        self.assertEqual(self.harness.session.closed, 1)
        self.assertEqual(self.harness.inspections, 1)

    def test_too_slow_manual_key_poll_is_rejected(self):
        class SlowFake:
            def snapshot(self_inner):
                self.harness.clock.time += .5
                return {"W": False, "A": False, "D": False}
        with self.assertRaisesRegex(SeriesUnavailable, "snapshot exceeded 50 ms"):
            self.harness.run(
                observe_manual_keys=True, keyboard_factory=SlowFake,
            )
        self.assertEqual(self.harness.session.closed, 1)

    def test_cli_manual_key_flag_forwarded_without_injection(self):
        report = self.harness.run()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "manual-keys.json"
            argv = [
                "observe-native-series", "--pid", str(PID),
                "--start-ticks", str(TICKS), "--exe-path", PATH,
                "--sha256", SHA, "--hwnd", str(HWND), "--host", "LEGION",
                "--samples", "4", "--observe-manual-keys", "--out", str(target),
            ]
            with patch("rift_taxi.cli.observe_native_series", return_value=report) as observer:
                self.assertEqual(main(argv), 0)
                self.assertTrue(observer.call_args.kwargs["observe_manual_keys"])
            self.assertFalse(json.loads(target.read_text())["qualifications"]["gameInputSent"])

    def test_three_optional_diagnostics_are_explicit_and_candidate_only(self):
        result = self.harness.run(
            include_matrix_candidate=True,
            include_refresh_guard_candidate=True,
            include_actor_translation_candidate=True,
        )
        self.assertEqual(len(result["observations"][0]["matrixEvidence"]["actorRawBits"]), 9)
        self.assertTrue(result["observations"][0]["matrixEvidence"]["rawBitsMatch"])
        self.assertEqual(result["observations"][0]["refreshGuardEvidence"]["flagRaw"], 0)
        self.assertEqual(result["observations"][0]["actorTranslationEvidence"]["reconstructionResidual"], 0)
        self.assertTrue(all(v is True for v in self.harness.options_seen[0].values()))
        self.assertFalse(result["qualifications"]["playerBodyHeadingVerified"])

    def test_foreground_lost_after_decode_aborts_no_partial_report_and_closes(self):
        self.harness.fail_fast_at = 3
        with self.assertRaisesRegex(SeriesUnavailable, "foreground changed"):
            self.harness.run()
        self.assertEqual(self.harness.session.closed, 1)
        self.assertEqual(self.harness.inspections, 1)

    def test_process_epoch_changed_during_series_aborts(self):
        def decode(session, *, clock, **options):
            sample = SeriesHarness.decode(self.harness, session, clock=clock, **options)
            if self.harness.decodes == 2:
                self.harness.api.epoch += 1
            return sample
        self.harness.decode = decode
        with self.assertRaisesRegex(SeriesUnavailable, "epoch"):
            self.harness.run()
        self.assertEqual(self.harness.session.closed, 1)

    def test_hidden_or_minimized_window_disappears_from_fast_eligibility(self):
        original = self.harness.decode
        def hide_after_second_sample(session, *, clock, **options):
            item = original(session, clock=clock, **options)
            if self.harness.decodes == 2:
                self.harness.api.windows = ()
            return item
        self.harness.decode = hide_after_second_sample
        with self.assertRaisesRegex(SeriesUnavailable, "foreground changed"):
            self.harness.run()
        self.assertEqual(self.harness.session.closed, 1)
        self.assertEqual(self.harness.inspections, 1)

    def test_wrong_trusted_hash_refused_before_opening_memory(self):
        self.harness.pins["executable_sha256"] = "b" * 64
        with self.assertRaisesRegex(SeriesUnavailable, "initial full"):
            self.harness.run()
        self.assertEqual(self.harness.opens, 0)
        self.assertEqual(self.harness.inspections, 1)

    def test_player_owner_changed_aborts(self):
        self.harness.owner_changes_at = 3
        with self.assertRaisesRegex(SeriesUnavailable, "owner changed"):
            self.harness.run()
        self.assertEqual(self.harness.session.closed, 1)

    def test_decoder_source_pid_epoch_and_build_must_match_each_sample(self):
        cases = [
            ("process_id", PID + 1),
            ("process_start_utc_ticks", TICKS + 1),
            ("build_sha256", "e" * 64),
        ]
        for field, bad in cases:
            h = SeriesHarness()
            original = h.decode
            def changed(session, *, clock, **opts):
                row = original(session, clock=clock, **opts)
                return replace(row, **{field: bad}) if h.decodes == 2 else row
            h.decode = changed
            with self.subTest(field=field), self.assertRaisesRegex(
                    SeriesUnavailable, "source PID, epoch or build mismatch"):
                h.run()
            self.assertEqual(h.session.closed, 1)
            self.assertEqual(h.inspections, 1)

    def test_source_clock_outside_bracket_refused(self):
        self.harness.stale_clock_at = 2
        with self.assertRaisesRegex(SeriesUnavailable, "timestamp invalid"):
            self.harness.run()
        self.assertEqual(self.harness.session.closed, 1)

    def test_unqualified_final_full_identity_aborts(self):
        self.harness.final_bad = True
        with self.assertRaisesRegex(SeriesUnavailable, "final full"):
            self.harness.run()
        self.assertEqual(self.harness.inspections, 2)

    def test_decoder_failure_aborts_all_samples_and_closes_handle(self):
        self.harness.fail_decode_at = 2
        with self.assertRaisesRegex(SeriesUnavailable, "synthetic pointer"):
            self.harness.run()
        self.assertEqual(self.harness.decodes, 2)
        self.assertEqual(self.harness.session.closed, 1)

    def test_time_budget_exceeded_aborts(self):
        class SlowHarness(SeriesHarness):
            def decode(self, session, *, clock, **opts):
                self.clock.time += 1.8
                return super().decode(session, clock=clock, **opts)
        h = SlowHarness()
        with self.assertRaisesRegex(SeriesUnavailable, "budget"):
            h.run(max_total_s=2.)
        self.assertEqual(h.session.closed, 1)

    def test_unsupported_arguments_fail_before_inspect(self):
        cases = [
            ("samples", 2), ("samples", 129), ("samples", True),
            ("interval_ms", 0), ("interval_ms", 2001),
            ("max_total_s", 1.), ("max_total_s", float("nan")),
            ("include_matrix_candidate", 1),
            ("include_refresh_guard_candidate", "true"),
            ("observe_manual_keys", 1),
            ("pid", 0), ("start_utc_ticks", 0), ("window_handle", True),
            ("executable_path", "rift_x64.exe"),
            ("executable_sha256", "not-a-hash"), ("host", " "),
        ]
        for field, bad in cases:
            h = SeriesHarness()
            with self.subTest(field=field), self.assertRaises(ValueError):
                h.run(**{field: bad})
            self.assertEqual(h.inspections, 0)
            self.assertEqual(h.opens, 0)

    def test_cli_writes_only_new_report_and_forwards_options(self):
        data = self.harness.run()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "series.json"
            args = [
                "observe-native-series", "--pid", str(PID),
                "--start-ticks", str(TICKS), "--exe-path", PATH,
                "--sha256", SHA, "--hwnd", str(HWND), "--host", "LEGION",
                "--samples", "4", "--interval-ms", "100",
                "--include-actor-translation-candidate", "--out", str(target),
            ]
            with patch("rift_taxi.cli.observe_native_series", return_value=data) as observe:
                self.assertEqual(main(args), 0)
                self.assertTrue(observe.call_args.kwargs["include_actor_translation_candidate"])
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(args), 2)
                self.assertEqual(observe.call_count, 1)
            self.assertEqual(json.loads(target.read_text())["completedSamples"], 4)

    def test_doctor_reports_series_not_game_control(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["doctor"]), 0)
        doc = json.loads(output.getvalue())
        self.assertTrue(doc["nativeCandidateSeriesAvailable"])
        self.assertTrue(doc["readOnlyManualKeyObservationAvailable"])
        self.assertTrue(doc["nativeReadOnlyCandidateReaderImplemented"])
        self.assertFalse(doc["nativeReaderImplemented"])  # qualified live pose not yet
        self.assertFalse(doc["nativeCandidateQualifiedForMovement"])
        self.assertFalse(doc["gameInputEnabled"])


if __name__ == "__main__":
    unittest.main()
