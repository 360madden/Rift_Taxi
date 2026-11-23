"""Taxi-owned, driver-neutral live control gate (M1 pre-hardware slice).

This module deliberately does not select a RIFT process or inject Windows input.
A future native pose reader and independently tested, bounded OS backend must be
connected before any live-control claim. The recording tests exercise decisions,
not game-consumed keys or real player motion.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import threading
import time
from typing import Callable, Iterable, Protocol

_ORDER = ("W", "A", "D")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")


class ControlRefused(RuntimeError):
    """A session, telemetry, input, or latched STOP gate rejected control."""


def _positive_int(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be nonempty trimmed text")


def _finite(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    try:
        x = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{name} must be finite") from error
    if not math.isfinite(x):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class SessionBinding:
    """Exact-client/actor identity supplied by a *future verified* reader.

    start_ticks is the operating system's process-creation identity, not a
    reusable PID alone. window_handle and actor_id must be freshly qualified.
    """

    host: str
    process_id: int
    start_ticks: int
    executable_sha256: str
    window_handle: int
    actor_id: str
    zone_id: str

    def __post_init__(self) -> None:
        for field in ("host", "actor_id", "zone_id"):
            _nonempty(getattr(self, field), field)
        for field in ("process_id", "start_ticks", "window_handle"):
            _positive_int(getattr(self, field), field)
        if not isinstance(self.executable_sha256, str) or not _SHA256.fullmatch(self.executable_sha256):
            raise ValueError("executable_sha256 must be 64 hex digits")


@dataclass(frozen=True)
class LivePose:
    """One same-clock, actor-qualified pose; it does not prove motion."""

    session: SessionBinding
    sequence: int
    observed_monotonic_s: float
    xyz: tuple[float, float, float]
    actor_yaw_deg: float
    actor_yaw_verified: bool
    foreground_verified: bool

    def __post_init__(self) -> None:
        if not isinstance(self.session, SessionBinding):
            raise ValueError("session must be a SessionBinding")
        _positive_int(self.sequence, "sequence")
        _finite(self.observed_monotonic_s, "observed_monotonic_s")
        if self.observed_monotonic_s < 0:
            raise ValueError("observed_monotonic_s cannot be negative")
        if not isinstance(self.xyz, tuple) or len(self.xyz) != 3:
            raise ValueError("xyz must contain X/Y/Z")
        for axis, value in zip("xyz", self.xyz):
            _finite(value, axis)
        _finite(self.actor_yaw_deg, "actor_yaw_deg")
        if type(self.actor_yaw_verified) is not bool or type(self.foreground_verified) is not bool:
            raise ValueError("qualification flags must be bool")


class KeyBackend(Protocol):
    """Synchronous bounded insertion only. True means *backend accepted*.

    Insertion is NOT a verified in-game key transition. Production must supply
    an independently supervised, tested Windows-specific implementation.
    """

    def write_key(self, key: str, is_down: bool) -> bool: ...


@dataclass(frozen=True)
class KeyEdge:
    at_monotonic_s: float
    key: str
    is_down: bool
    backend_accepted: bool


@dataclass(frozen=True)
class ControlStatus:
    stop_latched: bool
    stop_reason: str | None
    potentially_held_keys: tuple[str, ...]
    last_pose_sequence: int | None
    backend_release_fault_observed: bool
    game_response_verified: bool = False


class HeldInputController:
    """In-process exclusive W/A/D state with fail-closed, timed release.

    A watchdog thread checks lease/pose expiry independently of a normal
    steering loop. Backends MUST return promptly; Python threads cannot
    rescue a blocked foreign driver or assert RIFT consumed a release.
    Exactly one controller per process is assumed here; cross-process
    exclusion, current native telemetry and Windows injection are not built.
    STOP is latched for the lifetime of the controller; rearm requires a new
    exact-identity controller and fresh pose qualification.
    """

    def __init__(
        self,
        session: SessionBinding,
        backend: KeyBackend,
        *,
        max_pose_age_s: float = 0.35,
        max_hold_s: float = 0.50,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(session, SessionBinding):
            raise ValueError("session must be a SessionBinding")
        if not callable(getattr(backend, "write_key", None)):
            raise ValueError("backend must provide write_key")
        for label, limit in (("max_pose_age_s", max_pose_age_s), ("max_hold_s", max_hold_s)):
            _finite(limit, label)
            if not 0.02 <= limit <= 5.0:
                raise ValueError(f"{label} must be between 0.02 and 5 seconds")
        if not callable(clock):
            raise ValueError("clock must be callable")
        self.session = session
        self._backend = backend
        self._clock = clock
        self._pose_age = float(max_pose_age_s)
        self._hold_s = float(max_hold_s)
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._closed = False
        self._stop_latched = False
        self._stop_reason: str | None = None
        # A rejected or exceptional DOWN is also potentially held until UP accepted.
        self._potentially_held: set[str] = set()
        self._last_pose: LivePose | None = None
        self._lease_deadline: float | None = None
        self._release_fault = False
        self._edges: list[KeyEdge] = []
        self._thread = threading.Thread(
            target=self._watch, name="RiftTaxiInputWatchdog", daemon=True
        )
        self._thread.start()

    def __enter__(self) -> "HeldInputController":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def events(self) -> tuple[KeyEdge, ...]:
        with self._lock:
            return tuple(self._edges)

    @property
    def status(self) -> ControlStatus:
        with self._lock:
            return ControlStatus(
                stop_latched=self._stop_latched,
                stop_reason=self._stop_reason,
                potentially_held_keys=tuple(k for k in _ORDER if k in self._potentially_held),
                last_pose_sequence=self._last_pose.sequence if self._last_pose else None,
                backend_release_fault_observed=self._release_fault,
            )

    def _write_edge(self, key: str, down: bool, now: float) -> bool:
        if down:
            # Assume uncertainty before attempting DOWN, including exceptions.
            self._potentially_held.add(key)
        try:
            accepted = self._backend.write_key(key, down) is True
        except Exception:
            accepted = False
        self._edges.append(KeyEdge(now, key, down, accepted))
        if not down:
            if accepted:
                self._potentially_held.discard(key)
            else:
                self._release_fault = True
        return accepted

    def _release_all(self, now: float) -> None:
        # Attempt EVERY key even if one release fails; retain unsuccessful keys.
        for key in ("A", "D", "W"):
            if key in self._potentially_held:
                self._write_edge(key, False, now)
        self._lease_deadline = None

    def _stop_locked(self, reason: str, now: float) -> None:
        if not self._stop_latched:
            self._stop_reason = reason
        self._stop_latched = True
        self._release_all(now)
        self._wake.set()

    def stop(self, reason: str = "explicit-stop") -> ControlStatus:
        """STOP stays latched. Repeated STOP retries any unaccepted key-ups."""
        _nonempty(reason, "reason")
        with self._lock:
            self._stop_locked(reason, self._clock())
            return self.status

    def _expire_locked(self, now: float) -> None:
        if self._stop_latched or not self._potentially_held:
            return
        if self._last_pose is None or now - self._last_pose.observed_monotonic_s > self._pose_age:
            self._stop_locked("pose-expired", now)
        elif self._lease_deadline is None or now >= self._lease_deadline:
            self._stop_locked("lease-expired", now)

    def check_expiry(self) -> ControlStatus:
        """Deterministic expiry check, also used by the watchdog thread."""
        with self._lock:
            self._expire_locked(self._clock())
            return self.status

    def _watch(self) -> None:
        while True:
            self._wake.wait(0.025)
            self._wake.clear()
            with self._lock:
                if self._closed:
                    return
                self._expire_locked(self._clock())

    def _validate_pose(self, pose: LivePose, now: float) -> None:
        if not isinstance(pose, LivePose):
            raise ControlRefused("native pose missing/invalid")
        if pose.session != self.session:
            raise ControlRefused("process/window/actor/zone identity changed")
        if not pose.actor_yaw_verified:
            raise ControlRefused("actor yaw is not independently qualified")
        if not pose.foreground_verified:
            raise ControlRefused("target window foreground not verified")
        age = now - pose.observed_monotonic_s
        if age < -0.05 or age > self._pose_age:
            raise ControlRefused("pose is stale or from a different clock")
        if self._last_pose is not None:
            previous = self._last_pose
            if pose.sequence < previous.sequence:
                raise ControlRefused("pose sequence rolled backward")
            if pose.sequence == previous.sequence and pose != previous:
                raise ControlRefused("contradictory duplicate pose sequence")
            if (pose.sequence > previous.sequence
                    and pose.observed_monotonic_s <= previous.observed_monotonic_s):
                raise ControlRefused("pose timestamp failed to advance")

    def apply(self, requested_keys: Iterable[str], pose: LivePose) -> ControlStatus:
        """Set desired W/A/D set, releasing obsolete keys BEFORE pressing new.

        Continuous W is preserved while turning. Source, time and ownership
        checks precede every new input. Any failure latches STOP and attempts
        release; no automatic rearm.
        """
        with self._lock:
            now = self._clock()
            self._expire_locked(now)
            if self._stop_latched or self._closed:
                raise ControlRefused(f"STOP latched: {self._stop_reason}")
            try:
                # Reject strings, unbounded generators and custom iterables, even
                # if they happen to contain valid characters. Never let malformed
                # steering requests leave previously held keys active.
                if not isinstance(requested_keys, (list, tuple, set, frozenset)):
                    raise ControlRefused("requested movement keys must be a finite collection")
                if any(type(key) is not str or key not in _ORDER for key in requested_keys):
                    raise ControlRefused("unsupported movement key")
                desired = set(requested_keys)
                if "A" in desired and "D" in desired:
                    raise ControlRefused("invalid or contradictory movement keys")
                self._validate_pose(pose, now)
            except Exception as error:
                # Covers validation exceptions and broken collection methods too.
                # Input faults are STOP events, not permission to keep W held.
                self._stop_locked(str(error), now)
                raise ControlRefused(str(error)) from error
            self._last_pose = pose
            # Release all obsolete inputs before allowing any new direction.
            for key in ("A", "D", "W"):
                if key in self._potentially_held and key not in desired:
                    if not self._write_edge(key, False, now):
                        self._stop_locked("backend-release-rejected", now)
                        raise ControlRefused("backend-release-rejected")
            for key in _ORDER:
                if key in desired and key not in self._potentially_held:
                    if not self._write_edge(key, True, now):
                        self._stop_locked("backend-press-rejected", now)
                        raise ControlRefused("backend-press-rejected")
            self._lease_deadline = now + self._hold_s if self._potentially_held else None
            self._wake.set()
            return self.status

    def close(self) -> None:
        with self._lock:
            self._stop_locked("controller-closed", self._clock())
            self._closed = True
            self._wake.set()
        if self._thread is not threading.current_thread():
            self._thread.join(timeout=1)
