"""Composite Windows W/A/D backend with independent release-process lease.

M1 prototype, deliberately not exposed as a live CLI command. The separate
release child must ACK a key reservation BEFORE any key-down insertion, and
the normal controller must renew its lease on EVERY fresh valid pose call,
even if no input edge changes.

No game input is issued during module import. Tests inject fake SendInput and
dry-run release workers. True game-consumed input and crash/restart resilience
remain unverified.
"""
from __future__ import annotations

import ntpath
from typing import Protocol

from .control import ControlRefused, SessionBinding
from .release_supervisor import ExternalReleaseSupervisor, SupervisorUnavailable
from .win32_input import WindowsScanKeyBackend

_KEYS = ("W", "A", "D")


class ReleaseSupervisorProtocol(Protocol):
    pin: object
    dry_run: bool
    alive: bool
    def reserve(self, key: str) -> dict: ...
    def clear(self, key: str) -> dict: ...
    def renew(self) -> dict: ...
    def stop(self) -> dict: ...


class SupervisedKeyBackend:
    """For HeldInputController, with external release reservation per DOWN edge.

    If either channel refuses, treat the key state as uncertain and allow
    STOP to attempt release; never label an OS ACK as in-game response.
    """

    def __init__(
        self, backend: WindowsScanKeyBackend,
        supervisor: ReleaseSupervisorProtocol,
    ) -> None:
        if not isinstance(backend, WindowsScanKeyBackend) or not backend.armed:
            raise ControlRefused("explicitly armed WindowsScanKeyBackend required")
        if not isinstance(supervisor, ExternalReleaseSupervisor):
            raise ControlRefused("external release process client required")
        if not supervisor.alive:
            raise ControlRefused("external release process not running")
        s: SessionBinding = backend.session
        pin = supervisor.pin
        if (pin.pid != s.process_id or pin.start_utc_ticks != s.start_ticks
                or pin.hwnd != s.window_handle or pin.host.casefold() != s.host.casefold()
                or pin.sha256.casefold() != s.executable_sha256.casefold()
                or ntpath.normcase(pin.executable_path)
                != ntpath.normcase(backend.executable_path)):
            raise ControlRefused("external release supervisor session mismatch")
        if backend.has_native_sender and supervisor.dry_run:
            raise ControlRefused("dry-run release supervisor cannot guard real OS key insertion")
        self.backend = backend
        self.supervisor = supervisor
        self.failed = False

    def _healthy(self, status: dict) -> bool:
        return (isinstance(status, dict)
                and status.get("stopped") is False
                and status.get("gameResponseVerified") is False)

    def renew_guard(self) -> bool:
        """Called on every fresh pose by HeldInputController, even W held."""
        if self.failed or not self.backend.armed or not self.supervisor.alive:
            self.failed = True
            return False
        try:
            state = self.supervisor.renew()
        except SupervisorUnavailable:
            self.failed = True
            return False
        if not self._healthy(state):
            self.failed = True
            return False
        return True

    def write_key(self, key: str, is_down: bool) -> bool:
        if type(key) is not str or key not in _KEYS or type(is_down) is not bool:
            return False
        if is_down:
            if self.failed or not self.backend.armed or not self.supervisor.alive:
                self.failed = True
                return False
            try:
                reserved = self.supervisor.reserve(key)
            except SupervisorUnavailable:
                self.failed = True
                return False
            if not self._healthy(reserved) or key not in reserved.get("possibleHeld", ()):
                self.failed = True
                return False
            # The parent SendInput call can itself run longer than the child
            # lease. If that late DOWN returns *after* the child already sent
            # emergency UP, immediately attempt a compensating local UP.
            # This reduces (not eliminates) a scheduler/OS race.
            inserted = self.backend.write_key(key, True) is True
            if not inserted:
                return False  # parent gate STOP still attempts the paired UP
            try:
                after = self.supervisor.renew()
            except SupervisorUnavailable:
                after = None
            if not self._healthy(after) or key not in after.get("possibleHeld", ()):
                self.failed = True
                self.backend.write_key(key, False)  # best-effort late-DOWN release
                return False
            return True

        # Key-up must remain available even after lease failure/focus loss.
        # The child forgets uncertainty ONLY after accepted OS key-up.
        inserted = self.backend.write_key(key, False) is True
        if not inserted:
            return False
        try:
            clear = self.supervisor.clear(key)
        except SupervisorUnavailable:
            self.failed = True
            return False
        if not self._healthy(clear):
            self.failed = True
            return False
        return key not in clear.get("possibleHeld", ())

    def stop(self) -> None:
        self.failed = True
        self.backend.disarm()
        try:
            self.supervisor.stop()
        except SupervisorUnavailable:
            pass  # independent TTL/EOF path still attempts child key-up
