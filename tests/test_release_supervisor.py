"""Deterministic and true child-process release-only tests.

Every spawned worker uses dry_run=True. Tests never call SendInput or
touch RIFT's process, focus, memory, or keyboard state.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from rift_taxi.control import LivePose, SessionBinding
from rift_taxi.release_supervisor import (
    ExternalReleaseSupervisor, ReleaseLeasePin, ReleaseState,
    SupervisorUnavailable, _TaxiSessionMutex,
)


class FakeClock:
    def __init__(self):
        self.now = 25.0

    def __call__(self):
        return self.now


class StateTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.events = []
        self.accepted = True
        self.state = ReleaseState(
            ttl_s=.30, clock=self.clock, release=self._release
        )

    def _release(self, key):
        self.events.append(key)
        return self.accepted

    def test_reserve_clear_no_release(self):
        self.assertEqual(self.state.command("reserve", "W")["possibleHeld"], ["W"])
        self.assertEqual(self.state.command("clear", "W")["possibleHeld"], [])
        self.clock.now += 3
        self.assertFalse(self.state.expire())
        self.assertEqual(self.events, [])

    def test_reserve_then_expiry_releases_in_order_and_latches_stop(self):
        self.state.command("reserve", "W")
        self.state.command("reserve", "D")
        self.state.command("reserve", "A")
        self.clock.now += .301
        self.assertTrue(self.state.expire())
        self.assertEqual(self.events, ["A", "D", "W"])
        self.assertEqual(self.state.reason, "lease-expired")
        self.assertEqual(self.state.status()["possibleHeld"], [])
        self.assertFalse(self.state.status()["gameResponseVerified"])
        with self.assertRaisesRegex(SupervisorUnavailable, "STOP latched"):
            self.state.command("reserve", "W")

    def test_renew_advances_lease_deadline(self):
        self.state.command("reserve", "W")
        self.clock.now += .2
        self.state.command("renew")
        self.clock.now += .2
        self.assertFalse(self.state.expire())
        self.assertEqual(self.events, [])
        self.clock.now += .11
        self.assertTrue(self.state.expire())
        self.assertEqual(self.events, ["W"])

    def test_invalid_key_protocol_latches_stop_and_releases(self):
        self.state.command("reserve", "D")
        with self.assertRaisesRegex(SupervisorUnavailable, "duplicate"):
            self.state.command("reserve", "D")
        self.assertEqual(self.state.reason, "invalid-or-duplicate-reserve")
        self.assertEqual(self.events, ["D"])

    def test_failed_release_retains_uncertainty_without_false_game_claim(self):
        self.state.command("reserve", "W")
        self.accepted = False
        self.state.stop("explicit-stop")
        self.assertEqual(self.state.status()["possibleHeld"], ["W"])
        self.assertFalse(self.state.status()["releaseAttempts"][0]["releaseHandlerAccepted"])
        self.accepted = True
        self.state.stop("explicit-stop")
        self.assertEqual(self.state.status()["possibleHeld"], [])
        self.assertEqual(self.events, ["W", "W"])
        self.assertFalse(self.state.status()["gameResponseVerified"])

    def test_partial_release_retries_only_unresolved_keys(self):
        self.state.command("reserve", "W")
        self.state.command("reserve", "D")
        def partial(key):
            self.events.append(key)
            return key != "D"
        self.state.release = partial
        first = self.state.stop("fault")
        self.assertEqual(first["possibleHeld"], ["D"])
        self.assertEqual(self.events, ["D", "W"])
        self.state.release = self._release
        second = self.state.stop("retry")
        self.assertEqual(second["possibleHeld"], [])
        self.assertEqual(second["reason"], "fault")
        self.assertEqual(self.events, ["D", "W", "D"])
        self.assertFalse(second["gameResponseVerified"])

    def test_bad_operations_and_parameters_rejected(self):
        for ttl in (-1, 0, 5, float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                ReleaseState(ttl_s=ttl, release=lambda _: True)
        with self.assertRaisesRegex(SupervisorUnavailable, "invalid"):
            self.state.command("reserve", "S")
        self.assertTrue(self.state.stopped)


class ChannelTests(unittest.TestCase):
    """Inert transport fixtures; no game or native input access."""

    class Process:
        def __init__(self):
            self.running = True
            self.joined = False

        def is_alive(self):
            return self.running

        def join(self, timeout):
            self.joined = True

    class Pipe:
        def __init__(self):
            self.sent = []
            self.closed = False
            self.ready = True
            self.reply = None
            self.receive_error = None
            self.receive_count = 0

        def send(self, message):
            self.sent.append(message)

        def poll(self, timeout):
            return self.ready

        def recv(self):
            self.receive_count += 1
            if self.receive_error:
                raise self.receive_error
            return self.reply

        def close(self):
            self.closed = True

    def setUp(self):
        self.process = self.Process()
        self.pipe = self.Pipe()
        pin = ReleaseLeasePin("LEGION", 777, 12345, 888,
                              r"C:\Fake\rift_x64.exe", "a" * 64)
        self.worker = ExternalReleaseSupervisor(
            self.process, self.pipe, pin, True,
        )
        self.addCleanup(self.worker.close)

    def status(self, *, stopped=False, held=None, deadline=None, attempts=None):
        return {
            "ok": True, "status": {
                "stopped": stopped, "reason": "explicit-stop" if stopped else None,
                "possibleHeld": [] if held is None else held,
                "deadlineMonotonicSeconds": deadline,
                "releaseAttempts": [] if attempts is None else attempts,
                "gameResponseVerified": False,
            }
        }

    def test_timed_out_channel_never_consumes_late_reply(self):
        self.pipe.ready = False
        with self.assertRaisesRegex(SupervisorUnavailable, "timed out"):
            self.worker.reserve("W")
        self.assertTrue(self.pipe.closed)
        self.assertFalse(self.worker.alive)
        self.pipe.ready = True
        self.pipe.reply = self.status(held=["W"], deadline=100.)
        with self.assertRaisesRegex(SupervisorUnavailable, "not running"):
            self.worker.renew()
        self.assertEqual(self.pipe.sent, [{"action": "reserve", "key": "W"}])
        self.assertEqual(self.pipe.receive_count, 0)

    def test_missing_status_poisoned_instead_of_keyerror(self):
        self.pipe.reply = {"ok": True}
        with self.assertRaisesRegex(SupervisorUnavailable, "missing release status"):
            self.worker.reserve("A")
        self.assertFalse(self.worker.alive)
        self.assertTrue(self.pipe.closed)

    def test_invalid_status_fields_refused(self):
        malformed = [
            {"possibleHeld": "W"},
            {"possibleHeld": ["W", "W"], "deadlineMonotonicSeconds": 100.},
            {"possibleHeld": ["unknown"], "deadlineMonotonicSeconds": 100.},
            {"possibleHeld": [[]]},
            {"stopped": 0},
            {"gameResponseVerified": True},
            {"releaseAttempts": [{"key": "W", "releaseHandlerAccepted": 1}]},
            {"deadlineMonotonicSeconds": float("nan")},
            {"possibleHeld": ["W"]},
        ]
        for fields in malformed:
            with self.subTest(fields=fields):
                reply = self.status()["status"]
                reply.update(fields)
                with self.assertRaisesRegex(SupervisorUnavailable, "malformed"):
                    self.worker._validate_status(reply)

    def test_stop_ack_preserves_partial_release_uncertainty(self):
        self.pipe.reply = self.status(
            stopped=True, held=["D"],
            attempts=[
                {"key": "D", "releaseHandlerAccepted": False},
                {"key": "W", "releaseHandlerAccepted": True},
            ],
        )
        reply = self.worker.stop()
        self.assertTrue(reply["stopped"])
        self.assertEqual(reply["possibleHeld"], ["D"])
        self.assertFalse(reply["gameResponseVerified"])

    def test_stop_without_latched_ack_is_refused(self):
        self.pipe.reply = self.status()
        with self.assertRaisesRegex(SupervisorUnavailable, "not latched"):
            self.worker.stop()
        self.assertFalse(self.worker.alive)

    def test_eof_and_worker_disappearance_close_channel(self):
        self.pipe.receive_error = EOFError()
        with self.assertRaisesRegex(SupervisorUnavailable, "channel unavailable"):
            self.worker.reserve("D")
        self.assertFalse(self.worker.alive)
        self.assertTrue(self.pipe.closed)
        self.process.running = False
        with self.assertRaisesRegex(SupervisorUnavailable, "not running"):
            self.worker.clear("D")
        self.assertEqual(len(self.pipe.sent), 1)

    def test_worker_refusal_prevents_further_commands(self):
        self.pipe.reply = {"ok": False, "error": "STOP latched"}
        with self.assertRaisesRegex(SupervisorUnavailable, "refused"):
            self.worker.reserve("W")
        with self.assertRaisesRegex(SupervisorUnavailable, "not running"):
            self.worker.stop()
        self.assertEqual(len(self.pipe.sent), 1)

    def test_dead_worker_never_receives_new_request(self):
        self.process.running = False
        with self.assertRaisesRegex(SupervisorUnavailable, "not running"):
            self.worker.reserve("W")
        self.assertEqual(self.pipe.sent, [])
        self.assertTrue(self.pipe.closed)


def _fake_qualified_pose() -> LivePose:
    binding = SessionBinding(
        host="LEGION", process_id=123_456_789, start_ticks=639_310_000_000_000_000,
        executable_sha256="a" * 64, window_handle=456_789,
        actor_id="FAKE-TEST-ONLY", zone_id="FAKE-ZONE",
    )
    return LivePose(binding, 1, time.monotonic(), (1., 2., 3.), 0., True, True)


class ChildProcessTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.pose = _fake_qualified_pose()
        self.path = r"C:\Fake\rift_x64.exe"

    def events(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]

    def start(self, logname: str, *, ttl_s: float = .3):
        return ExternalReleaseSupervisor.start(
            self.pose, self.path, ttl_s=ttl_s,
            dry_run=True, ack_timeout_s=4.0,
            audit_path=str(self.root / logname),
        )

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows child process only")
    def test_worker_is_an_actual_other_process_and_expiry_runs_without_heartbeat(self):
        worker = self.start("expired.jsonl", ttl_s=.20)
        try:
            self.assertNotEqual(worker._process.pid, __import__("os").getpid())
            self.assertTrue(worker._process.is_alive())
            reserved = worker.reserve("W")
            self.assertEqual(reserved["possibleHeld"], ["W"])
            worker._process.join(timeout=3)
            self.assertFalse(worker._process.is_alive())
        finally:
            worker.close()
        events = self.events(self.root / "expired.jsonl")
        self.assertIn("simulated-key-up", [r["event"] for r in events])
        self.assertNotIn("native-key-up-attempt", [r["event"] for r in events])
        stop = [r for r in events if r["event"] == "stop"][-1]
        self.assertEqual(stop["reason"], "lease-expired")
        self.assertFalse(stop["gameResponseVerified"])

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows child process only")
    def test_connection_eof_causes_worker_to_release_without_parent_command(self):
        worker = self.start("disconnected.jsonl", ttl_s=1.)
        worker.reserve("D")
        worker._conn.close()  # simulate unexpected transport disappearance
        worker._closed = True  # avoid sending a STOP message during cleanup
        worker._process.join(timeout=3)
        self.assertFalse(worker._process.is_alive())
        log = self.events(self.root / "disconnected.jsonl")
        self.assertIn("simulated-key-up", [r["event"] for r in log])
        final = [r for r in log if r["event"] == "stop"][-1]
        self.assertEqual(final["reason"], "parent-disconnected")
        self.assertEqual(final["releaseAttempts"][0]["key"], "D")

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows child process only")
    def test_stop_and_clear_semantics_have_no_unexpected_fake_keyups(self):
        with self.start("clear.jsonl", ttl_s=.7) as worker:
            worker.reserve("W")
            worker.clear("W")
            self.assertEqual(worker.stop()["possibleHeld"], [])
        self.assertNotIn("simulated-key-up", [
            e["event"] for e in self.events(self.root / "clear.jsonl")
        ])
        with self.start("stop.jsonl", ttl_s=.7) as worker:
            worker.reserve("A")
            reply = worker.stop()
            self.assertTrue(reply["stopped"])
            self.assertFalse(reply["gameResponseVerified"])
        self.assertIn("simulated-key-up", [
            e["event"] for e in self.events(self.root / "stop.jsonl")
        ])

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows child process only")
    def test_exclusive_worker_mutex_refuses_second_same_epoch(self):
        with self.start("owner.jsonl", ttl_s=1.0):
            with self.assertRaisesRegex(SupervisorUnavailable, "already owns"):
                self.start("other.jsonl", ttl_s=.5)
        self.assertFalse((self.root / "other.jsonl").exists())

    @unittest.skipUnless(sys.platform == "win32", "Windows crash test only")
    def test_actual_parent_process_abrupt_exit_triggers_dry_run_child_release(self):
        # This is an actual second Python parent process terminating via
        # os._exit(37). Its spawned child is dry-run only: zero OS key events.
        audit = self.root / "abrupt-parent-exit.jsonl"
        quoted_path = json.dumps(str(audit))
        script = (
            "import os,time\n"
            "from rift_taxi.control import SessionBinding,LivePose\n"
            "from rift_taxi.release_supervisor import ExternalReleaseSupervisor\n"
            "s=SessionBinding('LEGION',123456789,639310000000000000,'a'*64,"
            "456789,'FAKE-TEST-ONLY','FAKE-ZONE')\n"
            "p=LivePose(s,1,time.monotonic(),(1.,2.,3.),0.,True,True)\n"
            f"log={quoted_path}\n"
            "w=ExternalReleaseSupervisor.start(p,r'C:\\Fake\\rift_x64.exe',"
            "dry_run=True,ttl_s=.5,ack_timeout_s=4.0,audit_path=log)\n"
            "w.reserve('W')\n"
            "os._exit(37)\n"
        )
        cmd = subprocess.run(
            [sys.executable, "-B", "-c", script],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=15,
        )
        self.assertEqual(cmd.returncode, 37, cmd.stderr.decode(errors="replace"))
        end = time.monotonic() + 5
        recorded = []
        while time.monotonic() < end:
            if audit.exists():
                try:
                    recorded = self.events(audit)
                except (OSError, json.JSONDecodeError):
                    recorded = []
                if any(row["event"] == "simulated-key-up" for row in recorded):
                    break
            time.sleep(.05)
        self.assertIn("simulated-key-up", [row["event"] for row in recorded])
        self.assertNotIn("native-key-up-attempt", [row["event"] for row in recorded])
        final = [row for row in recorded if row["event"] == "stop"][-1]
        self.assertEqual(final["reason"], "parent-disconnected")
        self.assertFalse(final["gameResponseVerified"])

    def test_unqualified_pose_cannot_start_supervisor(self):
        for bogus in (
            replace(self.pose, actor_yaw_verified=False),
            replace(self.pose, foreground_verified=False),
        ):
            with self.assertRaisesRegex(SupervisorUnavailable, "qualified"):
                ExternalReleaseSupervisor.start(bogus, self.path, dry_run=True)
        with self.assertRaisesRegex(SupervisorUnavailable, "absolute"):
            ExternalReleaseSupervisor.start(self.pose, "rift_x64.exe", dry_run=True)

    def test_existing_audit_file_refused_before_spawning_worker(self):
        output = self.root / "old.jsonl"
        output.write_text("immutable\n", encoding="utf8")
        with self.assertRaisesRegex(SupervisorUnavailable, "new"):
            ExternalReleaseSupervisor.start(
                self.pose, self.path, dry_run=True, audit_path=str(output)
            )
        self.assertEqual(output.read_text(), "immutable\n")


if __name__ == "__main__":
    unittest.main()
