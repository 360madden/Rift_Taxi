"""Synthetic-only Pure Pursuit geometry and heading-preview tests."""

from __future__ import annotations

import json
from dataclasses import replace
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from rift_taxi.contracts import Point, PoseSample, TraceError, load_trace
from rift_taxi.steering import _angle_delta, _project, _segments, _lookahead_point, preview_steering

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

    def route_trace(self, vertices, positions):
        """Build a synthetic route and observations without a live client."""
        trace = load_trace(SYNTHETIC)
        points = tuple(Point(str(i), "destination" if i == len(vertices)-1 else "guide", xyz)
                       for i, xyz in enumerate(vertices))
        poses = tuple(PoseSample(float(i), xyz, 0.) for i, xyz in enumerate(positions))
        return replace(trace, points=points, poses=poses)

    @staticmethod
    def full_scan_projection(points, cumulative, position, low, high):
        """Frozen pre-optimization oracle: visit every segment in route order.

        Deliberately independent of bisect and of the shared projector. Keep
        the original floating-point operations so a change in candidate
        selection, clipping or tie behavior fails exact tuple comparison.
        """
        candidates = []
        for i, (a, b) in enumerate(zip(points, points[1:])):
            length = cumulative[i + 1] - cumulative[i]
            if length <= 1e-12 or cumulative[i + 1] < low or cumulative[i] > high:
                continue
            left = max(0., (low - cumulative[i]) / length)
            right = min(1., (high - cumulative[i]) / length)
            if left > right:
                continue
            dx, dz = b.xyz[0] - a.xyz[0], b.xyz[2] - a.xyz[2]
            fraction = ((position[0] - a.xyz[0]) * dx + (position[2] - a.xyz[2]) * dz) / (length * length)
            fraction = max(left, min(right, fraction))
            x, z = a.xyz[0] + fraction * dx, a.xyz[2] + fraction * dz
            candidates.append((math.hypot(position[0] - x, position[2] - z), cumulative[i] + fraction * length))
        if not candidates:
            raise TraceError("no admissible synthetic projection")
        error, progress = min(candidates)
        return max(low, min(high, progress)), error

    def test_indexed_projection_preserves_original_full_scan_exactly(self):
        # Include equal vertex arcs, repeated geometry, exact vertex bounds,
        # full-route and stationary windows. The public preview rejects
        # degenerate geometry; the shared primitive must nevertheless retain
        # the original behavior around equal cumulative entries.
        rng = random.Random(20261124)
        for case in range(100):
            vertices = [(0., 0., 0.), (1., 0., 0.)]
            vertices += [(float(rng.randint(-5, 5)), 0., float(rng.randint(-5, 5)))
                         for _ in range(rng.randint(2, 30))]
            vertices.extend((vertices[-1], vertices[0]))
            points = self.route_trace(tuple(vertices), (vertices[0], vertices[1])).points
            cumulative, total = _segments(points)
            intervals = [(0., 0.), (total, total), (0., total)]
            for _ in range(6):
                a = rng.choice(cumulative)
                intervals.append((a, a))
                intervals.append(tuple(sorted((a, rng.uniform(0., total)))))
            for low, high in intervals:
                position = (rng.uniform(-6., 6.), 0., rng.uniform(-6., 6.))
                with self.subTest(case=case, low=low, high=high):
                    expected = self.full_scan_projection(points, cumulative, position, low, high)
                    self.assertEqual(_project(points, cumulative, position, low, high), expected)

    def test_indexed_projection_uses_earliest_arc_at_identical_crossing(self):
        vertices = ((0., 0., 0.), (4., 0., 0.), (0., 0., 0.), (4., 0., 0.))
        points = self.route_trace(vertices, vertices).points
        cumulative, total = _segments(points)
        # Three visits to the same point; only the earliest *eligible* one
        # wins. No nearest-segment shortcut is allowed to prefer the last.
        self.assertEqual(_project(points, cumulative, (2., 0., 0.), 0., total), (2., 0.))
        self.assertEqual(_project(points, cumulative, (2., 0., 0.), 4., total), (6., 0.))

    @staticmethod
    def full_scan_lookahead(points, cumulative, along):
        """Frozen pre-index reference; preserve the first eligible arc tie."""
        if along >= cumulative[-1]:
            return points[-1].xyz
        for i in range(len(points)-1):
            if along > cumulative[i+1]:
                continue
            distance = cumulative[i+1]-cumulative[i]
            if distance <= 1e-12:
                continue
            portion=(along-cumulative[i])/distance
            a,b=points[i].xyz,points[i+1].xyz
            return tuple(start+portion*(finish-start) for start,finish in zip(a,b))
        return points[-1].xyz

    def test_indexed_lookahead_preserves_exact_full_scan_arithmetic(self):
        rng=random.Random(20261127)
        # Include both sides of the small-route threshold, equal arc
        # coordinates with differing height, near-zero segments and every
        # vertex boundary. No approximation tolerance hides changed ties.
        for n in (2,5,8,9,16,50,500):
            for _ in range(5):
                vertices=[(0.,0.,0.),(1.,1.,0.)]
                while len(vertices)<n:
                    x,y,z=vertices[-1]
                    vertices.append((x+rng.choice((0.,1e-13,1.,3.)),
                                     y+rng.uniform(-3.,3.),
                                     z+rng.choice((0.,0.,2.))))
                points=tuple(Point(str(i),"destination" if i==n-1 else "guide",xyz)
                             for i,xyz in enumerate(vertices))
                cumulative,total=_segments(points)
                queries=[*cumulative,-.5,total+.5]
                queries.extend(rng.uniform(0.,total) for _ in range(40))
                for q in queries:
                    self.assertEqual(_lookahead_point(points,cumulative,q),
                                     self.full_scan_lookahead(points,cumulative,q))

    def test_exact_vertex_uses_earlier_segment_before_vertical_duplicate(self):
        vertices=((0.,0.,0.),(1.,2.,0.),(1.,99.,0.),
                  *((float(i),0.,0.) for i in range(2,10)))
        points=tuple(Point(str(i),"guide",p) for i,p in enumerate(vertices))
        cumulative,_=_segments(points)
        self.assertEqual(_lookahead_point(points,cumulative,1.),(1.,2.,0.))
        self.assertEqual(_lookahead_point(points,cumulative,1.5),(1.5,49.5,0.))

    def test_stationary_closed_loop_cannot_arrive_at_start(self):
        # A global nearest-point tie used to select the route's final arc
        # at t=0, falsely reporting arrival on a 16-unit closed course.
        vertices = ((0.,0.,0.), (4.,0.,0.), (4.,0.,4.), (0.,0.,4.), (0.,0.,0.))
        trace = self.route_trace(vertices, (vertices[0],) * 3)
        frames = preview_steering(trace)["frames"]
        self.assertTrue(all(f["progress"] == 0. for f in frames))
        self.assertTrue(all(f["arrivalCondition"] == "not-arrived" for f in frames))

    def test_closed_loop_arrival_requires_ordered_progress(self):
        vertices = ((0.,0.,0.), (4.,0.,0.), (4.,0.,4.), (0.,0.,4.), (0.,0.,0.))
        frames = preview_steering(self.route_trace(vertices, vertices))["frames"]
        self.assertEqual([f["progress"] for f in frames], [0.,4.,8.,12.,16.])
        self.assertTrue(all(f["arrivalCondition"] == "not-arrived" for f in frames[:-1]))
        self.assertEqual(frames[-1]["arrivalCondition"], "synthetic-position-only")

    def test_backtracking_error_measured_against_admissible_arc(self):
        vertices = ((0.,0.,0.), (10.,0.,0.))
        positions = ((0.,0.,0.), (4.,0.,0.), (2.,0.,0.), (2.,0.,0.))
        frames = preview_steering(self.route_trace(vertices, positions))["frames"]
        self.assertEqual([f["progress"] for f in frames], [0.,4.,4.,4.])
        self.assertEqual([f["crossTrackErrorXZ"] for f in frames], [0.,0.,2.,2.])

    def test_later_overlapping_leg_cannot_jump_progress(self):
        vertices = ((0.,0.,0.), (4.,0.,0.), (4.,0.,4.), (0.,0.,4.), (0.,0.,0.), (5.,0.,0.))
        positions = ((0.,0.,0.), (.5,0.,0.), (.5,0.,0.))
        frames = preview_steering(self.route_trace(vertices, positions))["frames"]
        self.assertEqual([f["progress"] for f in frames], [0.,.5,.5])

    def test_unbounded_and_degenerate_geometry_refused(self):
        for vertices in (
            ((0.,0.,0.), (1e308,0.,0.)),
            ((0.,0.,0.), (1e-13,0.,0.)),
            ((0.,0.,0.), (0.,1.,0.), (5.,0.,0.)),
            ((0.,0.,0.), (.2,0.,0.)),
        ):
            with self.subTest(vertices=vertices), self.assertRaises(TraceError):
                preview_steering(self.route_trace(vertices, ((0.,0.,0.), (0.,0.,0.))))

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
