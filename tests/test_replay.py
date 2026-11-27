"""Offline-only contract, provenance and metric regressions."""

from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import random
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rift_taxi.contracts import InputEvent, TraceError, load_trace
from rift_taxi.replay import Span, _turn_overlap, analyze, compare

ROOT = Path(__file__).resolve().parents[1]
STOP = ROOT / "samples" / "synthetic_stop_go.json"
CONTINUOUS = ROOT / "samples" / "synthetic_continuous.json"


class ContractTests(unittest.TestCase):
    def load_modified(self, modifier) -> None:
        doc = json.loads(STOP.read_text(encoding="utf-8"))
        modifier(doc)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "modified.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaises(TraceError):
                load_trace(path)

    def test_synthetic_contract_is_strict_and_has_destination(self):
        trace = load_trace(STOP)
        self.assertEqual(trace.source_type, "synthetic")
        self.assertEqual(trace.route_id, "three-bend-synthetic-course")
        self.assertEqual(trace.points[-1].kind, "destination")
        self.assertEqual(len(trace.points), 5)
        self.assertEqual(trace.verified_source_sha256, None)

    def test_reject_bad_frame(self):
        self.load_modified(lambda d: d["frame"].update({"upAxis": "z"}))

    def test_reject_nonfinite_number(self):
        self.load_modified(lambda d: d["poses"][0]["xyz"].__setitem__(0, float("nan")))

    def test_reject_wrong_source_type(self):
        self.load_modified(lambda d: d.update({"sourceType": "RR2"}))

    def test_reject_early_destination(self):
        self.load_modified(lambda d: d["route"]["points"][1].update({"kind": "destination"}))

    def test_reject_unordered_poses(self):
        self.load_modified(lambda d: d["poses"][2].update({"t": 0.3}))

    def test_reject_unordered_events(self):
        self.load_modified(lambda d: d["events"][2].update({"t": 0.9}))

    def test_reject_duplicate_key_down(self):
        def change(doc):
            doc["events"].insert(1, {"t": 0.1, "key": "W", "edge": "down"})
        self.load_modified(change)

    def test_reject_orphan_key_up(self):
        def change(doc):
            doc["events"].insert(0, {"t": 0, "key": "D", "edge": "up"})
        self.load_modified(change)

    def test_duplicate_trace_keys_are_refused_at_all_levels(self):
        raw = STOP.read_text(encoding="utf-8")
        for invalid in (raw.replace('"sourceType": "synthetic"',
                                    '"sourceType": "historical", "sourceType": "synthetic"', 1),
                        raw.replace('"upAxis": "y"', '"upAxis": "z", "upAxis": "y"', 1)):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "duplicate.json"
                path.write_text(invalid, encoding="utf-8")
                with self.assertRaisesRegex(TraceError, "duplicate JSON key"):
                    load_trace(path)

    def test_overflow_number_and_excessive_nesting_are_refused(self):
        raw = STOP.read_text(encoding="utf-8")
        for invalid in (raw.replace('"arrivalToleranceXZ": 0.3',
                                    '"arrivalToleranceXZ": 1e400', 1),
                        "["*2000 + "0" + "]"*2000):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "invalid.json"
                path.write_text(invalid, encoding="utf-8")
                with self.assertRaises(TraceError):
                    load_trace(path)

    def test_unhashable_source_type_is_a_contract_error(self):
        for value in ([], {}, None, True):
            with self.subTest(value=value):
                self.load_modified(lambda d: d.update(sourceType=value))

    def test_bounded_read_enforces_actual_read_length(self):
        from unittest.mock import patch, mock_open
        from rift_taxi.contracts import _read_bounded
        from types import SimpleNamespace
        # A file may grow between its initial stat and open. A limit+1
        # read detects that case without allocating the entire larger file.
        with patch.object(Path, "stat", return_value=SimpleNamespace(st_size=1, st_mode=0o100644)), \
                patch.object(Path, "open", mock_open(read_data=b"12345")) as opened:
            with self.assertRaisesRegex(TraceError, "bounded size"):
                _read_bounded(Path("fixture"), 4, "fixture")
            opened.return_value.read.assert_called_once_with(5)

    def test_missing_yaw_is_unavailable_not_zero(self):
        doc = json.loads(STOP.read_text(encoding="utf-8"))
        for sample in doc["poses"]:
            sample["actorYawDeg"] = None
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            result = analyze(load_trace(path))
            self.assertEqual(result["movement"]["actorYawAvailableSamples"], 0)

    def test_historical_source_hash_is_enforced_but_not_authenticated(self):
        doc = json.loads(STOP.read_text(encoding="utf-8"))
        doc["sourceType"] = "historical"
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.bin"
            original.write_bytes(b"local original bytes for integrity only")
            doc["source"] = {
                "repository": "RR2",
                "commit": "a" * 40,
                "originalFile": "original.bin",
                "sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
                "timeBasis": "single-monotonic",
            }
            trace_path = Path(directory) / "history.json"
            trace_path.write_text(json.dumps(doc), encoding="utf-8")
            trace = load_trace(trace_path)
            report = analyze(trace)
            self.assertEqual(report["trace"]["sourceIntegrity"], "submitted-source-sha256-match")
            self.assertFalse(report["trace"]["historicalAuthenticityEstablished"])
            self.assertFalse(report["arrival"]["liveArrivalVerified"])
            original.write_bytes(b"tampered")
            with self.assertRaisesRegex(TraceError, "SHA256 mismatch"):
                load_trace(trace_path)

    def test_reject_historical_source_escape(self):
        doc = json.loads(STOP.read_text(encoding="utf-8"))
        doc["sourceType"] = "historical"
        doc["source"] = {
            "repository": "RR2", "commit": "a" * 40,
            "originalFile": "../outside.bin", "sha256": "a" * 64,
            "timeBasis": "single-monotonic",
        }
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "bad.json"
            file.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaises(TraceError):
                load_trace(file)


class MetricTests(unittest.TestCase):
    def test_stop_go_counts_forward_releases_and_no_running_turns(self):
        report = analyze(load_trace(STOP))
        self.assertAlmostEqual(report["movement"]["forwardDutyRatio"], 4 / 5.2)
        self.assertEqual(report["movement"]["intermediateForwardReleases"], 3)
        self.assertEqual(report["movement"]["guideReleaseProxies"], 3)
        self.assertEqual(report["movement"]["turningWhileForwardIntervals"], 0)
        self.assertEqual(report["movement"]["turnDirectionAlternations"], 2)
        self.assertIsNone(report["movement"]["guideStopCountVerified"])
        self.assertTrue(report["arrival"]["withinDeclaredXZTolerance"])
        self.assertTrue(report["arrival"]["inputKeysReleasedByTraceEnd"])
        self.assertFalse(report["arrival"]["liveArrivalVerified"])

    def test_continuous_trace_has_w_held_during_turns(self):
        report = analyze(load_trace(CONTINUOUS))
        self.assertAlmostEqual(report["movement"]["forwardDutyRatio"], 1.0)
        self.assertEqual(report["movement"]["intermediateForwardReleases"], 0)
        self.assertEqual(report["movement"]["guideReleaseProxies"], 0)
        self.assertEqual(report["movement"]["turningWhileForwardIntervals"], 3)
        self.assertAlmostEqual(report["movement"]["turningWhileForwardSeconds"], 0.9)
        self.assertEqual(report["arrival"]["replayFinalXZError"], 0)

    def test_input_metrics_exclude_pre_and_post_window_activity(self):
        trace = replace(load_trace(CONTINUOUS), window_start=1., window_end=4.,
            events=tuple(InputEvent(t, key, edge) for t, key, edge in (
                (0., "W", "down"), (0., "D", "down"),
                (.4, "D", "up"), (.5, "W", "up"),
                (1., "W", "down"), (1.2, "A", "down"),
                (1.4, "A", "up"), (2., "W", "up"),
                (2.5, "W", "down"), (3., "D", "down"),
                (4., "W", "up"), (4.2, "D", "up"),
                (4.3, "A", "down"), (4.4, "W", "down"),
                (4.8, "A", "up"), (5., "W", "up"),
            )))
        result = analyze(trace)
        movement = result["movement"]
        self.assertAlmostEqual(movement["eligibleSeconds"], 3.)
        self.assertAlmostEqual(movement["forwardHeldSeconds"], 2.5)
        self.assertAlmostEqual(movement["turningWhileForwardSeconds"], 1.2)
        self.assertEqual(movement["turningWhileForwardIntervals"], 2)
        self.assertEqual(movement["turnDirectionAlternations"], 1)
        self.assertEqual(movement["intermediateForwardReleases"], 1)
        self.assertEqual(movement["inputMetricScope"], "declared-movement-window")
        self.assertEqual(movement["trajectoryMetricScope"], "full-observed-pose-timeline")
        self.assertTrue(result["arrival"]["inputKeysReleasedByTraceEnd"])
        self.assertFalse(result["arrival"]["liveArrivalVerified"])

    def test_held_turn_crosses_window_and_multiple_forward_spans(self):
        trace = replace(load_trace(CONTINUOUS), window_start=1., window_end=4.,
            events=tuple(InputEvent(t, key, edge) for t, key, edge in (
                (0., "A", "down"), (.5, "W", "down"), (1.5, "W", "up"),
                (2., "W", "down"), (2.5, "W", "up"), (3., "W", "down"),
                (4.5, "A", "up"), (5., "W", "up"),
            )))
        movement = analyze(trace)["movement"]
        self.assertAlmostEqual(movement["turningWhileForwardSeconds"], 2.)
        self.assertEqual(movement["turningWhileForwardIntervals"], 1)
        self.assertEqual(movement["intermediateForwardReleases"], 2)

    def test_release_at_window_start_is_not_intermediate_guide_release(self):
        trace = replace(load_trace(CONTINUOUS), window_start=1.3, window_end=4.,
            events=tuple(InputEvent(t, key, edge) for t, key, edge in (
                (0., "W", "down"), (1.3, "W", "up"),
                (1.4, "W", "down"), (4., "W", "up"),
            )))
        movement = analyze(trace)["movement"]
        self.assertEqual(movement["intermediateForwardReleases"], 0)
        self.assertEqual(movement["guideReleaseProxies"], 0)

    def test_sweep_matches_pairwise_oracle_on_seeded_intervals(self):
        rng = random.Random(20261123)
        def spans():
            result = []
            cursor = 0.
            for _ in range(rng.randrange(0, 60)):
                left = cursor + rng.random()
                right = left + rng.random()
                result.append(Span(left, right))
                cursor = right
            return result
        for _ in range(100):
            forward, turns = spans(), spans()
            start = rng.uniform(0., 20.)
            end = start + rng.uniform(.01, 30.)
            amounts = [
                sum(max(0., min(w.end, t.end, end) - max(w.start, t.start, start))
                    for w in forward) for t in turns
            ]
            seconds, count = _turn_overlap(forward, turns, start, end)
            self.assertAlmostEqual(seconds, sum(amounts), places=10)
            self.assertEqual(count, sum(a > 0. for a in amounts))

    def test_compare_same_route_reports_delta_without_live_claim(self):
        report = compare(load_trace(STOP), load_trace(CONTINUOUS))
        self.assertEqual(report["classification"], "OFFLINE_REPLAY_ONLY")
        self.assertLess(report["rightMinusLeft"]["intermediateForwardReleases"], 0)
        self.assertGreater(report["rightMinusLeft"]["forwardDutyRatio"], 0)
        self.assertGreater(report["rightMinusLeft"]["turningWhileForwardSeconds"], 0)

    def test_refuse_comparison_of_different_routes(self):
        doc = json.loads(CONTINUOUS.read_text(encoding="utf-8"))
        doc["route"]["id"] = "unrelated"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "other.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "identical route"):
                compare(load_trace(STOP), load_trace(path))

    def test_unreleased_input_is_reported_not_silently_released(self):
        doc = json.loads(CONTINUOUS.read_text(encoding="utf-8"))
        doc["events"] = doc["events"][:-1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unreleased.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            result = analyze(load_trace(path))
            self.assertFalse(result["arrival"]["inputKeysReleasedByTraceEnd"])
            self.assertEqual(result["arrival"]["keysStillHeldAtTraceEnd"], ["W"])


class CliTests(unittest.TestCase):
    def invoke(self, *args: str):
        return subprocess.run(
            [sys.executable, "-m", "rift_taxi", *args],
            cwd=ROOT, text=True, capture_output=True, check=False, timeout=20,
        )

    def test_offline_doctor_does_not_select_game(self):
        r = self.invoke("doctor")
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = json.loads(r.stdout)
        self.assertFalse(doc["gameInputEnabled"])
        self.assertFalse(doc["nativeReaderImplemented"])
        self.assertFalse(doc["siblingRepositoryRequired"])

    def test_cli_replay_and_compare(self):
        a = self.invoke("replay", str(STOP))
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(json.loads(a.stdout)["classification"], "OFFLINE_REPLAY_ONLY")
        b = self.invoke("compare", str(STOP), str(CONTINUOUS))
        self.assertEqual(b.returncode, 0, b.stderr)
        self.assertEqual(json.loads(b.stdout)["schema"], "taxi.replay-comparison/1")

    def test_cli_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "metrics.json"
            one = self.invoke("replay", str(STOP), "--out", str(target))
            two = self.invoke("replay", str(STOP), "--out", str(target))
            self.assertEqual(one.returncode, 0, one.stderr)
            self.assertEqual(two.returncode, 2)
            self.assertIn("overwrite", two.stderr)
