"""Inert crash-release supervision tests; no real RIFT key insertion."""
from __future__ import annotations

import argparse
import hashlib
import json
from itertools import count
import os
import sys
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from rift_taxi import crash_release_probe as cr


EXE = r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe"
SHA = "a" * 64


def args_in(folder: Path, *, execute: bool = True) -> argparse.Namespace:
    scene = folder / "review.jpg"
    scene.write_bytes(b"\xff\xd8" + b"x" * 1500)
    return argparse.Namespace(
        host="LEGION", pid=777, start_ticks=639310421805307472,
        hwnd=12345, exe_path=EXE, sha256=SHA, owner_key=1999,
        execute_physical=execute, precrash_hold_ms=0, scene=str(scene),
        scene_sha256=hashlib.sha256(scene.read_bytes()).hexdigest(),
        out=str(folder / "final.json"), audit=str(folder / "release.jsonl"),
        down_marker=str(folder / "down.json"),
        guard=str(folder / "watchdog.json"),
    )


def audit_events(*, accepted: bool, pid: int = 777) -> list[dict]:
    def event(kind, t, **kwargs):
        return {"event": kind, "monotonicSeconds": t, **kwargs}
    reserve_status = {"possibleHeld": ["A"], "stopped": False}
    return [
        event("ready", 100., pid=pid, dryRun=False),
        event("command", 100.01, action="reserve", key="A", status=reserve_status),
        event("command", 100.02, action="renew", key=None, status=reserve_status),
        event("native-key-up-attempt", 100.04, key="A", acceptedByOS=accepted),
        event("stop", 100.06, stopped=True,
              reason="parent-disconnected", possibleHeld=[] if accepted else ["A"]),
    ]


class FakeKeys:
    def snapshot(self):
        return {"W": False, "A": False, "D": False}


class FakeSend:
    sends = []
    def send(self, key: str, is_down: bool):
        self.sends.append((key, is_down))
        return True


class FakeParent:
    def __init__(self, cmd, *, accepted=True, write_marker=True):
        self.returncode = 37
        def get(arg):
            return Path(cmd[cmd.index(arg) + 1])
        audit = get("--audit")
        audit.write_text("\n".join(json.dumps(e) for e in audit_events(accepted=accepted))+"\n")
        if write_marker:
            get("--down-marker").write_text(json.dumps({
                "schema": "taxi.m1-parent-crash-A-down/1",
                "downAcceptedByOS": True,
                "parentIntentionallyOmittedKeyUp": True,
                "externalReleaseProcessReserved": True,
                "requestedPrecrashHoldMilliseconds": int(cmd[cmd.index("--precrash-hold-ms")+1]),
                "targetPid": 777,
                "startUtcTicks": 639310421805307472,
                "atMonotonicSeconds": 100.03,
                "ownerKeyDecimal": "1999"
            }))
    def poll(self):
        return self.returncode


class CrashReleaseTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.args = args_in(self.root)
        FakeSend.sends = []

    @unittest.skipUnless(sys.platform == "win32", "Win32 launcher process metadata")
    def test_win32_independent_launcher_liveness_check(self):
        self.assertTrue(cr._launcher_alive(os.getpid()))
        self.assertFalse(cr._launcher_alive(999_999_999))
        self.assertFalse(cr._launcher_alive(True))
        self.assertFalse(cr._launcher_alive(0))

    def test_precrash_A_hold_must_be_bounded_before_any_spawn(self):
        for value in (-1, 141, 999, True, 10.5):
            self.args.precrash_hold_ms = value
            with self.subTest(value=value), patch.object(cr.sys, "platform", "win32"):
                with self.assertRaisesRegex(cr.CrashReleaseRefused, "bounded pre-crash"):
                    cr.run_physical_crash_probe(self.args)
        self.assertFalse(Path(self.args.audit).exists())

    def test_scene_hash_tamper_and_staleness(self):
        result = cr._verify_scene(self.args.scene, self.args.scene_sha256)
        self.assertEqual(result["sha256"], self.args.scene_sha256)
        with self.assertRaisesRegex(cr.CrashReleaseRefused, "SHA-256 mismatch"):
            cr._verify_scene(self.args.scene, "0"*64)
        old = time.time() - 500
        import os
        os.utime(self.args.scene, (old, old))
        with self.assertRaisesRegex(cr.CrashReleaseRefused, "stale"):
            cr._verify_scene(self.args.scene, self.args.scene_sha256)

    def test_requires_current_pin_and_explicit_physical_choice(self):
        self.args.execute_physical = False
        with patch.object(cr.sys, "platform", "win32"):
            with self.assertRaisesRegex(cr.CrashReleaseRefused, "execute-physical"):
                cr.run_physical_crash_probe(self.args)
        self.assertFalse(Path(self.args.audit).exists())
        self.args.execute_physical = True
        self.args.owner_key = 0
        with patch.object(cr.sys, "platform", "win32"):
            with self.assertRaisesRegex(cr.CrashReleaseRefused, "owner"):
                cr.run_physical_crash_probe(self.args)

    def test_audit_report_requires_native_child_OS_UP_not_ledger_only(self):
        p = Path(self.args.audit)
        p.write_text("\n".join(json.dumps(e) for e in audit_events(accepted=True))+"\n")
        pin = cr._pin(self.args)
        summary = cr._audit_summary(p, pin)
        self.assertTrue(summary["reserveAckObserved"])
        self.assertTrue(summary["renewAckObserved"])
        self.assertTrue(summary["nativeChildUpAcceptedByOS"])
        self.assertTrue(summary["childStopObserved"])
        self.assertEqual(summary["childStopReason"], "parent-disconnected")
        events = audit_events(accepted=False)
        p.write_text("\n".join(json.dumps(e) for e in events)+"\n")
        self.assertFalse(cr._audit_summary(p, pin)["nativeChildUpAcceptedByOS"])
        events[0]["pid"] = 789
        p.write_text("\n".join(json.dumps(e) for e in events)+"\n")
        self.assertFalse(cr._audit_summary(p, pin)["auditReadable"])

    def _run_mock(self, *, child_up=True, write_marker=True, parent_exit=37):
        # FakeParent writes evidence in a synthetic monotonic epoch around
        # 100 seconds. A fresh hosted Linux runner can have a real uptime
        # below that value, so use a deterministic later clock in the same
        # fixture epoch. Advance it on every read to keep deadline loops
        # bounded even when sleep is mocked out.
        clock = count(start=50000)
        def monotonic():
            return next(clock) / 100.
        def popen(cmd, **kwargs):
            child = FakeParent(cmd, accepted=child_up, write_marker=write_marker)
            child.returncode = parent_exit
            return child
        capture = {
            "ownerKeyDecimal": "1999",
            "xyzCandidate": [100., 2., 300.],
            "actorMatrixPlanarAngleDegreesCandidate": 15.,
            "playerSystemBearingDegreesCandidate": -15.,
            "observedMonotonicSeconds": 500.,
            "actorHeadingVerified": False,
            "passivePositionFreshnessVerified": False,
        }
        with (patch.object(cr.sys, "platform", "win32"),
              patch.object(cr, "_identity"),
              patch.object(cr, "_capture", return_value=capture),
              patch.object(cr, "Win32KeySnapshot", return_value=FakeKeys()),
              patch.object(cr, "Win32ScanSender", return_value=FakeSend()),
              patch.object(cr.subprocess, "Popen", side_effect=popen),
              patch.object(cr.time, "monotonic", side_effect=monotonic),
              patch.object(cr.time, "sleep", return_value=None)):
            return cr.run_physical_crash_probe(self.args)

    def test_valid_short_precrash_hold_keeps_release_proof_not_game_claim(self):
        self.args.precrash_hold_ms = 100
        result = self._run_mock()
        self.assertEqual(result["parent"]["requestedPrecrashHoldMilliseconds"], 100)
        self.assertTrue(result["qualification"]["actualParentCrashAndChildOSUpObserved"])
        self.assertFalse(result["qualification"]["gameConsumedReleaseVerified"])

    def test_real_release_audit_in_mock_does_not_request_backup(self):
        result = self._run_mock()
        self.assertEqual(result["parent"]["crashWorkerExitCode"], 37)
        self.assertFalse(result["parent"]["launcherBackupKeyUpAttempted"])
        self.assertEqual(FakeSend.sends, [])
        self.assertTrue(result["qualification"]["actualParentCrashAndChildOSUpObserved"])
        self.assertTrue(result["qualification"]["durableDownMarkerAndChildReleaseOrderVerified"])
        self.assertFalse(result["qualification"]["gameConsumedReleaseVerified"])
        self.assertFalse(result["qualification"]["M1Complete"])
        self.assertTrue(Path(self.args.out).is_file())

    def test_marker_and_child_up_without_exit_37_do_not_claim_crash(self):
        # A marker can survive a later ordinary sender/clock/I/O failure.
        # Native child UP then proves release only, never intentional crash.
        result = self._run_mock(parent_exit=2)
        self.assertIsNotNone(result["parent"]["AKeyDownMarker"])
        self.assertTrue(result["child"]["nativeChildUpAcceptedByOS"])
        self.assertFalse(result["qualification"]["actualParentCrashAndChildOSUpObserved"])
        self.assertFalse(result["parent"]["workerProcessExitedAsExpected"])
        self.assertFalse(result["qualification"]["M1Complete"])

    def test_missing_child_OS_up_requires_immediate_backup(self):
        result = self._run_mock(child_up=False)
        self.assertTrue(result["parent"]["launcherBackupKeyUpAttempted"])
        self.assertEqual(FakeSend.sends, [("A", False)])
        self.assertFalse(result["qualification"]["actualParentCrashAndChildOSUpObserved"])
        self.assertTrue(result["qualification"]["osKeysUpAfter"])
        self.assertFalse(result["qualification"]["gameConsumedReleaseVerified"])

    def test_bad_child_or_release_audit_never_claims_game_consumption(self):
        p = Path(self.args.audit)
        p.write_text("partial\n")
        summary = cr._audit_summary(p, cr._pin(self.args))
        self.assertFalse(summary["nativeChildUpAcceptedByOS"])
        self.assertFalse(summary["auditReadable"])

    def test_new_paths_are_not_silently_overwritten(self):
        Path(self.args.out).write_text("preserve")
        with patch.object(cr.sys, "platform", "win32"):
            with self.assertRaisesRegex(cr.CrashReleaseRefused, "path must be new"):
                cr.run_physical_crash_probe(self.args)
        self.assertEqual(Path(self.args.out).read_text(), "preserve")

    def test_wrong_process_or_focus_refuses_before_child_spawn(self):
        with (patch.object(cr.sys, "platform", "win32"),
              patch.object(cr, "_identity", side_effect=cr.TurnProbeRefused("wrong foreground")),
              patch.object(cr.subprocess, "Popen") as pop):
            with self.assertRaisesRegex(cr.TurnProbeRefused, "wrong foreground"):
                cr.run_physical_crash_probe(self.args)
            pop.assert_not_called()



class _InterceptedCrash(BaseException):
    """Inert tests intercept the exit boundary; this is not a real crash."""


class _CrashChildHarness:
    """Exercise the actual child function with no native input or process reader.

    All Windows admission, keyboard, sender and release-worker objects are
    replaced. The pure ReleaseState keeps genuine lease-expiry semantics.
    Optional event files let a separate fake-input subprocess prove that real
    os._exit(37) skips Python cleanup; no game or release child is involved.
    """

    def __init__(self, folder: Path, *, persist_events=False):
        from rift_taxi.release_supervisor import ReleaseState
        self.args = args_in(folder)
        self.args.precrash_hold_ms = 100
        self.args.guard_token = "inert-test-token"
        self.args.launcher_pid = 123
        Path(self.args.guard).write_text(json.dumps({
            "token": self.args.guard_token, "launcherPid": 123,
            "targetPid": self.args.pid,
        }))
        self.now = 100.
        self.events = []
        self.identities = 0
        self.clock_fault = None
        self.on_identity = None
        self.on_renew = None
        self.on_send = None
        self.on_fsync = None
        self.on_sleep = None
        self.exit_callback = None
        self.event_path = folder / "inert-events.jsonl" if persist_events else None
        harness = self

        class Worker:
            """Inert context with the production pure state's .55-second TTL."""

            alive = True
            dry_run = False

            def __init__(self):
                self.state = ReleaseState(
                    ttl_s=.55, clock=harness.clock,
                    release=lambda key: harness.record("child-up", key) is None,
                )

            def __enter__(self):
                return self

            def __exit__(self, *_):
                harness.record("context-exit")
                if self.alive:
                    self.stop()
                self.alive = False

            def reserve(self, key):
                harness.record("reserve", key)
                return self.state.command("reserve", key)

            def renew(self):
                harness.record("renew")
                reply = self.state.command("renew")
                return harness.on_renew(reply) if harness.on_renew else reply

            def clear(self, key):
                harness.record("clear", key)
                return self.state.command("clear", key)

            def stop(self):
                harness.record("stop")
                return self.state.stop("inert-test-stop")

        self.worker = Worker()

    def record(self, *event):
        self.events.append(event)
        if self.event_path:
            with self.event_path.open("a", encoding="utf8") as stream:
                stream.write(json.dumps(event) + "\n")

    def clock(self):
        if self.clock_fault == "raises":
            raise RuntimeError("injected clock failure")
        return self.now if self.clock_fault is None else self.clock_fault

    def identity(self, *_):
        self.identities += 1
        if self.on_identity:
            self.on_identity()

    def send(self, key, down):
        self.record("send", key, down)
        if self.on_send:
            return self.on_send(down)
        return True

    def fsync(self, _):
        if self.on_fsync:
            self.on_fsync()

    def sleep(self, delay):
        self.record("sleep", delay)
        if self.on_sleep:
            self.on_sleep(delay)
        else:
            self.now += delay

    def exit(self, code):
        # The event is written before invoking the callback. Real os._exit
        # never returns; the regular unit tests deliberately intercept it.
        self.record("exit-attempt", code)
        if self.exit_callback:
            self.exit_callback(code)
        raise _InterceptedCrash()

    def run(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for target, name, kwargs in (
                (cr.sys, "platform", {"new": "win32"}),
                (cr, "_launcher_alive", {"return_value": True}),
                (cr, "_identity", {"side_effect": self.identity}),
                (cr, "_capture", {"return_value": {}}),
                (cr, "Win32KeySnapshot", {"return_value": FakeKeys()}),
                (cr, "Win32ScanSender", {"return_value": self}),
                (cr.ExternalReleaseSupervisor, "start_turn_probe",
                 {"return_value": self.worker}),
                (cr.time, "monotonic", {"side_effect": self.clock}),
                (cr.time, "sleep", {"side_effect": self.sleep}),
                (cr.os, "fsync", {"side_effect": self.fsync}),
                (cr.os, "_exit", {"side_effect": self.exit}),
            ):
                stack.enter_context(patch.object(target, name, **kwargs))
            return cr._child(self.args)

    def attempt(self):
        """Return the actual refusal; intercepting exit alone is never a pass."""
        try:
            self.run()
        except BaseException as error:
            return error
        raise AssertionError("crash child returned normally")


class CrashChildLeaseTests(unittest.TestCase):
    """Regress stale ACKs and failures after uncertain DOWN with inert endpoints."""

    def harness(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return _CrashChildHarness(Path(folder.name))

    def assert_refused_and_released(self, h, *, down_attempted):
        error = h.attempt()
        self.assertNotIsInstance(error, _InterceptedCrash,
                                 "fault reached the intentional crash boundary")
        self.assertFalse(any(e[0] == "exit-attempt" for e in h.events))
        self.assertIn(("stop",), h.events)
        if down_attempted:
            self.assertIn(("send", "A", True), h.events)
            self.assertIn(("send", "A", False), h.events)
            self.assertLess(h.events.index(("send", "A", False)),
                            h.events.index(("stop",)))
        else:
            self.assertNotIn(("send", "A", True), h.events)
        return error

    def test_expiry_during_final_identity_never_sends_late_down(self):
        # Previously reserve/renew preceded the full SHA identity check.
        # The state independently releases before the old code sends DOWN.
        h = self.harness()
        def identity():
            if h.identities == 2:
                h.now += .56
                self.assertTrue(h.worker.state.expire())
                h.worker.alive = False
        h.on_identity = identity
        self.assert_refused_and_released(h, down_attempted=False)
        self.assertIn(("child-up", "A"), h.events)

    def test_bad_or_delayed_renewal_never_sends_down(self):
        import math
        for kind in ("delayed", "nan", "infinite", "bool", "string",
                     "missing", "past", "short", "foreign", "wrong-ttl"):
            with self.subTest(kind=kind):
                h = self.harness()
                def renew(reply):
                    if kind == "delayed":
                        h.now += .56
                    elif kind == "missing":
                        reply.pop("deadlineMonotonicSeconds")
                    else:
                        reply["deadlineMonotonicSeconds"] = {
                            "nan": math.nan, "infinite": math.inf, "bool": True,
                            "string": "100.55", "past": 99., "short": 100.05,
                            "foreign": 1000., "wrong-ttl": 100.58,
                        }[kind]
                    return reply
                h.on_renew = renew
                self.assert_refused_and_released(h, down_attempted=False)

    def test_worker_disappearance_before_or_after_down_refuses_crash(self):
        for stage in ("before", "after"):
            with self.subTest(stage=stage):
                h = self.harness()
                if stage == "before":
                    def renew(reply):
                        h.worker.alive = False
                        return reply
                    h.on_renew = renew
                else:
                    def send(down):
                        if down:
                            h.worker.alive = False
                        return True
                    h.on_send = send
                self.assert_refused_and_released(h, down_attempted=stage == "after")

    def test_late_or_throwing_sender_compensates_without_hold(self):
        for kind in ("late", "raises", "false"):
            with self.subTest(kind=kind):
                h = self.harness()
                def send(down):
                    if down:
                        if kind == "late":
                            h.now += .56
                        elif kind == "raises":
                            raise OSError("DOWN may have reached the OS")
                        else:
                            return False
                    return True
                h.on_send = send
                self.assert_refused_and_released(h, down_attempted=True)
                self.assertFalse(any(e[0] == "sleep" for e in h.events))

    def test_invalid_clock_after_down_cannot_skip_compensation(self):
        import math
        for value in (math.nan, math.inf, True, 99., "raises"):
            with self.subTest(value=value):
                h = self.harness()
                def send(down):
                    if down:
                        h.clock_fault = value
                    return True
                h.on_send = send
                self.assert_refused_and_released(h, down_attempted=True)

    def test_marker_failure_or_slow_flush_compensates_without_hold(self):
        # A durable marker can block or fail after DOWN. It must not allow a
        # further hold or intentional crash on an already expired child lease.
        for kind in ("open", "fsync", "slow"):
            with self.subTest(kind=kind):
                h = self.harness()
                if kind == "open":
                    h.args.down_marker = str(Path(h.args.guard).parent / "missing" / "down.json")
                else:
                    def fsync():
                        if kind == "fsync":
                            raise OSError("injected marker flush failure")
                        h.now += .50  # fewer than 100 ms remain
                    h.on_fsync = fsync
                self.assert_refused_and_released(h, down_attempted=True)
                self.assertFalse(any(e[0] == "sleep" for e in h.events))

    def test_hold_exception_expiry_or_clock_failure_never_intentionally_crashes(self):
        for kind in ("raises", "expired", "clock"):
            with self.subTest(kind=kind):
                h = self.harness()
                def sleep(delay):
                    if kind == "raises":
                        raise RuntimeError("injected interrupted hold")
                    h.now += .56 if kind == "expired" else delay
                    if kind == "clock":
                        h.clock_fault = "raises"
                h.on_sleep = sleep
                self.assert_refused_and_released(h, down_attempted=True)

    def test_failed_compensating_up_does_not_prevent_child_stop(self):
        h = self.harness()
        def send(down):
            if down:
                h.now += .56
                return True
            raise OSError("injected UP failure")
        h.on_send = send
        self.assert_refused_and_released(h, down_attempted=True)
        self.assertIn(("child-up", "A"), h.events)

    def test_normal_path_reaches_exit_with_lease_and_no_early_parent_up(self):
        h = self.harness()
        self.assertIsInstance(h.attempt(), _InterceptedCrash)
        exit_index = h.events.index(("exit-attempt", 37))
        self.assertIn(("send", "A", True), h.events[:exit_index])
        self.assertNotIn(("send", "A", False), h.events[:exit_index])
        marker = json.loads(Path(h.args.down_marker).read_text())
        self.assertTrue(marker["downAcceptedByOS"])
        self.assertIs(marker["intentionalCrashVerified"], False)
        # This unit-test interception does run cleanup afterward. The next
        # subprocess test, not this fake exception, proves abrupt-exit behavior.

    def test_actual_exit_37_with_fake_input_skips_python_cleanup(self):
        import subprocess
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        code = (
            "import os, sys\n"
            "from pathlib import Path\n"
            "from test_crash_release_probe import _CrashChildHarness\n"
            "h = _CrashChildHarness(Path(sys.argv[1]), persist_events=True)\n"
            "h.exit_callback = os._exit\n"
            "h.run()\n"
        )
        # Only this test process dies. All game/Windows input and all native
        # identity/read/release endpoints remain patched to inert fixtures.
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((
            str(Path(__file__).resolve().parent),
            str(Path(__file__).resolve().parents[1]),
        ))
        done = subprocess.run(
            [sys.executable, "-B", "-c", code, folder.name],
            cwd=Path(__file__).resolve().parents[1], env=env,
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(done.returncode, 37, done.stderr)
        events = [json.loads(line) for line in
                  (Path(folder.name) / "inert-events.jsonl").read_text().splitlines()]
        self.assertIn(["send", "A", True], events)
        self.assertIn(["exit-attempt", 37], events)
        self.assertNotIn(["send", "A", False], events)
        self.assertNotIn(["stop"], events)
        self.assertNotIn(["context-exit"], events)
        self.assertTrue((Path(folder.name) / "down.json").is_file())

if __name__ == "__main__":
    unittest.main()
