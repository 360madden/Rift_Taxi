"""Synthetic-only Pure Pursuit geometry and heading-preview tests."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rift_taxi.contracts import TraceError, load_trace
from rift_taxi.steering import _angle_delta, preview_steering

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "samples" / "synthetic_continuous.json"


class SteeringPreviewTests(unittest.TestCase):
    def modified(self, modifier):
        doc = json.loads(SYNTHETIC.read_text(encoding="utf-8"))
        modifier(doc)
        return doc

    def preview_document(self, doc):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "trace.json"
            p.write_text(json.dumps(doc), encoding="utf-8")
            return preview_steering(load_trace(p))

    def test_heading_and_corners_use_forward_intent_without_keys(self):
        result = preview_steering(load_trace(SYNTHETIC), lookahead=2)
        frames = result["frames"]
        self.assertFalse(result["gameInputSent"])
        self.assertEqual(result["classification"], "SYNTHETIC_GEOMETRY_ONLY")
        self.assertEqual(frames[0]["turnIntent"], "none")
        self.assertEqual(frames[1]["turnIntent"], "positive-yaw")
        self.assertTrue(frames[1]["forwardIntent"])
        self.assertEqual(frames[2]["turnIntent"], "none")
        self.assertEqual(frames[3]["turnIntent"], "positive-yaw")
        self.assertFalse(frames[4]["forwardIntent"])
        self.assertEqual(frames[4]["arrivalCondition"], "synthetic-position-only")
        self.assertTrue(all(frames[i]["progress"] <= frames[i+1]["progress"]
                            for i in range(len(frames)-1)))

    def test_never_accept_historical_real_movement_trace_for_steering(self):
        doc = self.modified(lambda x: x["frame"].update({"frameId": "rift-native-xyz-candidate"}))
        with self.assertRaisesRegex(TraceError, "synthetic-local"):
            self.preview_document(doc)

    def test_missing_actor_yaw_fails_without_zero_substitution(self):
        def mutate(doc):
            doc["poses"][1]["actorYawDeg"] = None
        with self.assertRaisesRegex(TraceError, "actor yaw"):
            self.preview_document(self.modified(mutate))

    def test_hard_stops_and_mandatory_regions_not_silently_skipped(self):
        for kind in ("hard_stop", "mandatory_passage"):
            def mutate(doc):
                doc["route"]["points"][1]["kind"] = kind
            with self.assertRaisesRegex(TraceError, "constraint controller"):
                self.preview_document(self.modified(mutate))

    def test_wraparound_angles(self):
        self.assertAlmostEqual(_angle_delta(-179, 179), 2)
        self.assertAlmostEqual(_angle_delta(179, -179), -2)

    def test_bad_lookahead_refused(self):
        trace = load_trace(SYNTHETIC)
        for lookahead in (-1, 0, float("inf"), float("nan")):
            with self.assertRaises(TraceError):
                preview_steering(trace, lookahead=lookahead)

    def test_cli_emits_synthetic_preview_without_game_use(self):
        result = subprocess.run(
            [sys.executable, "-m", "rift_taxi", "preview-steering", str(SYNTHETIC)],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = json.loads(result.stdout)
        self.assertFalse(doc["gameInputSent"])
        self.assertEqual(doc["algorithm"], "pure-pursuit-lookahead-heading")


if __name__ == "__main__":
    unittest.main()
