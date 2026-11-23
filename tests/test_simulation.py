"""Offline feedback experiment regressions: no native process or input."""
from dataclasses import replace
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from rift_taxi.contracts import Point, TraceError, load_trace
from rift_taxi.simulation import _project, _turn_limited_speed, simulate_route
from rift_taxi.steering import _segments

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "samples" / "synthetic_continuous.json"


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.trace = load_trace(SOURCE)

    def test_three_bend_feedback_converges_without_intermediate_stop(self):
        result = simulate_route(self.trace)
        metrics = result["metrics"]
        self.assertEqual(result["status"], "synthetic-arrived")
        self.assertLessEqual(metrics["finalXZError"], .3)
        self.assertGreaterEqual(metrics["forwardDutyRatio"], .95)
        self.assertGreater(metrics["turningWhileForwardSeconds"], 0.)
        self.assertGreaterEqual(metrics["turnSignRuns"], 3)
        self.assertLess(metrics["maxCrossTrackErrorXZ"], .6)
        self.assertFalse(result["gameInputSent"])
        self.assertFalse(result["liveArrivalVerified"])
        self.assertFalse(result["liveNavigabilityVerified"])
        frames = result["frames"]
        self.assertTrue(all(b["t"] > a["t"] for a,b in zip(frames, frames[1:])))
        self.assertTrue(all(b["progress"] >= a["progress"] for a,b in zip(frames, frames[1:])))
        self.assertEqual(frames[-1]["speed"], 0.)
        self.assertTrue(all(abs(f["yawRateDegreesPerSecond"]) <= 180. for f in frames))
        self.assertTrue(all(f["speed"] > 0. for f in frames[:-1]))

    def test_result_does_not_replay_later_recorded_poses_or_inputs(self):
        changed = replace(self.trace, poses=(self.trace.poses[0],), events=())
        self.assertEqual(simulate_route(self.trace), simulate_route(changed))

    def test_turn_limited_speed_respects_synthetic_curvature_envelope(self):
        import math
        self.assertEqual(_turn_limited_speed(3., 0., 1., 60.), 3.)
        for heading in (-80., -45., 45., 80.):
            curvature = 2.*abs(math.sin(math.radians(heading)))/1.5
            limited = _turn_limited_speed(3., heading, 1.5, 60.)
            self.assertGreater(limited, 0.)
            self.assertLessEqual(limited, 3.)
            self.assertLessEqual(limited*curvature, .8*math.radians(60.)+1e-12)

    def test_explicit_fixed_policy_retains_default_baseline(self):
        self.assertEqual(simulate_route(self.trace),
                         simulate_route(self.trace, speed_policy="fixed"))

    def test_turn_limited_model_respects_motion_bounds(self):
        result = simulate_route(self.trace, max_yaw_rate=60., speed_policy="turn-limited")
        self.assertEqual(result["status"], "synthetic-arrived")
        self.assertEqual(result["model"]["speedPolicy"], "turn-limited")
        self.assertGreaterEqual(result["metrics"]["forwardDutyRatio"], .95)
        self.assertGreater(result["metrics"]["meanMovingSpeedSyntheticUnitsPerSecond"], 1.)
        for frame in result["frames"]:
            self.assertLessEqual(frame["speed"], 3.)
            self.assertLessEqual(abs(frame["yawRateDegreesPerSecond"]), 60.)
        self.assertFalse(result["gameInputSent"])
        self.assertFalse(result["liveArrivalVerified"])

    def test_unknown_speed_policy_refused(self):
        with self.assertRaisesRegex(TraceError, "unknown synthetic speed policy"):
            simulate_route(self.trace, speed_policy="unknown")

    def test_repeatability(self):
        self.assertEqual(simulate_route(self.trace), simulate_route(self.trace))

    def test_off_route_start_refuses_motion(self):
        initial = replace(self.trace.poses[0], xyz=(0., 0., -10.))
        result = simulate_route(replace(self.trace, poses=(initial,)))
        self.assertEqual(result["status"], "cross-track-limit")
        self.assertEqual(result["metrics"]["elapsedSeconds"], 0.)
        self.assertEqual(result["metrics"]["forwardSeconds"], 0.)
        self.assertFalse(result["metrics"]["syntheticArrival"])

    def test_timeout_is_bounded_not_arrival(self):
        result = simulate_route(self.trace, max_seconds=.22)
        self.assertEqual(result["status"], "time-budget-exhausted")
        self.assertAlmostEqual(result["metrics"]["elapsedSeconds"], .22)
        self.assertFalse(result["metrics"]["syntheticArrival"])
        self.assertEqual(result["frames"][-1]["speed"], 0.)

    def test_crossing_cannot_jump_to_later_arc(self):
        points = tuple(Point(str(i), "guide", xyz) for i,xyz in enumerate((
            (0.,0.,0.), (4.,0.,0.), (4.,0.,4.), (0.,0.,4.), (0.,0.,0.), (5.,0.,0.),
        )))
        cumulative, _ = _segments(points)
        progress,error = _project(points,cumulative,(.5,0.,0.),0.,1.)
        self.assertAlmostEqual(progress,.5)
        self.assertAlmostEqual(error,0.)

    def test_reject_constraints_historical_and_nonflat_routes(self):
        for kind in ("hard_stop", "mandatory_passage"):
            points = list(self.trace.points)
            points[1] = replace(points[1], kind=kind)
            with self.assertRaisesRegex(TraceError, "constraint controller"):
                simulate_route(replace(self.trace, points=tuple(points)))
        with self.assertRaisesRegex(TraceError,"synthetic-local"):
            simulate_route(replace(self.trace,source_type="historical"))
        points = list(self.trace.points)
        points[1] = replace(points[1], xyz=(4., 1., 0.))
        with self.assertRaisesRegex(TraceError,"flat"):
            simulate_route(replace(self.trace,points=tuple(points)))

    def test_invalid_limits_and_missing_yaw_rejected(self):
        for kwargs in ({"dt":0.}, {"speed":True}, {"lookahead":float("nan")},
                       {"max_seconds":121.}, {"max_yaw_rate":0.}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TraceError):
                simulate_route(self.trace,**kwargs)
        with self.assertRaisesRegex(TraceError, "initial synthetic actor yaw"):
            simulate_route(replace(self.trace,poses=(replace(self.trace.poses[0],actor_yaw_deg=None),)))

    def test_cli_writes_new_report_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/"feedback.json"
            args = [sys.executable,"-B","-m","rift_taxi","simulate-route",str(SOURCE),"--out",str(output)]
            first = subprocess.run(args,cwd=ROOT,text=True,capture_output=True,timeout=20)
            self.assertEqual(first.returncode,0,first.stderr)
            self.assertTrue(json.loads(output.read_text())["metrics"]["syntheticArrival"])
            second = subprocess.run(args,cwd=ROOT,text=True,capture_output=True,timeout=20)
            self.assertEqual(second.returncode,2)
            self.assertIn("overwrite",second.stderr)


if __name__ == "__main__":
    unittest.main()
