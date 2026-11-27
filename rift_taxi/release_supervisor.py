"""Separate-process, release-only W/A/D + camera mouse lease (M1 prototype).

A reserve ACK precedes any future controller key-down. On lease expiry, EOF,
or explicit STOP, the child process attempts release for all reserved keys.

No game inputs are issued when dry_run=True. The supervisor is NOT connected
to a live Taxi controller or enabled by any CLI command. Real release calls
require exact OS process/window epoch qualification. SendInput acceptance is
not proof the game consumed key-up. The process itself can also fail.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import ctypes
from ctypes import wintypes
import json
import math
import multiprocessing as mp
from multiprocessing.connection import Connection
import ntpath
from pathlib import Path
import sys
import threading
import time
from typing import Callable

from .control import ControlRefused, LivePose
from .win32_identity import DesktopCandidate, ProcessInfo, Win32DesktopProbe, inspect_desktop
from .win32_input import Win32ScanSender
from .win32_mouse import Win32MouseSender

_KEYS = ("A", "D", "W", "MOUSE_LEFT")
_ERROR_ALREADY_EXISTS = 183


class SupervisorUnavailable(RuntimeError):
    """External key-release lease could not be acquired or maintained."""


@dataclass(frozen=True)
class ReleaseLeasePin:
    host: str
    pid: int
    start_utc_ticks: int
    hwnd: int
    executable_path: str
    sha256: str

    @classmethod
    def from_live_pose(cls, pose: LivePose, executable_path: str) -> "ReleaseLeasePin":
        if (not isinstance(pose, LivePose) or pose.actor_yaw_verified is not True
                or pose.foreground_verified is not True):
            raise SupervisorUnavailable("independently qualified live actor pose required")
        s = pose.session
        if not isinstance(executable_path, str) or not ntpath.isabs(executable_path):
            raise SupervisorUnavailable("absolute executable path required")
        return cls(s.host, s.process_id, s.start_ticks, s.window_handle,
                   executable_path, s.executable_sha256)


class _TaxiSessionMutex:
    """Windows kernel name excludes simultaneous cooperating Taxi controllers."""

    def __init__(self, pin: ReleaseLeasePin) -> None:
        self.handle = None
        if sys.platform != "win32":
            raise SupervisorUnavailable("Windows-only external supervisor")
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        k.CreateMutexW.restype = wintypes.HANDLE
        k.ReleaseMutex.argtypes = (wintypes.HANDLE,)
        k.ReleaseMutex.restype = wintypes.BOOL
        k.CloseHandle.argtypes = (wintypes.HANDLE,)
        k.CloseHandle.restype = wintypes.BOOL
        name = f"Local\\RiftTaxi-{pin.pid}-{pin.start_utc_ticks}"
        handle = k.CreateMutexW(None, True, name)
        error = ctypes.get_last_error()
        if not handle:
            raise SupervisorUnavailable(f"CreateMutexW failed (Win32 {error})")
        if error == _ERROR_ALREADY_EXISTS:
            k.CloseHandle(handle)
            raise SupervisorUnavailable("another Taxi supervisor already owns this game epoch")
        self._kernel = k
        self.handle = handle

    def close(self) -> None:
        if self.handle:
            self._kernel.ReleaseMutex(self.handle)
            self._kernel.CloseHandle(self.handle)
            self.handle = None


class ReleaseState:
    """Pure deterministic lease state machine, using an injected release function."""

    def __init__(self, *, ttl_s: float = 0.5,
                 clock: Callable[[], float] = time.monotonic,
                 release: Callable[[str], bool]):
        if type(ttl_s) not in (int, float) or not 0.10 <= ttl_s <= 2.0:
            raise ValueError("release ttl must be within 0.10..2.0 seconds")
        if not callable(clock) or not callable(release):
            raise ValueError("clock and release callback required")
        self.clock = clock
        self.release = release
        self.ttl_s = float(ttl_s)
        self.held: set[str] = set()
        self.deadline: float | None = None
        self.stopped = False
        self.reason: str | None = None
        self.release_results: list[tuple[str, bool]] = []
        self._last_clock: float | None = None

    def status(self) -> dict:
        return {
            "stopped": self.stopped, "reason": self.reason,
            "possibleHeld": [key for key in _KEYS if key in self.held],
            "deadlineMonotonicSeconds": self.deadline,
            "releaseAttempts": [
                {"key": key, "releaseHandlerAccepted": accepted}
                for key, accepted in self.release_results
            ],
            "gameResponseVerified": False,
        }

    def _release_all(self) -> None:
        for key in _KEYS:
            if key not in self.held:
                continue
            try:
                accepted = self.release(key) is True
            except Exception:
                accepted = False
            self.release_results.append((key, accepted))
            if accepted:
                self.held.discard(key)
        self.deadline = None

    def stop(self, reason: str) -> dict:
        if not self.stopped:
            self.stopped = True
            self.reason = reason
        self._release_all()
        return self.status()

    def _admit_clock(self) -> float | None:
        """Validate a single monotonic sample before admitting a lease operation.

        Clock failure must not suppress release or resurrect an expired lease.
        Validate even when idle, retaining the last admitted epoch across CLEAR.
        Leave room below the status protocol's finite deadline bound for the
        maximum TTL. Reject bools and unrepresentable numeric inputs before
        floating-point conversion. No clock is needed to attempt STOP/release.
        """
        if self.stopped:
            return None
        try:
            raw = self.clock()
            if type(raw) not in (int, float) or not 0 <= raw <= 1e15 - 2:
                raise ValueError("invalid monotonic sample")
            now = float(raw)
        except Exception:
            self.stop("clock-invalid")
            return None
        if self._last_clock is not None and now < self._last_clock:
            self.stop("clock-rollback")
            return None
        self._last_clock = now
        if self.deadline is not None and now >= self.deadline:
            self.stop("lease-expired")
            return None
        return now

    def expire(self) -> bool:
        self._admit_clock()
        return self.stopped

    def command(self, action: str, key: str | None = None) -> dict:
        # Use the very same admitted timestamp for expiry and new deadline.
        # A second unvalidated read could cross the previous lease boundary.
        now = self._admit_clock()
        if action == "status":
            return self.status()
        if action == "stop":
            return self.stop("explicit-stop")
        if self.stopped:
            raise SupervisorUnavailable("release supervisor STOP latched")
        if action == "reserve":
            if type(key) is not str or key not in _KEYS or key in self.held:
                self.stop("invalid-or-duplicate-reserve")
                raise SupervisorUnavailable("duplicate/invalid reserved key")
            self.held.add(key)
        elif action == "clear":
            if type(key) is not str or key not in self.held:
                self.stop("invalid-clear")
                raise SupervisorUnavailable("clear requires a known reserved key")
            # The parent only sends CLEAR after receiving OS key-up acceptance.
            # This statement is NOT evidence of game key-release consumption.
            self.held.discard(key)
        elif action == "renew":
            if key is not None:
                self.stop("invalid-heartbeat")
                raise SupervisorUnavailable("renew must not carry a key")
        else:
            self.stop("invalid-operation")
            raise SupervisorUnavailable("unknown supervisor operation")
        assert now is not None  # STOP and invalid clocks were refused above.
        self.deadline = now + self.ttl_s if self.held else None
        return self.status()


def _exact_release_possible(pin: ReleaseLeasePin) -> bool:
    """Reject PID reuse/HWND reuse; focus is not required for emergency key-up."""
    try:
        probe = Win32DesktopProbe()
        process = probe.process(pin.pid)
        return (
            isinstance(process, ProcessInfo) and process.pid == pin.pid
            and process.start_utc_ticks == pin.start_utc_ticks
            and ntpath.normcase(process.executable_path) == ntpath.normcase(pin.executable_path)
            and probe.window_belongs_to_pid(pin.hwnd, pin.pid)
        )
    except (OSError, RuntimeError, ValueError):
        return False


def _audit(path: Path | None, kind: str, data: dict) -> None:
    if path is None:
        return
    payload = {
        "atUtc": datetime.now(timezone.utc).isoformat(),
        "monotonicSeconds": time.monotonic(),
        "event": kind, **data,
    }
    with path.open("a", encoding="utf8", newline="\n") as stream:
        stream.write(json.dumps(payload, allow_nan=False, sort_keys=True) + "\n")
        stream.flush()


def _worker_entry(conn: Connection, pin: ReleaseLeasePin, ttl_s: float,
                  dry_run: bool, audit_path: str | None) -> None:
    """Spawn target. Never imports or calls game input when dry_run=True."""
    lock = None
    state: ReleaseState | None = None
    path = Path(audit_path) if audit_path is not None else None
    audit_created = False
    try:
        lock = _TaxiSessionMutex(pin)
        # A new evidence filename is mandatory; do not truncate prior receipts.
        if path is not None:
            with path.open("x", encoding="utf8"):
                pass
            audit_created = True
        sender = None if dry_run else Win32ScanSender()

        def release(key: str) -> bool:
            if dry_run:
                _audit(path, "simulated-key-up", {"key": key, "acceptedByOS": False})
                return True  # fake sink ledger only: not OS acceptance!
            if not _exact_release_possible(pin):
                _audit(path, "release-not-sent-identity-unavailable",
                       {"key": key, "acceptedByOS": False})
                return False
            accepted = (Win32MouseSender().send(key, False)
                        if key == "MOUSE_LEFT" else sender.send(key, False)) is True
            _audit(path, "native-mouse-up-attempt" if key == "MOUSE_LEFT"
                   else "native-key-up-attempt",
                   {"key": key, "acceptedByOS": accepted})
            return accepted

        state = ReleaseState(ttl_s=ttl_s, release=release)
        _audit(path, "ready", {"dryRun": dry_run, "pid": pin.pid,
                                "gameResponseVerified": False})
        conn.send({"ok": True, "ready": True, "dryRun": dry_run})
        while True:
            # The independent child clock enforces expiry even if the parent
            # steering loop hangs or stops sending messages.
            if state.expire():
                _audit(path, "stop", state.status())
                break
            timeout = (min(0.025, max(0.0, state.deadline - time.monotonic()))
                       if state.deadline is not None else 0.1)
            try:
                has_data = conn.poll(timeout)
            except (OSError, EOFError):
                has_data = False
                state.stop("parent-connection-error")
                break
            if not has_data:
                continue
            try:
                request = conn.recv()
            except (EOFError, OSError):
                state.stop("parent-disconnected")
                _audit(path, "stop", state.status())
                break
            try:
                if (not isinstance(request, dict) or set(request) != {"action", "key"}
                        or not isinstance(request["action"], str)):
                    raise SupervisorUnavailable("invalid protocol message")
                result = state.command(request["action"], request["key"])
                _audit(path, "command", {
                    "action": request["action"], "key": request["key"],
                    "status": result,
                })
                conn.send({"ok": True, "status": result})
            except SupervisorUnavailable as error:
                state.stop("protocol-error")
                _audit(path, "stop", {"error": str(error), **state.status()})
                try:
                    conn.send({"ok": False, "error": str(error), "status": state.status()})
                except (EOFError, OSError):
                    pass
                break
            except (EOFError, OSError):
                state.stop("parent-connection-error")
                _audit(path, "stop", state.status())
                break
            if state.stopped:
                _audit(path, "stop", state.status())
                break
    except Exception as error:
        _audit(path if audit_created else None, "worker-init-or-runtime-failed",
               {"error": type(error).__name__, "message": str(error)})
        try:
            conn.send({"ok": False, "error": str(error)})
        except (EOFError, OSError):
            pass
    finally:
        # Do not silently abandon a failed OS key-up after the first try.
        # Retry at most twice; after that retain unresolved evidence and exit.
        # These attempts cannot prove the RIFT client consumed key-up.
        if state is not None and state.held:
            for attempt in range(1, 3):
                time.sleep(0.025)
                state.stop("final-release-retry")
                _audit(path if audit_created else None, "bounded-final-release-retry",
                       {"attempt": attempt, **state.status()})
                if not state.held:
                    break
        if lock is not None:
            lock.close()
        conn.close()


class ExternalReleaseSupervisor:
    """Parent client for a separate non-daemon, short-lease release-only child.

    Future supervised input adapter must synchronously reserve each key BEFORE
    sending DOWN, and CLEAR only after accepted UP. This is not automatically
    connected to WindowsScanKeyBackend and is not enabled for live RIFT control.
    """

    def __init__(self, process: mp.Process, connection: Connection,
                 pin: ReleaseLeasePin, dry_run: bool,
                 *, ack_timeout_s: float = 1.5):
        self.pin = pin
        self.dry_run = dry_run
        self._process = process
        self._conn = connection
        self._timeout = ack_timeout_s
        self._closed = False
        self._channel_failed = False
        self._request_lock = threading.RLock()

    @classmethod
    def start(cls, pose: LivePose, executable_path: str, *,
              ttl_s: float = 0.5, dry_run: bool = True,
              audit_path: str | None = None, ack_timeout_s: float = 1.5):
        if type(dry_run) is not bool:
            raise ValueError("dry_run must be bool")
        pin = ReleaseLeasePin.from_live_pose(pose, executable_path)
        if isinstance(ack_timeout_s, bool) or not isinstance(ack_timeout_s, (int, float)) \
                or not math.isfinite(ack_timeout_s) or not .2 <= ack_timeout_s <= 5:
            raise ValueError("ack timeout must be 0.2..5 seconds")
        if audit_path is not None:
            target = Path(audit_path)
            if target.exists() or not target.parent.is_dir():
                raise SupervisorUnavailable("audit path must be new, with existing parent")
        if not dry_run:
            now = time.monotonic()
            if now < pose.observed_monotonic_s or now - pose.observed_monotonic_s > 0.35:
                raise SupervisorUnavailable("native release requires current qualified pose")
            s = pose.session
            # Require the same real OS target before permitting a child that
            # can issue release-only SendInput. No input is sent here.
            desktop = inspect_desktop(
                s.process_id, expected_executable_path=executable_path,
                expected_executable_sha256=s.executable_sha256,
                expected_start_utc_ticks=s.start_ticks,
                expected_window_handle=s.window_handle,
                expected_host=s.host, require_foreground=True,
            )
            if not desktop.foreground:
                raise SupervisorUnavailable("release supervisor target not foreground")
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe(duplex=True)
        process = ctx.Process(target=_worker_entry,
                              args=(child, pin, ttl_s, dry_run, audit_path),
                              daemon=False, name="RiftTaxiReleaseSupervisor")
        try:
            process.start()
            child.close()
            if not parent.poll(ack_timeout_s):
                raise SupervisorUnavailable("supervisor did not acknowledge startup")
            reply = parent.recv()
            if not isinstance(reply, dict) or reply.get("ok") is not True \
                    or reply.get("ready") is not True or reply.get("dryRun") is not dry_run:
                raise SupervisorUnavailable(f"supervisor initialization refused: {reply}")
            return cls(process, parent, pin, dry_run, ack_timeout_s=ack_timeout_s)
        except Exception:
            parent.close()
            child.close()
            # Without parent handle the child will expire/observe EOF; never
            # blindly terminate a helper that might own uncertain key releases.
            raise

    @classmethod
    def start_turn_probe(
        cls, pin: ReleaseLeasePin, *, ttl_s: float = 0.6,
        dry_run: bool = True, audit_path: str | None = None,
        ack_timeout_s: float = 4.0,
        admit: Callable = inspect_desktop,
    ) -> "ExternalReleaseSupervisor":
        """Release-only child for one bounded A/D/W or left-mouse diagnostic; no navigation.

        Does not fabricate a LivePose. Physical release capability requires a
        fresh exact-PID/start/path/SHA/HWND/foreground check. The caller must
        independently constrain the key, duration, current scene and release.
        """
        if not isinstance(pin, ReleaseLeasePin) or type(dry_run) is not bool:
            raise ValueError("validated pin and explicit dry_run bool required")
        if (type(pin.pid) is not int or pin.pid <= 0
                or type(pin.start_utc_ticks) is not int or pin.start_utc_ticks <= 0
                or type(pin.hwnd) is not int or pin.hwnd <= 0
                or not isinstance(pin.host, str) or not pin.host.strip()
                or not isinstance(pin.executable_path, str)
                or not ntpath.isabs(pin.executable_path)
                or not isinstance(pin.sha256, str)
                or len(pin.sha256) != 64
                or any(c not in "0123456789abcdefABCDEF" for c in pin.sha256)):
            raise ValueError("turn diagnostic pin must be fully specified")
        if not isinstance(ttl_s, (float, int)) or isinstance(ttl_s, bool) \
                or not math.isfinite(ttl_s) or not .4 <= ttl_s <= .8:
            raise ValueError("turn diagnostic release TTL must be .4..0.8 seconds")
        if not isinstance(ack_timeout_s, (float, int)) or isinstance(ack_timeout_s, bool) \
                or not math.isfinite(ack_timeout_s) or not 1 <= ack_timeout_s <= 5:
            raise ValueError("turn diagnostic ACK timeout must be 1..5 seconds")
        if audit_path is not None:
            destination = Path(audit_path)
            if destination.exists() or not destination.parent.is_dir():
                raise SupervisorUnavailable("turn diagnostic audit path must be new")
        if not dry_run:
            target = admit(
                pin.pid, expected_executable_path=pin.executable_path,
                expected_executable_sha256=pin.sha256,
                expected_start_utc_ticks=pin.start_utc_ticks,
                expected_window_handle=pin.hwnd,
                expected_host=pin.host, require_foreground=True,
            )
            if (not isinstance(target, DesktopCandidate) or not target.foreground
                    or target.pid != pin.pid
                    or target.start_utc_ticks != pin.start_utc_ticks
                    or target.window_handle != pin.hwnd
                    or target.executable_sha256.casefold() != pin.sha256.casefold()):
                raise SupervisorUnavailable("turn diagnostic release admission refused")
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe(duplex=True)
        process = ctx.Process(
            target=_worker_entry, args=(child, pin, ttl_s, dry_run, audit_path),
            daemon=False, name="RiftTaxiTurnProbeRelease",
        )
        try:
            process.start()
            child.close()
            if not parent.poll(ack_timeout_s):
                raise SupervisorUnavailable("turn diagnostic release process did not acknowledge")
            reply = parent.recv()
            if not isinstance(reply, dict) or reply.get("ok") is not True \
                    or reply.get("ready") is not True or reply.get("dryRun") is not dry_run:
                raise SupervisorUnavailable(f"turn diagnostic release worker refused: {reply}")
            return cls(process, parent, pin, dry_run, ack_timeout_s=ack_timeout_s)
        except Exception:
            parent.close()
            child.close()
            raise

    @property
    def alive(self) -> bool:
        return not self._closed and not self._channel_failed and self._process.is_alive()

    def _invalidate_channel(self) -> None:
        # A late reply after a timeout must never be consumed as the ACK for
        # another command. Closing the pipe also gives the worker its EOF
        # fallback; do not terminate a worker with uncertain reservations.
        self._channel_failed = True
        try:
            self._conn.close()
        except OSError:
            pass

    @staticmethod
    def _validate_status(status: object) -> dict:
        if not isinstance(status, dict):
            raise SupervisorUnavailable("missing release status")
        held = status.get("possibleHeld")
        stopped = status.get("stopped")
        attempts = status.get("releaseAttempts")
        deadline = status.get("deadlineMonotonicSeconds")
        if (type(stopped) is not bool
                or status.get("gameResponseVerified") is not False
                or not isinstance(held, list)
                or any(type(k) is not str or k not in _KEYS for k in held)
                or len(set(held)) != len(held)
                or not isinstance(attempts, list)
                or any(not isinstance(a, dict)
                       or type(a.get("key")) is not str or a["key"] not in _KEYS
                       or type(a.get("releaseHandlerAccepted")) is not bool
                       for a in attempts)
                or (deadline is not None and (
                    type(deadline) not in (int, float)
                    or not 0 <= deadline <= 1e15 or not math.isfinite(deadline)))
                or (stopped and deadline is not None)
                or (not stopped and bool(held) != (deadline is not None))):
            raise SupervisorUnavailable("malformed release status")
        return status

    def _request(self, action: str, key: str | None = None) -> dict:
        with self._request_lock:
            if not self.alive:
                self._invalidate_channel()
                raise SupervisorUnavailable("release supervisor not running")
            try:
                self._conn.send({"action": action, "key": key})
                if not self._conn.poll(self._timeout):
                    raise SupervisorUnavailable("release supervisor response timed out")
                reply = self._conn.recv()
                if not isinstance(reply, dict) or reply.get("ok") is not True:
                    raise SupervisorUnavailable(f"release supervisor refused: {reply}")
                status = self._validate_status(reply.get("status"))
                if action == "stop" and status["stopped"] is not True:
                    raise SupervisorUnavailable("STOP acknowledgement not latched")
                return status
            except (EOFError, OSError) as error:
                self._invalidate_channel()
                raise SupervisorUnavailable("release supervisor channel unavailable") from error
            except SupervisorUnavailable:
                self._invalidate_channel()
                raise

    def reserve(self, key: str) -> dict:
        """Must ACK before parent may attempt the corresponding key DOWN."""
        return self._request("reserve", key)

    def clear(self, key: str) -> dict:
        """Caller confirms accepted OS UP, *not* game-consumed release."""
        return self._request("clear", key)

    def renew(self) -> dict:
        """Required while held keys remain active; otherwise TTL auto-releases."""
        return self._request("renew")

    def status(self) -> dict:
        return self._request("status")

    def stop(self) -> dict:
        return self._request("stop")

    def close(self) -> None:
        with self._request_lock:
            if self._closed:
                return
            try:
                if self.alive:
                    try:
                        self.stop()
                    except SupervisorUnavailable:
                        pass  # child TTL/EOF is the fallback
            finally:
                self._closed = True
                self._conn.close()
        self._process.join(timeout=3.0)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
