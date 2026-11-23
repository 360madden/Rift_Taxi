"""Camera-only orbit probe regressions; all mouse input is injected/fake."""
from __future__ import annotations

import contextlib
import ctypes
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from rift_taxi.camera_probe import CameraProbeRefused, run_camera_orbit_probe
from rift_taxi.cli import main
from rift_taxi.release_supervisor import ExternalReleaseSupervisor, ReleaseLeasePin
from rift_taxi.win32_identity import DesktopCandidate
from rift_taxi.win32_input import _Input
from rift_taxi.win32_mouse import (
    Win32MouseSender, encode_left_edge, encode_relative_motion,
)

PATH = r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"
SHA = "a" * 64
OWNER = 8891


class Clock:
    def __init__(self):
        self.now = 100.
    def __call__(self):
        return self.now
    def sleep(self, dt):
        self.now += dt


class FakeKeys:
    def snapshot(self):
        return {"W": False, "A": False, "D": False}


class FakeMouse:
    def __init__(self):
        self.events = []
        self.cursor = (123, 234)
        self.held = False
        self.right = False
        self.fail_up = False
        self.fail_move = False
    def cursor_position(self):
        return self.cursor
    def window_rect(self, hwnd):
        return (0, 0, 1600, 900)
    def left_pressed(self):
        return self.held
    def right_pressed(self):
        return self.right
    def position_cursor(self, x, y):
        self.cursor = (x, y)
        self.events.append(("cursor", x, y))
        return True
    def send(self, key, is_down):
        self.events.append(("button", key, is_down))
        if not is_down and self.fail_up:
            return False
        self.held = is_down
        return True
    def move_relative(self, dx, dy=0):
        self.events.append(("move", dx, dy))
        return not self.fail_move


class FakeWorker:
    def __init__(self, dry_run):
        self.alive = True
        self.dry_run = dry_run
        self.held = []
        self.events = []
    def __enter__(self):
        return self
    def __exit__(self, *_):
        self.alive = False
    def reserve(self, key):
        self.events.append(("reserve", key))
        self.held.append(key)
        return {"stopped": False, "possibleHeld": self.held[:]}
    def renew(self):
        self.events.append(("renew", None))
        return {"stopped": False, "possibleHeld": self.held[:]}
    def clear(self, key):
        self.events.append(("clear", key))
        self.held.remove(key)
    def stop(self):
        self.events.append(("stop", None))
        self.held.clear()
        return {"stopped": True, "possibleHeld": []}


class Harness:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.audit = str(Path(self.temp.name) / "audit.jsonl")
        self.clock = Clock()
        self.pin = ReleaseLeasePin("LEGION", 777,
            639310421805307472, 8899, PATH, SHA)
        self.mouse = FakeMouse()
        self.worker = None
        self.reads = 0
        self.after_owner = OWNER
    def close(self):
        self.temp.cleanup()
    def inspect(self, pid, **kwargs):
        assert pid == self.pin.pid and kwargs["require_foreground"]
        return DesktopCandidate("LEGION", pid, self.pin.start_utc_ticks,
                                PATH, SHA, self.pin.hwnd, True, self.clock())
    def capture(self, **kwargs):
        self.reads += 1
        assert kwargs["include_matrix_candidate"] is True
        actor = OWNER if self.reads == 1 else self.after_owner
        scalar = 12. if self.reads == 1 else 21.
        return {
            "schema": "taxi.native-candidate/1", "status": "candidate-only",
            "process": {
                "host": "LEGION", "pid": self.pin.pid,
                "startUtcTicks": self.pin.start_utc_ticks,
                "windowHandle": self.pin.hwnd, "executablePath": PATH,
                "onDiskExecutableSha256": SHA,
            },
            "candidate": {
                "ownerKeyDecimal": str(actor), "xyz": [2., 3., 4.],
                "playerSystemBearingDegrees": scalar,
                "observationMonotonicSeconds": self.clock(),
            },
            "evidence": {
                "actorHeadingQualified": False,
                "passivePositionFreshnessQualified": False,
                "liveInGameResponseVerified": False, "inputSent": False,
            },
            "matrixEvidence": {
                "actorPlanarAngleDegreesCandidate": 45.,
                "actorHeadingQualified": False,
            },
        }
    def start(self, pin, **kwargs):
        assert pin == self.pin
        self.worker = FakeWorker(kwargs["dry_run"])
        return self.worker
    def run(self, **kwargs):
        opts = {
            "pin": self.pin, "expected_owner_key": OWNER,
            "horizontal_drag_px": 60, "cursor_x_fraction": .36,
            "cursor_y_fraction": .45, "hold_ms": 100,
            "audit_path": self.audit, "scene_image_sha256": "b"*64,
            "dry_run": True, "inspect": self.inspect,
            "capture": self.capture, "key_factory": FakeKeys,
            "mouse_factory": lambda: self.mouse,
            "release_start": self.start, "clock": self.clock,
            "sleeper": self.clock.sleep,
        }
        opts.update(kwargs)
        return run_camera_orbit_probe(**opts)


class CameraMouseTests(unittest.TestCase):
    def test_mouse_packets_are_inert_and_bounded(self):
        self.assertEqual(encode_left_edge(True).type, 0)
        self.assertEqual(encode_left_edge(True).data.mi.dwFlags, 0x0002)
        self.assertEqual(encode_left_edge(False).data.mi.dwFlags, 0x0004)
        pkt = encode_relative_motion(21)
        self.assertEqual((pkt.type, pkt.data.mi.dx, pkt.data.mi.dwFlags),
                         (0, 21, 0x0001))
        for bad in [True, 0, "W"]:
            with self.assertRaises(ValueError):
                encode_relative_motion(bad)
        for bad in [False, 101, -101]:
            with self.assertRaises(ValueError):
                encode_relative_motion(bad, 0)
        with self.assertRaises(ValueError):
            encode_left_edge(1)
        if sys.platform == "win32" and ctypes.sizeof(ctypes.c_void_p) == 8:
            self.assertEqual(ctypes.sizeof(_Input), 40)
            # Constructor only, never sends an event.
            self.assertIsInstance(Win32MouseSender(), Win32MouseSender)

    def test_default_dryrun_is_inert_and_reports_candidate_only(self):
        h = Harness(); self.addCleanup(h.close)
        result = h.run()
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["schema"], "taxi.m1-camera-only-orbit-probe/1")
        self.assertFalse(result["action"]["mouseDownAcceptedByOS"])
        self.assertFalse(result["action"]["gameCameraOrbitIndependentlyVerified"])
        self.assertEqual(result["candidateChanges"]["deltaXYZ"], [0., 0., 0.])
        self.assertEqual(result["candidateChanges"]["playerSystemYawDeltaDegreesCandidate"], 9.)
        self.assertEqual(result["candidateChanges"]["actorMatrixAngleDeltaDegreesCandidate"], 0.)
        self.assertEqual(result["candidateSettledAfterRelease"]["xyzCandidate"], [2., 3., 4.])
        self.assertEqual(h.mouse.events, [])  # No real mouse backend constructed
        self.assertEqual(h.worker.events,
                         [("reserve", "MOUSE_LEFT"), ("renew", None),
                          ("clear", "MOUSE_LEFT"), ("stop", None)])

    def test_fake_physical_mouse_drag_has_exact_edges_and_restores_cursor(self):
        h = Harness(); self.addCleanup(h.close)
        result = h.run(dry_run=False)
        self.assertTrue(result["action"]["mouseDownAcceptedByOS"])
        self.assertTrue(result["action"]["mouseUpAcceptedByOS"])
        self.assertTrue(result["action"]["cursorRestored"])
        self.assertEqual(h.mouse.cursor, (123, 234))
        self.assertEqual(h.mouse.events, [
            ("cursor", 576, 405), ("button", "MOUSE_LEFT", True),
            ("move", 20, 0), ("move", 20, 0), ("move", 20, 0),
            ("button", "MOUSE_LEFT", False), ("cursor", 123, 234),
        ])
        self.assertEqual(h.reads, 3)

    def test_mouse_up_failure_never_returns_finished_receipt(self):
        h = Harness(); self.addCleanup(h.close)
        h.mouse.fail_up = True
        with self.assertRaisesRegex(CameraProbeRefused, "UP not accepted"):
            h.run(dry_run=False)
        self.assertEqual(h.mouse.cursor, (123, 234))
        self.assertIn(("stop", None), h.worker.events)

    def test_mouse_motion_failure_attempts_up_and_restores_pointer(self):
        h = Harness(); self.addCleanup(h.close)
        h.mouse.fail_move = True
        with self.assertRaisesRegex(CameraProbeRefused, "motion not accepted"):
            h.run(dry_run=False)
        self.assertIn(("button", "MOUSE_LEFT", False), h.mouse.events)
        self.assertEqual(h.mouse.cursor, (123, 234))
        self.assertIn(("stop", None), h.worker.events)

    def test_right_mouse_already_held_refuses_camera_only(self):
        h = Harness(); self.addCleanup(h.close)
        h.mouse.right = True
        with self.assertRaisesRegex(CameraProbeRefused, "mouse button already down"):
            h.run(dry_run=False)
        self.assertEqual(h.mouse.events, [])
        self.assertEqual(h.reads, 1)

    def test_right_mouse_copress_during_motion_forces_release(self):
        h = Harness(); self.addCleanup(h.close)
        class CoPressed(FakeMouse):
            def move_relative(self, dx, dy=0):
                self.right = True
                return super().move_relative(dx, dy)
        h.mouse = CoPressed()
        with self.assertRaisesRegex(CameraProbeRefused, "co-pressed"):
            h.run(dry_run=False)
        self.assertIn(("button", "MOUSE_LEFT", False), h.mouse.events)
        self.assertEqual(h.mouse.cursor, (123, 234))
        self.assertIn(("stop", None), h.worker.events)

    def test_wrong_owner_after_action_refuses_source(self):
        h = Harness(); self.addCleanup(h.close)
        h.after_owner = OWNER + 1
        with self.assertRaisesRegex(CameraProbeRefused, "actor, session"):
            h.run(dry_run=False)
        self.assertEqual(h.mouse.cursor, (123, 234))
        self.assertIn(("stop", None), h.worker.events)

    def test_invalid_inputs_refuse_before_capture(self):
        for wrong in [
            {"horizontal_drag_px": 91}, {"horizontal_drag_px": 0},
            {"horizontal_drag_px": True}, {"cursor_x_fraction": .05},
            {"cursor_y_fraction": .9}, {"hold_ms": 200},
            {"hold_ms": True}, {"expected_owner_key": 0},
            {"dry_run": False, "scene_image_sha256": None},
        ]:
            h = Harness(); self.addCleanup(h.close)
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                h.run(**wrong)
            self.assertEqual(h.reads, 0)

    def test_cli_defaults_to_dryrun_and_forwards_physical_flag(self):
        h = Harness(); self.addCleanup(h.close)
        with tempfile.TemporaryDirectory() as folder:
            base = [
                "probe-camera-orbit", "--pid", "777",
                "--start-ticks", str(h.pin.start_utc_ticks),
                "--exe-path", PATH, "--sha256", SHA,
                "--hwnd", str(h.pin.hwnd), "--host", "LEGION",
                "--owner-key", str(OWNER), "--drag-px", "60",
                "--hold-ms", "100", "--cursor-x-fraction", ".36",
                "--cursor-y-fraction", ".45",
                "--scene-image-sha256", "b" * 64,
                "--audit", str(Path(folder) / "child.jsonl"),
                "--out", str(Path(folder) / "dry.json"),
            ]
            with patch("rift_taxi.cli.run_camera_orbit_probe",
                       return_value=h.run()) as probe:
                self.assertEqual(main(base), 0)
                self.assertTrue(probe.call_args.kwargs["dry_run"])
            physical = base.copy()
            physical[-1] = str(Path(folder) / "real.json")
            physical.append("--execute-physical")
            with patch("rift_taxi.cli.run_camera_orbit_probe",
                       return_value=h.run()) as probe:
                self.assertEqual(main(physical), 0)
                self.assertFalse(probe.call_args.kwargs["dry_run"])

    @unittest.skipUnless(sys.platform == "win32", "requires Windows child process")
    def test_external_release_child_simulates_mouse_up_dry_run(self):
        h = Harness(); self.addCleanup(h.close)
        with ExternalReleaseSupervisor.start_turn_probe(
            h.pin, dry_run=True, ttl_s=.45, audit_path=h.audit
        ) as worker:
            worker.reserve("MOUSE_LEFT")
            self.assertTrue(worker.stop()["stopped"])
        events = [json.loads(s) for s in Path(h.audit).read_text().splitlines()]
        self.assertIn("MOUSE_LEFT", [
            event.get("key") for event in events
            if event.get("event") == "simulated-key-up"
        ])


if __name__ == "__main__":
    unittest.main()
