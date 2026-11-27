"""M1 A-turn-only real parent-crash release experiment, never navigation.

The parent that inserts a single A DOWN deliberately calls os._exit(37),
leaving the separately spawned release child to send A UP on pipe EOF/TTL.
The *launcher* remains alive as an independent guard and issues a backup UP
if the child does not record an accepted native release in time.

Physical mode requires a fresh, locally SHA-verified and independently
reviewed gameplay screenshot, exact process epoch/owner, a visible foreground
RIFT window, new unoccupied evidence paths and explicit --execute-physical.
This is diagnostic-only: no W, no route, no Qualified LivePose.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

from .key_observation import Win32KeySnapshot, validate_key_snapshot
from .native_capture import capture_native_candidate
from .release_supervisor import (
    ExternalReleaseSupervisor, ReleaseLeasePin, SupervisorUnavailable,
)
from .turn_probe import (
    _capture, _identity, _probe_clock, _probe_deadline, TurnProbeRefused,
)
from .win32_identity import inspect_desktop
from .win32_input import Win32ScanSender

_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
_EXIT = 37
_CRASH_LEASE_SECONDS = .55


class CrashReleaseRefused(ValueError):
    """Physical diagnostic could not retain exact and safe admission."""


def _new_path(value: str, *, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise CrashReleaseRefused(f"{label}: evidence path required")
    path = Path(value)
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise CrashReleaseRefused(f"{label}: path must be new with existing parent")
    return path


def _pins(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", required=True)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--start-ticks", required=True, type=int)
    parser.add_argument("--hwnd", required=True, type=lambda x: int(x, 0))
    parser.add_argument("--exe-path", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--owner-key", required=True, type=int)


def _pin(args: argparse.Namespace) -> ReleaseLeasePin:
    pin = ReleaseLeasePin(args.host, args.pid, args.start_ticks,
                          args.hwnd, args.exe_path, args.sha256)
    if (not isinstance(pin.host, str) or not pin.host.strip()
            or type(pin.pid) is not int or pin.pid <= 0
            or type(pin.start_utc_ticks) is not int or pin.start_utc_ticks <= 0
            or type(pin.hwnd) is not int or pin.hwnd <= 0
            or not isinstance(pin.executable_path, str)
            or not ntpath.isabs(pin.executable_path)
            or not isinstance(pin.sha256, str) or not _SHA.fullmatch(pin.sha256)
            or type(args.owner_key) is not int or args.owner_key <= 0):
        raise CrashReleaseRefused("exact physical game pin and owner key required")
    return pin


def _verify_scene(path: str, expected_sha: str, *, max_age_seconds: float = 180.) -> dict:
    if not isinstance(expected_sha, str) or not _SHA.fullmatch(expected_sha):
        raise CrashReleaseRefused("real reviewed screenshot SHA-256 required")
    p = Path(path)
    if (not p.is_file() or p.suffix.lower() not in (".jpg", ".jpeg", ".png")
            or not 1000 <= p.stat().st_size <= 16_000_000):
        raise CrashReleaseRefused("current real JPEG/PNG screenshot required")
    age = time.time() - p.stat().st_mtime
    if not 0 <= age <= max_age_seconds:
        raise CrashReleaseRefused("reviewed screenshot is stale or time-invalid")
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != expected_sha.lower():
        raise CrashReleaseRefused("reviewed screenshot content SHA-256 mismatch")
    return {"name": p.name, "sha256": actual, "ageSeconds": age}


def _audit_summary(path: Path, pin: ReleaseLeasePin) -> dict:
    """Strictly observe file, never fabricate an OS release from a ledger stop."""
    result = {
        "nativeChildUpAttemptObserved": False,
        "nativeChildUpAcceptedByOS": False,
        "childStopObserved": False,
        "releaseAcceptedAtMonotonicSeconds": None,
        "childStopReason": None,
        "auditReadable": False,
        "auditSHA256": None,
        "reserveAckObserved": False,
        "renewAckObserved": False,
    }
    if not path.is_file() or path.stat().st_size > 100_000:
        return result
    raw = path.read_bytes()
    result["auditSHA256"] = hashlib.sha256(raw).hexdigest()
    try:
        events = [json.loads(line) for line in raw.decode("utf8").splitlines()]
    except (UnicodeError, json.JSONDecodeError):
        return result
    if not events or events[0].get("event") != "ready" or (
        events[0].get("pid") != pin.pid or events[0].get("dryRun") is not False
    ):
        return result
    result["auditReadable"] = True
    for event in events[1:]:
        kind = event.get("event")
        if kind == "command" and event.get("action") == "reserve" and event.get("key") == "A":
            status = event.get("status", {})
            result["reserveAckObserved"] = (isinstance(status, dict)
                and status.get("possibleHeld") == ["A"] and status.get("stopped") is False)
        if kind == "command" and event.get("action") == "renew":
            status = event.get("status", {})
            result["renewAckObserved"] = (isinstance(status, dict)
                and status.get("possibleHeld") == ["A"] and status.get("stopped") is False)
        if kind == "native-key-up-attempt" and event.get("key") == "A":
            result["nativeChildUpAttemptObserved"] = True
            if event.get("acceptedByOS") is True:
                result["nativeChildUpAcceptedByOS"] = True
                result["releaseAcceptedAtMonotonicSeconds"] = event.get("monotonicSeconds")
        if kind == "stop" and event.get("stopped") is True:
            result["childStopObserved"] = True
            result["childStopReason"] = event.get("reason")
    return result


def _launcher_alive(pid: int) -> bool:
    """Read-only OS check that the independent backup launcher still exists."""
    if sys.platform != "win32" or type(pid) is not int or pid <= 0:
        return False
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        return (bool(kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)))
                and exit_code.value == 259)
    finally:
        kernel.CloseHandle(handle)


def _crash_deadline(lease: object, now: float, hold_s: float) -> float:
    """Require a same-clock A lease that covers the remaining bounded hold.

    The shared turn helper validates status, numeric time and hold coverage.
    Its normal TTL is .6 s; this older crash diagnostic deliberately retains
    .55 s and therefore applies the stricter upper bound here as well.
    """
    deadline = _probe_deadline(lease, "A", now, hold_s)
    if deadline > now + _CRASH_LEASE_SECONDS:
        raise CrashReleaseRefused("crash release deadline exceeds its .55-second lease")
    return deadline


def _child(args: argparse.Namespace) -> int:
    """Attempt one admitted A pulse, then crash only on the intended success path.

    Ordinary exceptions, expired leases and uncertain sender/marker failures
    compensate with parent UP and child STOP. Only actual os._exit(37) bypasses
    Python cleanup; a DOWN marker alone never proves that this exit occurred.
    All clock/lease comparisons share the release child's monotonic domain.
    """
    pin = _pin(args)
    challenge = json.loads(Path(args.guard).read_text(encoding="utf8"))
    if (challenge.get("token") != args.guard_token
            or challenge.get("launcherPid") != args.launcher_pid
            or challenge.get("targetPid") != pin.pid):
        raise CrashReleaseRefused("missing or invalid live independent watchdog")
    # A stale guard token is not a replacement for an active rescue launcher.
    if sys.platform != "win32" or not _launcher_alive(args.launcher_pid):
        raise CrashReleaseRefused("independent rescue launcher not live")
    if type(args.precrash_hold_ms) is not int or not 0 <= args.precrash_hold_ms <= 140:
        raise CrashReleaseRefused("bounded pre-crash A hold must be 0..140 ms")
    last_clock = _probe_clock(time.monotonic)
    _identity(pin, inspect_desktop)
    if any(validate_key_snapshot(Win32KeySnapshot().snapshot()).values()):
        raise CrashReleaseRefused("W/A/D already down before failure child")
    _capture(pin, args.owner_key, capture_native_candidate)
    sender = Win32ScanSender()
    hold_s = args.precrash_hold_ms / 1000.
    with ExternalReleaseSupervisor.start_turn_probe(
        pin, ttl_s=_CRASH_LEASE_SECONDS, dry_run=False, audit_path=args.audit,
    ) as release:
        down_attempted = False
        try:
            if not release.alive:
                raise CrashReleaseRefused("release child not alive")
            ack = release.reserve("A")
            if (not isinstance(ack, dict) or ack.get("possibleHeld") != ["A"]
                    or ack.get("stopped") is not False):
                raise CrashReleaseRefused("external A key release reservation not confirmed")
            _identity(pin, inspect_desktop)
            if not _launcher_alive(args.launcher_pid):
                raise CrashReleaseRefused("backup launcher died before A DOWN")
            if any(validate_key_snapshot(Win32KeySnapshot().snapshot()).values()):
                raise CrashReleaseRefused("keyboard state changed before DOWN")

            # Full SHA admission can outlast the original reservation. Renew
            # only after those checks, and reject even a valid ACK that arrived
            # after the child deadline. No expired child can be resurrected.
            last_clock = _probe_clock(time.monotonic, last_clock)
            renewed = release.renew()
            down_at = last_clock = _probe_clock(time.monotonic, last_clock)
            _crash_deadline(renewed, down_at, hold_s)
            if not release.alive:
                raise CrashReleaseRefused("release child unavailable before A DOWN")
            down_attempted = True  # SendInput may insert before raising/returning false.
            if sender.send("A", True) is not True:
                raise CrashReleaseRefused("OS A DOWN not accepted")
            last_clock = _probe_clock(time.monotonic, last_clock)
            _crash_deadline(renewed, last_clock, hold_s)
            if not release.alive:
                raise CrashReleaseRefused("release child unavailable after A DOWN")

            marker = {
                "schema": "taxi.m1-parent-crash-A-down/1",
                "pid": os.getpid(), "targetPid": pin.pid,
                "startUtcTicks": pin.start_utc_ticks,
                "ownerKeyDecimal": str(args.owner_key),
                "atMonotonicSeconds": down_at,
                "downAcceptedByOS": True,
                # This is intent at marker time, not proof of a later crash.
                # The launcher still requires actual exit 37 and ordered child
                # UP. Any later ordinary failure takes the compensation path.
                "parentIntentionallyOmittedKeyUp": True,
                "intentionalCrashVerified": False,
                "externalReleaseProcessReserved": True,
                "requestedPrecrashHoldMilliseconds": args.precrash_hold_ms,
            }
            with Path(args.down_marker).open("x", encoding="utf8", newline="\n") as file:
                json.dump(marker, file, allow_nan=False)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())

            # File I/O and the optional hold are separately fallible/slow.
            # Neither may consume the lease and then permit an intentional
            # crash that abandons a key after its release child has expired.
            last_clock = _probe_clock(time.monotonic, last_clock)
            _crash_deadline(renewed, last_clock, hold_s)
            if not release.alive:
                raise CrashReleaseRefused("release child unavailable after DOWN marker")
            if hold_s:
                time.sleep(hold_s)
            last_clock = _probe_clock(time.monotonic, last_clock)
            _crash_deadline(renewed, last_clock, 0.)
            if not release.alive:
                raise CrashReleaseRefused("release child unavailable before intentional crash")

            # A real abrupt process exit skips this except block and the
            # context manager, preserving the independent EOF/TTL experiment.
            # Check/exit remains non-atomic; the launcher remains a backup.
            os._exit(_EXIT)
            raise CrashReleaseRefused("intentional crash exit returned unexpectedly")
        except BaseException:
            # Compensation deliberately reads no clock and performs no disk
            # I/O. Attempt UP even when DOWN raised after possible insertion.
            # A failed local UP leaves the child's reservation intact for STOP.
            try:
                if down_attempted:
                    try:
                        accepted_up = sender.send("A", False) is True
                    except Exception:
                        accepted_up = False
                    if accepted_up:
                        try:
                            release.clear("A")
                        except SupervisorUnavailable:
                            pass  # expiry/EOF may already have latched child STOP
            finally:
                try:
                    release.stop()
                except SupervisorUnavailable:
                    pass  # preserve the original fault; launcher/TTL/EOF remain
            raise


def run_physical_crash_probe(args: argparse.Namespace) -> dict:
    """Keep independent backup A-UP in this live launcher."""
    if sys.platform != "win32":
        raise CrashReleaseRefused("physical crash release requires Windows")
    if not args.execute_physical:
        raise CrashReleaseRefused("explicit --execute-physical required (no implicit action)")
    pin = _pin(args)
    if type(args.precrash_hold_ms) is not int or not 0 <= args.precrash_hold_ms <= 140:
        raise CrashReleaseRefused("bounded pre-crash A hold must be 0..140 ms")
    scene = _verify_scene(args.scene, args.scene_sha256)
    report_path = _new_path(args.out, label="final report")
    audit_path = _new_path(args.audit, label="external child release audit")
    marker_path = _new_path(args.down_marker, label="child DOWN marker")
    guard_path = _new_path(args.guard, label="launcher guard")
    paths = [str(x.resolve()) for x in (report_path, audit_path, marker_path, guard_path)]
    if len(set(paths)) != len(paths):
        raise CrashReleaseRefused("evidence paths must be distinct")
    _identity(pin, inspect_desktop)
    keyboard = Win32KeySnapshot()
    if any(validate_key_snapshot(keyboard.snapshot()).values()):
        raise CrashReleaseRefused("W/A/D keys already down: no diagnostic admitted")
    native_before = _capture(pin, args.owner_key, capture_native_candidate)
    _identity(pin, inspect_desktop)
    if time.time() - Path(args.scene).stat().st_mtime > 180:
        raise CrashReleaseRefused("screenshot expired during admission")

    challenge = secrets.token_hex(16)
    guard = {"token": challenge, "launcherPid": os.getpid(),
             "targetPid": pin.pid, "createdUtc": datetime.now(timezone.utc).isoformat()}
    with guard_path.open("x", encoding="utf8") as file:
        json.dump(guard, file)
    base = [
        "--host", pin.host, "--pid", str(pin.pid),
        "--start-ticks", str(pin.start_utc_ticks),
        "--hwnd", str(pin.hwnd), "--exe-path", pin.executable_path,
        "--sha256", pin.sha256, "--owner-key", str(args.owner_key),
    ]
    cmd = [
        sys.executable, "-B", "-m", "rift_taxi.crash_release_probe",
        "--_crash-worker", *base,
        "--guard", str(guard_path), "--guard-token", challenge,
        "--launcher-pid", str(os.getpid()),
        "--audit", str(audit_path), "--down-marker", str(marker_path),
        "--precrash-hold-ms", str(args.precrash_hold_ms),
    ]
    start = time.monotonic()
    parent_exit = None
    backup_used = False
    backup_accepted = None
    audit = {}
    observed_a_down = False
    process = None
    try:
        process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   cwd=str(Path(__file__).resolve().parents[1]))
        deadline = start + 7.
        # Observe the child making its actual keydown, then its exit.
        while time.monotonic() < deadline:
            if keyboard.snapshot().get("A") is True:
                observed_a_down = True
            parent_exit = process.poll()
            if parent_exit is not None:
                break
            time.sleep(.01)
        if parent_exit is None:
            raise CrashReleaseRefused("crash worker did not exit in bounded time")
        # The separate release child should send UP after parent EOF or TTL.
        # Wait at most .8s, then this launcher independently rescues A UP.
        rescue_deadline = time.monotonic() + .8
        while time.monotonic() < rescue_deadline:
            audit = _audit_summary(audit_path, pin)
            if audit["nativeChildUpAcceptedByOS"]:
                break
            time.sleep(.02)
    finally:
        # Do not leave an injected A stuck if the child fails. If A was sent,
        # the launcher attempts a bounded redundant UP on absent child proof.
        marker_exists = marker_path.is_file()
        audit = _audit_summary(audit_path, pin)
        # If the sender is still alive after its deadline, it can deliver a
        # late DOWN after an earlier UP. Kill and reap it BEFORE the rescue UP.
        unexpected_live_sender = process is not None and process.poll() is None
        if unexpected_live_sender:
            process.kill()
            process.wait(timeout=2)
        # Even a crash between DOWN and durable marker creation can leave A
        # held. Initially all W/A/D were UP; a live sender timing out also
        # creates uncertain A-down state even without a marker.
        possible_injected_a = marker_exists or observed_a_down or unexpected_live_sender
        if (possible_injected_a and
                (unexpected_live_sender or not audit["nativeChildUpAcceptedByOS"])):
            backup_used = True
            try:
                backup_accepted = Win32ScanSender().send("A", False) is True
            except Exception:
                backup_accepted = False

    time.sleep(.15)
    _identity(pin, inspect_desktop)
    keys_after = validate_key_snapshot(keyboard.snapshot())
    # An accepted native child UP is not evidence of an OS key bit being UP.
    # If the independent check still sees A down, add a clearly reported
    # launcher rescue and re-sample rather than returning a stuck-key report.
    post_readback_rescue = False
    if keys_after["A"]:
        post_readback_rescue = True
        backup_used = True
        try:
            backup_accepted = Win32ScanSender().send("A", False) is True
        except Exception:
            backup_accepted = False
        keys_after = validate_key_snapshot(keyboard.snapshot())
    native_after = _capture(pin, args.owner_key, capture_native_candidate)
    _identity(pin, inspect_desktop)
    time.sleep(.25)
    keys_settled = validate_key_snapshot(keyboard.snapshot())
    native_settled = _capture(pin, args.owner_key, capture_native_candidate)
    _identity(pin, inspect_desktop)
    audit = _audit_summary(audit_path, pin)
    marker = (json.loads(marker_path.read_text(encoding="utf8"))
              if marker_path.is_file() else None)
    source = {
        "host": pin.host, "pid": pin.pid, "startUtcTicks": pin.start_utc_ticks,
        "executablePath": pin.executable_path,
        "onDiskExecutableSha256": pin.sha256,
        "windowHandle": pin.hwnd, "ownerKeyDecimalCandidate": str(args.owner_key),
        "reviewedScene": scene,
    }
    # A physical child may emit an OS UP before or after the intentional
    # parent abort; evidence is only accepted if a durable marker proves a
    # real A DOWN preceded that native UP and the correct lease was reserved.
    mark_down = marker.get("atMonotonicSeconds") if isinstance(marker, dict) else None
    marker_valid = (
        isinstance(marker, dict)
        and marker.get("schema") == "taxi.m1-parent-crash-A-down/1"
        and marker.get("downAcceptedByOS") is True
        and marker.get("parentIntentionallyOmittedKeyUp") is True
        and marker.get("externalReleaseProcessReserved") is True
        and marker.get("requestedPrecrashHoldMilliseconds") == args.precrash_hold_ms
        and marker.get("targetPid") == pin.pid
        and marker.get("startUtcTicks") == pin.start_utc_ticks
        and marker.get("ownerKeyDecimal") == str(args.owner_key)
        and type(mark_down) in (int, float)
        and 0 < mark_down < time.monotonic()
    )
    release_at = audit.get("releaseAcceptedAtMonotonicSeconds")
    child_sequence_valid = (
        marker_valid
        and audit.get("reserveAckObserved") is True
        and audit.get("renewAckObserved") is True
        and audit.get("childStopObserved") is True
        and audit.get("childStopReason") in ("parent-disconnected", "lease-expired")
        and type(release_at) in (int, float)
        and release_at > mark_down
    )
    result = {
        "schema": "taxi.m1-parent-crash-release-probe/1",
        "status": "physical-emergency-release-candidate-only",
        "source": source,
        "parent": {
            "crashWorkerExitCode": parent_exit,
            "intentionalExitCode": _EXIT,
            "workerProcessExitedAsExpected": parent_exit == _EXIT,
            "WInputForbidden": True,
            "requestedPrecrashHoldMilliseconds": args.precrash_hold_ms,
            "AKeyDownMarker": marker,
            "AKeyDownMarkerSHA256": (
                hashlib.sha256(marker_path.read_bytes()).hexdigest()
                if marker_path.is_file() else None),
            "independentLauncherObservedAHighBit": observed_a_down,
            "launcherBackupKeyUpAttempted": backup_used,
            "launcherBackupKeyUpAcceptedByOS": backup_accepted,
            "launcherPostReadbackRescueAttempted": post_readback_rescue,
        },
        "child": audit,
        "readback": {
            "sampledKeysAfter": keys_after,
            "sampledKeysSettled": keys_settled,
            "candidateBefore": native_before,
            "candidateAfter": native_after,
            "candidateSettled": native_settled,
            "sameActorAndSession": True,
            "releaseConsumedByGameIndependentlyVerified": False,
            "liveBodyHeadingQualified": False,
            "nativeXYZPassiveFreshnessVerified": False,
        },
        "qualification": {
            "actualParentCrashAndChildOSUpObserved": (
                parent_exit == _EXIT and audit["nativeChildUpAcceptedByOS"]
                and child_sequence_valid and not backup_used),
            "durableDownMarkerAndChildReleaseOrderVerified": child_sequence_valid,
            "osKeysUpAfter": not any(keys_after.values()) and not any(keys_settled.values()),
            "crashProofReleaseGuaranteed": False,
            "gameConsumedReleaseVerified": False,
            "productionNavigationArmed": False,
            "M1Complete": False,
        },
        "limitations": [
            "Physical A-only crash probe is not a W movement or route test.",
            "A high-bit key snapshot and OS UP receipt do not prove RIFT game consumption.",
            "The independent launcher may have missed a very short A key-down interval.",
            "Child native UP and backup UP are distinct and recorded separately.",
            "Native angle/XYZ candidate reads are potentially refreshed by installed addon API polling.",
            "This does not prove release when the release child itself crashes or Windows freezes.",
        ],
    }
    with report_path.open("x", encoding="utf8", newline="\n") as file:
        json.dump(result, file, allow_nan=False, indent=2)
        file.write("\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rift_taxi.crash_release_probe",
        description="Special one-A-key crash-release diagnostic, never navigation",
    )
    parser.add_argument("--_crash-worker", action="store_true",
                        help=argparse.SUPPRESS)
    _pins(parser)
    parser.add_argument("--execute-physical", action="store_true")
    parser.add_argument("--precrash-hold-ms", type=int, default=0,
                        help="0..140 ms A-only hold before intentional process death")
    parser.add_argument("--scene")
    parser.add_argument("--scene-sha256")
    parser.add_argument("--out")
    parser.add_argument("--audit", required=True)
    parser.add_argument("--down-marker", required=True)
    parser.add_argument("--guard", required=True)
    parser.add_argument("--guard-token", help=argparse.SUPPRESS)
    parser.add_argument("--launcher-pid", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args._crash_worker:
            if (not args.guard_token or type(args.launcher_pid) is not int
                    or args.launcher_pid <= 0):
                raise CrashReleaseRefused("internal worker requires active launcher guard")
            return _child(args)
        result = run_physical_crash_probe(args)
        print(json.dumps({
            "status": result["status"],
            "source": result["source"],
            "parent": result["parent"],
            "child": result["child"],
            "qualification": result["qualification"],
        }, indent=2, allow_nan=False))
        return 0 if (
            result["qualification"]["actualParentCrashAndChildOSUpObserved"]
            and result["qualification"]["osKeysUpAfter"]
        ) else 2
    except (CrashReleaseRefused, TurnProbeRefused, SupervisorUnavailable,
            OSError, ValueError) as exc:
        print(f"rift-taxi crash-release: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
