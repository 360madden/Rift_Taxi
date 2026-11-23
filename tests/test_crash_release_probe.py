"""Inert crash-release supervision tests; no real RIFT key insertion."""
from __future__ import annotations

import argparse
import hashlib
import json
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

    def _run_mock(self, *, child_up=True, write_marker=True):
        def popen(cmd, **kwargs):
            return FakeParent(cmd, accepted=child_up, write_marker=write_marker)
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


if __name__ == "__main__":
    unittest.main()
