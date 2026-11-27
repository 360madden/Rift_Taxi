"""Deterministic M1 driver-neutral held-input and fail-closed regression tests."""
from __future__ import annotations

from dataclasses import replace
import math
import time
import unittest

from rift_taxi.control import (
    ControlRefused, HeldInputController, LivePose, SessionBinding,
)


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class RecordingBackend:
    """Offline fake; accepts events but has no OS or game connection."""

    def __init__(self) -> None:
        self.events: list[tuple[str, bool]] = []
        self.reject: set[tuple[str, bool]] = set()
        self.raise_on: set[tuple[str, bool]] = set()

    def write_key(self, key: str, is_down: bool) -> bool:
        self.events.append((key, is_down))
        if (key, is_down) in self.raise_on:
            raise RuntimeError("simulated backend failure")
        return (key, is_down) not in self.reject


def session() -> SessionBinding:
    return SessionBinding(
        host="LEGION", process_id=1234, start_ticks=123456789,
        executable_sha256="a" * 64, window_handle=301, actor_id="Atank",
        zone_id="SanctumWatch",
    )


def pose(clock: Clock, *, sequence: int = 1, session_id: SessionBinding | None = None,
         foreground: bool = True, yaw_verified: bool = True) -> LivePose:
    return LivePose(
        session=session_id or session(), sequence=sequence,
        observed_monotonic_s=clock(), xyz=(1.0, 2.0, 3.0),
        actor_yaw_deg=90.0, actor_yaw_verified=yaw_verified,
        foreground_verified=foreground,
    )


class GateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.backend = RecordingBackend()
        self.controller = HeldInputController(
            session(), self.backend, clock=self.clock, max_pose_age_s=.20,
            max_hold_s=.40,
        )
        self.addCleanup(self.controller.close)

    def test_continuous_w_overlapping_steer_and_no_guide_release(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        self.clock.advance(.05)
        self.controller.apply(("W", "D"), pose(self.clock, sequence=2))
        self.clock.advance(.05)
        self.controller.apply(("W",), pose(self.clock, sequence=3))
        self.assertEqual(
            self.backend.events,
            [("W", True), ("D", True), ("D", False)],
        )
        self.assertFalse(self.controller.status.stop_latched)
        self.assertFalse(self.controller.status.game_response_verified)

    def test_direction_reversal_releases_first(self) -> None:
        self.controller.apply(("W", "D"), pose(self.clock))
        self.clock.advance(.05)
        self.controller.apply(("W", "A"), pose(self.clock, sequence=2))
        self.assertEqual(self.backend.events[-2:], [("D", False), ("A", True)])
        self.assertNotIn(("W", False), self.backend.events)

    def test_stop_latches_and_repeat_stop_is_idempotent(self) -> None:
        self.controller.apply(("W", "D"), pose(self.clock))
        status = self.controller.stop("manual")
        self.assertTrue(status.stop_latched)
        self.assertEqual(status.stop_reason, "manual")
        self.assertEqual(status.potentially_held_keys, ())
        count = len(self.backend.events)
        self.controller.stop("second-stop")
        self.assertEqual(len(self.backend.events), count)
        with self.assertRaisesRegex(ControlRefused, "STOP latched"):
            self.controller.apply(("W",), pose(self.clock, sequence=2))

    def test_malformed_stop_reason_cannot_prevent_release(self) -> None:
        class UnexpectedText(str):
            def strip(self):
                raise AssertionError("caller text hook must not run")

        # All callbacks record inert edges. No actual input is sent.
        for reason in (None, True, "", " ", " padded ", UnexpectedText("stop")):
            with self.subTest(reason=reason):
                clock, backend = Clock(), RecordingBackend()
                with HeldInputController(session(), backend, clock=clock) as gate:
                    gate.apply(("W", "D"), pose(clock))
                    with self.assertRaisesRegex(ValueError, "reason"):
                        gate.stop(reason)
                    self.assertEqual(gate.status.stop_reason, "invalid-stop-reason")
                    self.assertTrue(gate.status.stop_latched)
                    self.assertEqual(gate.status.potentially_held_keys, ())
                    self.assertEqual(backend.events,
                        [("W", True), ("D", True), ("D", False), ("W", False)])

    def test_invalid_stop_label_retries_uncertain_release(self) -> None:
        self.controller.apply(("W", "A"), pose(self.clock))
        self.backend.reject.add(("A", False))
        first = self.controller.stop("manual-stop")
        self.assertEqual(first.potentially_held_keys, ("A",))
        self.backend.reject.clear()
        with self.assertRaises(ValueError):
            self.controller.stop(None)
        self.assertEqual(self.controller.status.potentially_held_keys, ())
        self.assertEqual(self.controller.status.stop_reason, "manual-stop")
        self.assertTrue(self.controller.status.backend_release_fault_observed)

    def test_request_subclass_refused_without_iteration(self) -> None:
        invoked = []
        class CustomList(list):
            def __iter__(self):
                invoked.append(True)
                return super().__iter__()

        self.controller.apply(("W",), pose(self.clock))
        with self.assertRaisesRegex(ControlRefused, "finite collection"):
            self.controller.apply(CustomList(["W", "D"]), pose(self.clock))
        self.assertEqual(invoked, [])
        self.assertEqual(self.backend.events, [("W", True), ("W", False)])
        self.assertTrue(self.controller.status.stop_latched)

    def test_oversized_key_collection_refused_and_released(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        with self.assertRaisesRegex(ControlRefused, "exceeds bound"):
            self.controller.apply(["W"] * 4, pose(self.clock))
        self.assertEqual(self.backend.events, [("W", True), ("W", False)])
        self.assertTrue(self.controller.status.stop_latched)

    def test_builtin_request_snapshot_preserves_set_semantics(self) -> None:
        first = pose(self.clock)
        self.controller.apply(["W", "W"], first)
        self.controller.apply({"W", "D"}, first)
        self.controller.apply(frozenset(("W",)), first)
        self.assertEqual(self.backend.events,
                         [("W", True), ("D", True), ("D", False)])

    def test_lease_expiry_releases_without_steering_loop(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        self.clock.advance(.41)
        status = self.controller.check_expiry()
        self.assertTrue(status.stop_latched)
        self.assertEqual(status.stop_reason, "pose-expired")
        self.assertIn(("W", False), self.backend.events)

    def test_pose_expiry_dominates_lease(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        self.clock.advance(.21)
        self.assertEqual(self.controller.check_expiry().stop_reason, "pose-expired")

    def test_stale_pose_refuses_and_releases(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        stale = pose(self.clock, sequence=2)
        self.clock.advance(.25)
        with self.assertRaisesRegex(ControlRefused, "stale|pose-expired"):
            self.controller.apply(("W",), stale)
        self.assertEqual(self.controller.status.potentially_held_keys, ())

    def test_new_process_epoch_rejects_and_releases(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        different = replace(session(), start_ticks=123456790)
        with self.assertRaisesRegex(ControlRefused, "identity changed"):
            self.controller.apply(("W",), pose(self.clock, sequence=2, session_id=different))
        self.assertTrue(self.controller.status.stop_latched)

    def test_zone_or_actor_change_is_rejected(self) -> None:
        for changed in (replace(session(), zone_id="Elsewhere"),
                        replace(session(), actor_id="SomeoneElse")):
            clock, backend = Clock(), RecordingBackend()
            with HeldInputController(session(), backend, clock=clock) as gate:
                with self.assertRaisesRegex(ControlRefused, "identity changed"):
                    gate.apply(("W",), pose(clock, session_id=changed))
                self.assertEqual(backend.events, [])

    def test_focus_loss_releases_and_latches(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        self.clock.advance(.01)
        with self.assertRaisesRegex(ControlRefused, "foreground"):
            self.controller.apply(("W",), pose(self.clock, sequence=2, foreground=False))
        self.assertTrue(self.controller.status.stop_latched)

    def test_unqualified_actor_yaw_fails_closed(self) -> None:
        with self.assertRaisesRegex(ControlRefused, "yaw"):
            self.controller.apply(("W",), pose(self.clock, yaw_verified=False))
        self.assertEqual(self.backend.events, [])

    def test_duplicate_sample_reuse_allowed_only_within_age(self) -> None:
        first = pose(self.clock)
        self.controller.apply(("W",), first)
        self.clock.advance(.08)
        self.controller.apply(("W",), first)
        self.assertEqual(self.backend.events, [("W", True)])
        self.clock.advance(.13)
        with self.assertRaisesRegex(ControlRefused, "stale|pose-expired"):
            self.controller.apply(("W",), first)
        self.assertTrue(self.controller.status.stop_latched)

    def test_contradictory_duplicate_sequence_fails(self) -> None:
        previous = pose(self.clock)
        self.controller.apply(("W",), previous)
        with self.assertRaisesRegex(ControlRefused, "contradictory"):
            self.controller.apply(("W",), replace(previous, xyz=(3, 4, 5)))
        self.assertEqual(self.controller.status.potentially_held_keys, ())

    def test_rollback_sequence_latches_stop(self) -> None:
        self.controller.apply(("W",), pose(self.clock, sequence=3))
        with self.assertRaisesRegex(ControlRefused, "rolled backward"):
            self.controller.apply(("W",), pose(self.clock, sequence=2))

    def test_sequence_increment_without_new_timestamp_is_rejected(self) -> None:
        self.controller.apply(("W",), pose(self.clock, sequence=1))
        with self.assertRaisesRegex(ControlRefused, "timestamp failed to advance"):
            self.controller.apply(("W",), pose(self.clock, sequence=2))
        self.assertTrue(self.controller.status.stop_latched)
        self.assertIn(("W", False), self.backend.events)

    def test_clock_future_pose_rejected_and_released(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        self.clock.advance(.05)
        future = replace(pose(self.clock, sequence=2), observed_monotonic_s=1000)
        with self.assertRaisesRegex(ControlRefused, "different clock"):
            self.controller.apply(("W",), future)
        self.assertTrue(self.controller.status.stop_latched)

    def test_conflicting_turns_never_sent(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        with self.assertRaisesRegex(ControlRefused, "contradictory"):
            self.controller.apply(("W", "A", "D"), pose(self.clock, sequence=2))
        self.assertNotIn(("A", True), self.backend.events)
        self.assertNotIn(("D", True), self.backend.events)

    def test_bad_keys_never_sent(self) -> None:
        with self.assertRaises(ControlRefused):
            self.controller.apply(("W", "SPACE"), pose(self.clock))
        self.assertEqual(self.backend.events, [])

    def test_failed_key_down_triggers_recovery_up_and_stop(self) -> None:
        self.backend.reject.add(("W", True))
        with self.assertRaisesRegex(ControlRefused, "backend-press-rejected"):
            self.controller.apply(("W",), pose(self.clock))
        self.assertEqual(self.backend.events, [("W", True), ("W", False)])
        self.assertEqual(self.controller.status.potentially_held_keys, ())
        self.assertTrue(self.controller.status.stop_latched)

    def test_exception_on_key_down_treated_as_uncertain(self) -> None:
        self.backend.raise_on.add(("W", True))
        with self.assertRaises(ControlRefused):
            self.controller.apply(("W",), pose(self.clock))
        self.assertEqual(self.backend.events, [("W", True), ("W", False)])

    def test_rejected_release_preserves_uncertain_key_and_stop_retries(self) -> None:
        self.controller.apply(("W", "D"), pose(self.clock))
        self.clock.advance(.01)
        self.backend.reject.add(("D", False))
        with self.assertRaisesRegex(ControlRefused, "backend-release-rejected"):
            self.controller.apply(("W", "A"), pose(self.clock, sequence=2))
        self.assertTrue(self.controller.status.backend_release_fault_observed)
        self.assertIn("D", self.controller.status.potentially_held_keys)
        self.assertNotIn(("A", True), self.backend.events)
        self.backend.reject.clear()
        self.assertEqual(self.controller.stop().potentially_held_keys, ())
        with self.assertRaises(ControlRefused):
            self.controller.apply(("W",), pose(self.clock, sequence=3))

    def test_no_fake_verification_when_all_up_accepted(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        self.assertFalse(self.controller.stop().game_response_verified)

    def test_close_stops_input(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        self.controller.close()
        self.assertEqual(self.controller.status.potentially_held_keys, ())
        with self.assertRaises(ControlRefused):
            self.controller.apply(("W",), pose(self.clock))

    def test_invalid_contract_values(self) -> None:
        with self.assertRaises(ValueError):
            replace(session(), process_id=0)
        with self.assertRaises(ValueError):
            replace(session(), executable_sha256="bad")
        with self.assertRaises(ValueError):
            replace(session(), actor_id=" ")
        with self.assertRaises(ValueError):
            replace(pose(self.clock), actor_yaw_deg=float("nan"))
        with self.assertRaises(ValueError):
            replace(pose(self.clock), observed_monotonic_s=float("inf"))
        with self.assertRaises(ValueError):
            replace(pose(self.clock), xyz=(1, math.inf, 3))
        with self.assertRaises(ValueError):
            replace(pose(self.clock), actor_yaw_verified=1)


    def test_background_watchdog_releases_without_control_loop(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        self.clock.advance(.25)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and ("W", False) not in self.backend.events:
            time.sleep(.01)
        self.assertIn(("W", False), self.backend.events)
        self.assertTrue(self.controller.status.stop_latched)
        self.assertEqual(self.controller.status.stop_reason, "pose-expired")

    def test_lease_expiry_without_pose_expiry(self) -> None:
        clock, backend = Clock(), RecordingBackend()
        with HeldInputController(session(), backend, clock=clock,
                                 max_pose_age_s=.80, max_hold_s=.10) as gate:
            gate.apply(("W",), pose(clock))
            clock.advance(.11)
            result = gate.check_expiry()
            self.assertEqual(result.stop_reason, "lease-expired")
            self.assertEqual(result.potentially_held_keys, ())

    def test_string_is_not_a_movement_key_collection(self) -> None:
        with self.assertRaisesRegex(ControlRefused, "finite collection"):
            self.controller.apply("WA", pose(self.clock))
        self.assertEqual(self.backend.events, [])
        self.assertTrue(self.controller.status.stop_latched)

    def test_unbounded_iterable_not_evaluated(self) -> None:
        def bad():
            raise AssertionError("generator must never be iterated")
            yield "W"
        with self.assertRaisesRegex(ControlRefused, "finite collection"):
            self.controller.apply(bad(), pose(self.clock))
        self.assertEqual(self.backend.events, [])

    def test_pose_xyz_must_be_immutable(self) -> None:
        with self.assertRaisesRegex(ValueError, "xyz"):
            replace(pose(self.clock), xyz=[1, 2, 3])

    def test_slow_guard_cannot_authorize_a_stale_pose(self) -> None:
        def slow_renew():
            self.clock.advance(.21)
            return True
        self.backend.renew_guard = slow_renew
        with self.assertRaisesRegex(ControlRefused, "stale"):
            self.controller.apply(("W",), pose(self.clock))
        self.assertEqual(self.backend.events, [])
        self.assertTrue(self.controller.status.stop_latched)

    def test_slow_guard_cannot_resurrect_prior_lease(self) -> None:
        clock, backend = Clock(), RecordingBackend()
        with HeldInputController(session(), backend, clock=clock,
                                  max_pose_age_s=.8, max_hold_s=.10) as gate:
            gate.apply(("W",), pose(clock))
            clock.advance(.08)
            def slow_renew():
                clock.advance(.03)
                return True
            backend.renew_guard = slow_renew
            with self.assertRaisesRegex(ControlRefused, "lease-expired"):
                gate.apply(("W", "D"), pose(clock, sequence=2))
            self.assertEqual(backend.events, [("W", True), ("W", False)])
            self.assertEqual(gate.status.potentially_held_keys, ())

    def test_initial_guard_cannot_outlive_action_lease(self) -> None:
        clock, backend = Clock(), RecordingBackend()
        with HeldInputController(session(), backend, clock=clock,
                                  max_pose_age_s=.8, max_hold_s=.10) as gate:
            def slow_renew():
                clock.advance(.11)
                return True
            backend.renew_guard = slow_renew
            with self.assertRaisesRegex(ControlRefused, "action-lease-expired"):
                gate.apply(("W",), pose(clock))
            self.assertEqual(backend.events, [])

    def test_late_accepted_down_releases_and_blocks_second_down(self) -> None:
        write = self.backend.write_key
        def slow_write(key, down):
            if down:
                self.clock.advance(.21)
            return write(key, down)
        self.backend.write_key = slow_write
        with self.assertRaisesRegex(ControlRefused, "pose-expired"):
            self.controller.apply(("W", "D"), pose(self.clock))
        self.assertEqual(self.backend.events, [("W", True), ("W", False)])
        self.assertEqual(self.controller.status.potentially_held_keys, ())
        self.assertTrue(self.controller.status.stop_latched)

    def test_slow_turn_release_blocks_reversal(self) -> None:
        self.controller.apply(("W", "D"), pose(self.clock))
        self.clock.advance(.01)
        write = self.backend.write_key
        def slow_write(key, down):
            if (key, down) == ("D", False):
                self.clock.advance(.21)
            return write(key, down)
        self.backend.write_key = slow_write
        with self.assertRaisesRegex(ControlRefused, "pose-expired"):
            self.controller.apply(("W", "A"), pose(self.clock, sequence=2))
        self.assertEqual(self.backend.events, [
            ("W", True), ("D", True), ("D", False), ("W", False),
        ])
        self.assertEqual(self.controller.status.potentially_held_keys, ())

    def test_clock_rollback_and_nonfinite_release_held_keys(self) -> None:
        for invalid in (99.0, float("nan"), float("inf"), -1.0, True):
            with self.subTest(invalid=invalid):
                clock, backend = Clock(), RecordingBackend()
                with HeldInputController(session(), backend, clock=clock) as gate:
                    gate.apply(("W", "A"), pose(clock))
                    clock.t = invalid
                    status = gate.check_expiry()
                    self.assertEqual(status.stop_reason, "controller-clock-invalid")
                    self.assertEqual(status.potentially_held_keys, ())
                    self.assertEqual(backend.events[-2:], [("A", False), ("W", False)])

    def test_raising_clock_does_not_prevent_stop_or_close(self) -> None:
        for method in ("stop", "close", "check_expiry"):
            with self.subTest(method=method):
                clock, backend = Clock(), RecordingBackend()
                def read():
                    if clock.t < 0:
                        raise OSError("simulated clock failure")
                    return clock()
                with HeldInputController(session(), backend, clock=read) as gate:
                    gate.apply(("W",), pose(clock))
                    clock.t = -1
                    getattr(gate, method)()
                    self.assertEqual(backend.events, [("W", True), ("W", False)])
                    self.assertTrue(gate.status.stop_latched)
                    self.assertEqual(gate.status.potentially_held_keys, ())

    def test_background_watchdog_handles_clock_failure(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        self.clock.t = float("nan")
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and ("W", False) not in self.backend.events:
            time.sleep(.01)
        self.assertIn(("W", False), self.backend.events)
        self.assertEqual(self.controller.status.stop_reason, "controller-clock-invalid")

    def test_release_exception_retains_uncertainty_until_retry(self) -> None:
        self.controller.apply(("W",), pose(self.clock))
        self.backend.raise_on.add(("W", False))
        result = self.controller.stop()
        self.assertIn("W", result.potentially_held_keys)
        self.assertTrue(result.backend_release_fault_observed)
        self.backend.raise_on.clear()
        self.assertEqual(self.controller.stop().potentially_held_keys, ())
        self.assertTrue(self.controller.status.stop_latched)


if __name__ == "__main__":
    unittest.main()
