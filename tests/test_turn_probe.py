"""Strictly bounded A/D diagnostic tests; fake sender or dry-run worker only."""
from __future__ import annotations

from dataclasses import replace
import json
import math
import contextlib
import io
from unittest.mock import patch
from pathlib import Path
import tempfile
import time
import unittest

from rift_taxi.release_supervisor import (
    ExternalReleaseSupervisor, ReleaseLeasePin, SupervisorUnavailable,
)
from rift_taxi.turn_probe import TurnProbeRefused, run_turn_probe, run_forward_probe
from rift_taxi.cli import main
from rift_taxi.win32_identity import DesktopCandidate

PATH = r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"
SHA = "a" * 64
OWNER = 9388


class FakeClock:
    def __init__(self):
        self.time = 100.

    def __call__(self):
        return self.time

    def sleep(self, delay):
        self.time += delay


class FakeWorker:
    def __init__(self, *, dry_run):
        self.dry_run = dry_run
        self.alive = True
        self.keys = set()
        self.events = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.alive = False

    def reserve(self, key):
        self.events.append(("reserve", key))
        self.keys.add(key)
        return {"stopped": False, "possibleHeld": list(self.keys)}

    def renew(self):
        self.events.append(("renew", None))
        return {"stopped": False, "possibleHeld": list(self.keys)}

    def clear(self, key):
        self.events.append(("clear", key))
        self.keys.discard(key)
        return {"stopped": False, "possibleHeld": list(self.keys)}

    def stop(self):
        self.events.append(("stop", None))
        self.keys.clear()
        return {"stopped": True, "possibleHeld": []}


class FakeReader:
    def snapshot(self):
        return {"W": False, "A": False, "D": False}


class FakeSender:
    def __init__(self, *, accept_down=True, accept_up=True):
        self.events = []
        self.accept_down = accept_down
        self.accept_up = accept_up

    def send(self, key, down):
        self.events.append((key, down))
        return self.accept_down if down else self.accept_up


class TurnHarness:
    def __init__(self):
        self.clock = FakeClock()
        self.pin = ReleaseLeasePin("LEGION", 777, 639310421805307472,
                                   8899, PATH, SHA)
        self.scenes = 0
        self.reads = 0
        self.identity_calls = 0
        self.after_owner = OWNER
        self.worker = None
        self.sender = FakeSender()
        self.previous = None
        self.scene_sha = "b" * 64
        self.temp = tempfile.TemporaryDirectory()
        self.audit = str(Path(self.temp.name) / "child.jsonl")

    def close(self):
        self.temp.cleanup()

    def inspect(self, pid, **kwargs):
        self.identity_calls += 1
        assert pid == self.pin.pid
        assert kwargs["require_foreground"]
        return DesktopCandidate("LEGION", self.pin.pid, self.pin.start_utc_ticks,
                                PATH, SHA, self.pin.hwnd, True, self.clock())

    def capture(self, **kwargs):
        self.reads += 1
        assert kwargs["include_matrix_candidate"] is True
        actor = OWNER if self.reads == 1 else self.after_owner
        x = float(self.reads)
        angle = 15. if self.reads == 1 else 21.
        return {
            "schema": "taxi.native-candidate/1",
            "status": "candidate-only",
            "process": {
                "host": "LEGION", "pid": self.pin.pid,
                "startUtcTicks": self.pin.start_utc_ticks,
                "windowHandle": self.pin.hwnd,
                "executablePath": PATH, "onDiskExecutableSha256": SHA,
            },
            "candidate": {
                "ownerKeyDecimal": str(actor),
                "xyz": [x, 2., 3.],
                "playerSystemBearingDegrees": -angle,
                "observationMonotonicSeconds": self.clock(),
            },
            "evidence": {
                "actorHeadingQualified": False,
                "passivePositionFreshnessQualified": False,
                "liveInGameResponseVerified": False,
                "inputSent": False,
            },
            "matrixEvidence": {
                "actorPlanarAngleDegreesCandidate": angle,
                "actorHeadingQualified": False,
            },
        }

    def release_start(self, pin, **kwargs):
        assert pin == self.pin
        self.worker = FakeWorker(dry_run=kwargs["dry_run"])
        return self.worker

    def run(self, **args):
        config = dict(pin=self.pin, expected_owner_key=OWNER, key="A",
                      hold_ms=100, audit_path=self.audit,
                      scene_image_sha256=self.scene_sha,
                      dry_run=True, inspect=self.inspect, capture=self.capture,
                      key_factory=FakeReader,
                      sender_factory=lambda: self.sender,
                      release_start=self.release_start,
                      clock=self.clock, sleeper=self.clock.sleep)
        config.update(args)
        return run_turn_probe(**config)


class TurnProbeTests(unittest.TestCase):
    def setUp(self):
        self.h = TurnHarness()
        self.addCleanup(self.h.close)

    def test_default_dry_run_captures_two_candidates_but_injects_no_os_key(self):
        result = self.h.run()
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["schema"], "taxi.m1-bounded-turn-probe/1")
        self.assertEqual(result["action"]["requestedKey"], "A")
        self.assertEqual(result["action"]["requestedHoldMilliseconds"], 100)
        self.assertFalse(result["action"]["osKeyDownAccepted"])
        self.assertFalse(result["action"]["osKeyUpAccepted"])
        self.assertFalse(result["action"]["inputInjectedByTaxi"])
        self.assertEqual(result["candidateChanges"]["actorMatrixAngleDeltaDegrees"], 6.)
        self.assertEqual(result["candidateChanges"]["playerSystemYawDeltaDegrees"], -6.)
        self.assertEqual(self.h.worker.events, [
            ("reserve", "A"), ("clear", "A"), ("stop", None)
        ])
        self.assertEqual(self.h.reads, 2)
        self.assertFalse(result["candidateChanges"]["gameMotionIndependentlyVerified"])

    def test_diagnostic_never_accepts_w_or_unbounded_hold(self):
        for args in ({"key": "W"}, {"key": "a"}, {"key": "SPACE"},
                     {"hold_ms": 161}, {"hold_ms": 20}, {"hold_ms": True},
                     {"expected_owner_key": 0}):
            h = TurnHarness()
            self.addCleanup(h.close)
            with self.subTest(args=args), self.assertRaises(ValueError):
                h.run(**args)
            self.assertEqual(h.reads, 0)
            self.assertIsNone(h.worker)

    def test_wrong_owner_after_action_refuses_candidate_promotion(self):
        self.h.after_owner = OWNER + 1
        with self.assertRaisesRegex(TurnProbeRefused, "actor, session"):
            self.h.run()
        self.assertIn(("stop", None), self.h.worker.events)

    def test_physical_probe_refuses_missing_scene_image_receipt(self):
        with self.assertRaisesRegex(ValueError, "independently reviewed"):
            self.h.run(dry_run=False, scene_image_sha256=None)
        self.assertIsNone(self.h.worker)
        self.assertEqual(self.h.reads, 0)

    def test_injected_sender_error_still_attempts_key_up_and_stops(self):
        self.h.sender = FakeSender(accept_down=False)
        with self.assertRaisesRegex(TurnProbeRefused, "DOWN not accepted"):
            self.h.run(dry_run=False)
        self.assertEqual(self.h.sender.events, [("A", True), ("A", False)])
        self.assertEqual(self.h.worker.events, [
            ("reserve", "A"), ("clear", "A"), ("stop", None)
        ])

    def test_injected_up_failure_refuses_finished_receipt(self):
        self.h.sender = FakeSender(accept_up=False)
        with self.assertRaisesRegex(TurnProbeRefused, "UP not accepted"):
            self.h.run(dry_run=False)
        self.assertEqual(self.h.sender.events, [("A", True), ("A", False)])
        self.assertEqual(self.h.worker.events, [
            ("reserve", "A"), ("stop", None)
        ])

    def test_before_probe_all_keys_up_is_mandatory(self):
        class BusyReader:
            def snapshot(self):
                return {"W": True, "A": False, "D": False}
        with self.assertRaisesRegex(TurnProbeRefused, "already down"):
            self.h.run(key_factory=BusyReader)
        self.assertEqual(self.h.reads, 0)
        self.assertIsNone(self.h.worker)

    def test_missing_scene_hash_is_allowed_for_inert_dry_run(self):
        outcome = self.h.run(scene_image_sha256=None)
        self.assertTrue(outcome["dryRun"])

    def test_cli_defaults_to_dryrun_and_explicit_physical_switch_is_forwarded(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "report.json"
            audit = Path(folder) / "audit.jsonl"
            args = [
                "probe-ad-turn",
                "--pid", str(self.h.pin.pid), "--start-ticks", str(self.h.pin.start_utc_ticks),
                "--exe-path", PATH, "--sha256", SHA,
                "--hwnd", str(self.h.pin.hwnd), "--host", "LEGION",
                "--owner-key", str(OWNER), "--key", "D", "--hold-ms", "100",
                "--audit", str(audit), "--out", str(out),
                "--scene-image-sha256", self.h.scene_sha,
            ]
            with patch("rift_taxi.cli.run_turn_probe", return_value=self.h.run()) as probe:
                self.assertEqual(main(args), 0)
                self.assertTrue(probe.call_args.kwargs["dry_run"])
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(args), 2)  # no source recreation/overwrite
                self.assertEqual(probe.call_count, 1)
            self.assertEqual(json.loads(out.read_text())["status"],
                             "calibration-candidate-only")
            other = Path(folder) / "physical.json"
            args[args.index(str(out))] = str(other)
            args.append("--execute-physical")
            with patch("rift_taxi.cli.run_turn_probe", return_value=self.h.run()) as probe:
                self.assertEqual(main(args), 0)
                self.assertFalse(probe.call_args.kwargs["dry_run"])

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows child process only")
    def test_actual_release_child_can_run_in_dry_mode_with_exact_diagnostic_pin(self):
        with ExternalReleaseSupervisor.start_turn_probe(
            self.h.pin, dry_run=True, ttl_s=.45,
            audit_path=self.h.audit,
        ) as worker:
            self.assertTrue(worker.alive)
            self.assertTrue(worker.dry_run)
            worker.reserve("A")
            stopped = worker.stop()
            self.assertTrue(stopped["stopped"])
        log = [json.loads(line) for line in Path(self.h.audit).read_text().splitlines()]
        self.assertIn("simulated-key-up", [line["event"] for line in log])
        self.assertNotIn("native-key-up-attempt", [line["event"] for line in log])



class ForwardProbeTests(unittest.TestCase):
    """W-only diagnostic is independent from route navigation; fake senders only."""

    def setUp(self):
        self.h = TurnHarness()
        self.addCleanup(self.h.close)

    def forward(self, **kwargs):
        opts = dict(
            pin=self.h.pin, expected_owner_key=OWNER, hold_ms=100,
            audit_path=self.h.audit, scene_image_sha256=self.h.scene_sha,
            dry_run=True, inspect=self.h.inspect, capture=self.h.capture,
            key_factory=FakeReader, sender_factory=lambda: self.h.sender,
            release_start=self.h.release_start, clock=self.h.clock,
            sleeper=self.h.clock.sleep,
        )
        opts.update(kwargs)
        return run_forward_probe(**opts)

    def test_forward_default_dryrun_three_candidate_samples_and_no_input(self):
        result = self.forward()
        self.assertEqual(result["schema"], "taxi.m1-bounded-forward-probe/1")
        self.assertEqual(result["probeKind"], "forward")
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["action"]["requestedKey"], "W")
        self.assertFalse(result["action"]["osKeyDownAccepted"])
        self.assertFalse(result["action"]["inputInjectedByTaxi"])
        self.assertEqual(result["candidateChanges"]["planarDistanceXZCandidate"], 1.)
        self.assertEqual(result["candidateChanges"]["settledDeltaXYZCandidate"], [2., 0., 0.])
        self.assertIsNotNone(result["candidateSettledAfterRelease"])
        self.assertEqual(self.h.reads, 3)
        self.assertEqual(self.h.worker.events, [
            ("reserve", "W"), ("renew", None), ("clear", "W"), ("stop", None)
        ])
        self.assertEqual(self.h.sender.events, [])
        self.assertFalse(result["candidateChanges"]["gameMotionIndependentlyVerified"])

    def test_fake_physical_sender_brackets_only_w_and_releases(self):
        report = self.forward(dry_run=False)
        self.assertEqual(self.h.sender.events, [("W", True), ("W", False)])
        self.assertTrue(report["action"]["osKeyUpAccepted"])
        self.assertEqual(report["action"]["sampledAfterKeyUp"],
                         {"W": False, "A": False, "D": False})
        self.assertFalse(report["action"]["gameInputConsumptionVerified"])

    def test_forward_refuses_missing_scene_wrong_hold_and_bad_actor(self):
        for override in (
            {"dry_run": False, "scene_image_sha256": None},
            {"hold_ms": 200}, {"hold_ms": 0}, {"hold_ms": True},
        ):
            with self.subTest(override=override):
                h = TurnHarness()
                self.addCleanup(h.close)
                with self.assertRaises(ValueError):
                    self.forward(**override)
        self.h.after_owner = OWNER + 5
        with self.assertRaisesRegex(TurnProbeRefused, "actor, session"):
            self.forward()
        self.assertIsNotNone(self.h.worker)

    def test_expired_release_lease_refuses_w_down(self):
        class ExpiredWorker(FakeWorker):
            def renew(self):
                self.events.append(("renew", None))
                return {"stopped": True, "possibleHeld": []}
        def start(pin, **kwargs):
            self.h.worker = ExpiredWorker(dry_run=kwargs["dry_run"])
            return self.h.worker
        with self.assertRaisesRegex(TurnProbeRefused, "lease was not live"):
            self.forward(dry_run=False, release_start=start)
        self.assertNotIn(("W", True), self.h.sender.events)
        self.assertIn(("W", False), self.h.sender.events)

    def test_sender_up_failure_refuses_finished_receipt(self):
        self.h.sender = FakeSender(accept_up=False)
        with self.assertRaisesRegex(TurnProbeRefused, "UP not accepted"):
            self.forward(dry_run=False)
        self.assertEqual(self.h.sender.events, [("W", True), ("W", False)])

    def test_cli_dryrun_default_and_explicit_physical_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            base = [
                "probe-w-forward", "--pid", str(self.h.pin.pid),
                "--start-ticks", str(self.h.pin.start_utc_ticks),
                "--exe-path", PATH, "--sha256", SHA,
                "--hwnd", str(self.h.pin.hwnd), "--host", "LEGION",
                "--owner-key", str(OWNER), "--hold-ms", "100",
                "--audit", str(Path(folder) / "release.jsonl"),
                "--scene-image-sha256", self.h.scene_sha,
                "--out", str(Path(folder) / "dry.json"),
            ]
            with patch("rift_taxi.cli.run_forward_probe",
                       return_value=self.forward()) as probe:
                self.assertEqual(main(base), 0)
                self.assertTrue(probe.call_args.kwargs["dry_run"])
            physical = base.copy()
            physical[-1] = str(Path(folder) / "physical.json")
            physical.append("--execute-physical")
            with patch("rift_taxi.cli.run_forward_probe",
                       return_value=self.forward()) as probe:
                self.assertEqual(main(physical), 0)
                self.assertFalse(probe.call_args.kwargs["dry_run"])

    @unittest.skipUnless(__import__("sys").platform == "win32",
                         "Windows external release child only")
    def test_real_external_child_can_reserve_w_in_dry_mode(self):
        with ExternalReleaseSupervisor.start_turn_probe(
            self.h.pin, dry_run=True, ttl_s=.45, audit_path=self.h.audit,
        ) as worker:
            reserved = worker.reserve("W")
            self.assertIn("W", reserved["possibleHeld"])
            self.assertTrue(worker.stop()["stopped"])
        log = [json.loads(line) for line in Path(self.h.audit).read_text().splitlines()]
        self.assertIn("simulated-key-up", [event["event"] for event in log])


if __name__ == "__main__":
    unittest.main()
