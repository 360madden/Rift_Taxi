"""Integrated offline tests: independent release child + inert Win32 sender.

A fabricated *test-only* qualified pose is used exclusively with dry_run=True
and a fake SendInput backend. Never touch the running RIFT client.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
import unittest

from rift_taxi.control import ControlRefused, HeldInputController, LivePose, SessionBinding
from rift_taxi.release_supervisor import ExternalReleaseSupervisor
from rift_taxi.supervised_input import SupervisedKeyBackend
from rift_taxi.win32_identity import DesktopCandidate, ProcessInfo
from rift_taxi.win32_input import WindowsScanKeyBackend

EXE = r"C:\Fake\RIFT\rift_x64.exe"
SHA = "a" * 64


class FakeProbe:
    def __init__(self, s):
        self.session = s
        self.foreground = True

    def host(self):
        return self.session.host

    def process(self, pid):
        return ProcessInfo(pid, self.session.start_ticks, EXE)

    def window_ready(self, hwnd, pid):
        return (self.foreground and hwnd == self.session.window_handle
                and pid == self.session.process_id)

    def foreground_root(self):
        return self.session.window_handle if self.foreground else 0


class InertSender:
    def __init__(self):
        self.events = []
        self.refuse = set()
        self.down_delay_s = 0.0

    def send(self, key, down):
        if down and self.down_delay_s:
            time.sleep(self.down_delay_s)
        self.events.append((key, down))
        return (key, down) not in self.refuse


class SupervisedIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "release-audit.jsonl"
        self.session = SessionBinding(
            host="LEGION", process_id=984_321_567, start_ticks=639_310_000_000_000_000,
            executable_sha256=SHA, window_handle=765432,
            actor_id="SYNTHETIC-ONLY", zone_id="SYNTHETIC-ZONE",
        )
        self.probe = FakeProbe(self.session)
        self.sender = InertSender()

    def pose(self, sequence):
        return LivePose(
            self.session, sequence, time.monotonic(), (1., 2., 3.),
            90., True, True,
        )

    def backend(self):
        def admit(pid, **_):
            return DesktopCandidate(
                "LEGION", pid, self.session.start_ticks, EXE, SHA,
                self.session.window_handle, True, time.monotonic(),
            )
        b = WindowsScanKeyBackend(
            self.session, EXE, probe=self.probe, sender=self.sender,
            admit=admit, clock=time.monotonic,
        )
        b.arm(self.pose(1))
        return b

    def spawn(self, ttl_s=.5):
        return ExternalReleaseSupervisor.start(
            self.pose(1), EXE, dry_run=True, ttl_s=ttl_s,
            audit_path=str(self.path), ack_timeout_s=4,
        )

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows child test")
    def test_same_key_held_across_repeated_pose_updates_renews_child_lease(self):
        b = self.backend()
        with self.spawn(ttl_s=.4) as external:
            combined = SupervisedKeyBackend(b, external)
            with HeldInputController(
                self.session, combined, max_pose_age_s=.35, max_hold_s=.5,
            ) as gate:
                gate.apply(("W",), self.pose(1))
                time.sleep(.17)
                gate.apply(("W",), self.pose(2))  # no key edge, renew child lease
                time.sleep(.15)
                gate.apply(("W", "D"), self.pose(3))
                gate.apply(("W",), self.pose(4))
                gate.stop("synthetic")
                self.assertFalse(gate.status.game_response_verified)
                self.assertEqual(gate.status.potentially_held_keys, ())
                self.assertFalse(gate.status.backend_release_fault_observed)
        self.assertEqual(self.sender.events, [
            ("W", True), ("D", True), ("D", False), ("W", False)
        ])
        audit = [json.loads(line) for line in self.path.read_text().splitlines()]
        self.assertNotIn("native-key-up-attempt", [row["event"] for row in audit])
        self.assertNotIn("simulated-key-up", [row["event"] for row in audit])
        self.assertEqual(sum(row["event"] == "ready" for row in audit), 1)

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows child test")
    def test_expired_child_refuses_more_down_and_gate_latches_stop(self):
        b = self.backend()
        with self.spawn(ttl_s=.2) as external:
            combined = SupervisedKeyBackend(b, external)
            with HeldInputController(
                self.session, combined, max_pose_age_s=.40, max_hold_s=.5,
            ) as gate:
                gate.apply(("W",), self.pose(1))
                time.sleep(.28)  # independent helper expires
                with self.assertRaises(ControlRefused):
                    gate.apply(("W", "A"), self.pose(2))
                self.assertTrue(gate.status.stop_latched)
                self.assertNotIn(("A", True), self.sender.events)
        audit = [json.loads(line) for line in self.path.read_text().splitlines()]
        self.assertIn("simulated-key-up", [row["event"] for row in audit])
        self.assertIn("lease-expired", [row.get("reason") for row in audit])

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows child test")
    def test_failed_inert_key_down_remains_reserved_until_release_or_ttl(self):
        self.sender.refuse.add(("W", True))
        b = self.backend()
        with self.spawn(ttl_s=.5) as external:
            combined = SupervisedKeyBackend(b, external)
            with HeldInputController(self.session, combined) as gate:
                with self.assertRaisesRegex(ControlRefused, "backend-press-rejected"):
                    gate.apply(("W",), self.pose(1))
                self.assertTrue(gate.status.stop_latched)
        self.assertEqual(self.sender.events, [("W", True), ("W", False)])
        log = [json.loads(line) for line in self.path.read_text().splitlines()]
        commands = [row for row in log if row["event"] == "command"]
        self.assertEqual(commands[1]["action"], "reserve")
        self.assertEqual(commands[2]["action"], "clear")

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows child test")
    def test_late_key_down_after_child_expiry_gets_compensating_up(self):
        # A slow parent OS insertion can finish AFTER the child expires and
        # sends its dry-run release. The parent MUST then try local key-up.
        self.sender.down_delay_s = .34
        b = self.backend()
        with self.spawn(ttl_s=.20) as external:
            combined = SupervisedKeyBackend(b, external)
            with HeldInputController(self.session, combined, max_hold_s=.5,
                                     max_pose_age_s=.40) as gate:
                with self.assertRaises(ControlRefused):
                    gate.apply(("W",), self.pose(1))
                self.assertTrue(gate.status.stop_latched)
                self.assertFalse(gate.status.game_response_verified)
        self.assertEqual(self.sender.events, [("W", True), ("W", False)])
        audit = [json.loads(line) for line in self.path.read_text().splitlines()]
        self.assertIn("simulated-key-up", [row["event"] for row in audit])
        self.assertNotIn("native-key-up-attempt", [row["event"] for row in audit])

    def test_cannot_use_composer_without_armed_backend(self):
        b = self.backend()
        b.disarm()
        with self.assertRaisesRegex(ControlRefused, "armed"):
            SupervisedKeyBackend(b, None)


if __name__ == "__main__":
    unittest.main()
