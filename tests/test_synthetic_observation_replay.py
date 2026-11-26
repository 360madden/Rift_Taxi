"""Regression tests for synthetic packet transport and real inert gate expiry."""
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.synthetic_observation_replay import (
    DT, TICKS, ROUTES, delivery_tick, truth_frames, replay, evaluate,
)


class ObservationReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluate()

    def test_fixed_design_and_packet_accounting(self):
        self.assertEqual(self.report["caseCount"], 28)
        self.assertFalse(self.report["gameInputSent"])
        for row in self.report["rows"]:
            self.assertEqual(row["captured"], TICKS)
            self.assertEqual(row["delivered"] + row["dropped"] +
                             row["pendingBeyondWindow"], TICKS)
            self.assertEqual(len(row["packets"]), row["delivered"])
            for p in row["packets"]:
                self.assertGreaterEqual(p["deliveryTick"], p["captureTick"])
                self.assertEqual(p["sequence"], p["captureTick"]+1)
                self.assertEqual(p["ageSeconds"], (p["deliveryTick"]-p["captureTick"])*DT)

    def test_fresh_and_short_gap_do_not_stop(self):
        for row in self.report["rows"]:
            if row["profile"] in ("immediate", "steady-delay",
                                   "jitter-in-order", "short-dropout"):
                self.assertFalse(row["faultStop"], row["profile"])
                self.assertEqual(row["acceptedPackets"], row["delivered"])
                self.assertEqual(row["finalHeldKeys"], ["W", "A"])

    def test_expiry_and_reordered_packets_latch(self):
        for row in self.report["rows"]:
            expected = {"long-dropout": (25, "pose-expired"),
                        "out-of-order": (23, "pose sequence rolled backward"),
                        "stale-stream": (6, "pose is stale or from a different clock")}
            if row["profile"] in expected:
                tick, reason = expected[row["profile"]]
                self.assertTrue(row["faultStop"])
                self.assertEqual(row["firstStop"]["tick"], tick)
                self.assertEqual(row["firstStop"]["stopReason"], reason)
                self.assertEqual(row["finalHeldKeys"], [])
                self.assertGreater(row["refusedAfterStop"], 0)
                self.assertTrue(all(not s["heldKeys"] for s in
                                    row["tickStates"][tick:]))
                if row["profile"] != "stale-stream":
                    self.assertEqual({e["key"] for e in row["edges"] if not e["is_down"]},
                                     {"W", "A"})
                else:
                    self.assertEqual(row["edges"], [])

    def test_error_uses_capture_and_delivery_truth(self):
        for row in self.report["rows"]:
            if row["profile"] == "immediate":
                self.assertEqual(row["maxDeliveryPositionErrorXZ"], 0.)
                self.assertEqual(row["maxDeliveryYawErrorDegrees"], 0.)
            elif row["profile"] == "steady-delay":
                self.assertEqual(row["maxDeliveryAgeSeconds"], 2*DT)
                self.assertGreater(row["maxDeliveryPositionErrorXZ"], 0.)

    def test_transport_out_of_order_is_retained(self):
        self.assertEqual(delivery_tick(20, "out-of-order"), 23)
        self.assertEqual(delivery_tick(21, "out-of-order"), 21)
        self.assertIsNone(delivery_tick(21, "short-dropout"))
        with self.assertRaises(TraceError):
            delivery_tick(0, "unknown")
        with self.assertRaises(TraceError):
            delivery_tick(True, "immediate")

    def test_repeated_report_is_deterministic(self):
        self.assertEqual(self.report, evaluate())

    def test_invalid_truth_window_refused(self):
        name, points = ROUTES[0]
        _, frames = truth_frames(name, points, speed=2.5)
        with self.assertRaises(TraceError):
            replay(frames[:-1], "immediate")

    def test_gaps_are_visible_even_when_delivered_packets_are_fresh(self):
        for row in self.report["rows"]:
            if row["profile"] == "short-dropout":
                self.assertEqual(row["maxDeliveryAgeSeconds"], 0.)
                self.assertEqual(row["maxPreDeliveryObservationAgeSeconds"], 4*DT)
                self.assertEqual(row["maxHeldPoseAgeSeconds"], 3*DT)
                self.assertGreater(row["maxHeldPosePositionErrorXZ"], 0.)
            elif row["profile"] == "long-dropout":
                self.assertEqual(row["maxPreDeliveryObservationAgeSeconds"], 10*DT)
                self.assertEqual(row["maxHeldPoseAgeSeconds"], 5*DT)
            elif row["profile"] == "stale-stream":
                self.assertIsNone(row["maxHeldPoseAgeSeconds"])
                self.assertIsNone(row["maxHeldPosePositionErrorXZ"])

    def test_truth_digest_binds_the_profile_independent_of_delivery(self):
        groups = {}
        for row in self.report["rows"]:
            groups.setdefault((row["route"], row["speed"]), set()).add(row["truthPrefixSHA256"])
        self.assertEqual(len(groups), 4)
        self.assertTrue(all(len(digests) == 1 for digests in groups.values()))
        self.assertEqual(len(set().union(*groups.values())), 4)
