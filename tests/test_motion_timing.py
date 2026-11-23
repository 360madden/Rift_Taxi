"""Source-timing analysis tests. All traces are injected/synthetic."""
from __future__ import annotations

from dataclasses import replace
import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from rift_taxi.contracts import (
    MovementTrace, PoseSample, InputEvent, Point, TraceError, load_trace,
)
from rift_taxi.motion_timing import analyze_motion_timing
from rift_taxi.cli import main

ROOT = Path(__file__).resolve().parents[1]


def sample_trace(*, poses=None, events=None) -> MovementTrace:
    if poses is None:
        poses = [
            PoseSample(0., (0., 0., 0.), None),
            PoseSample(.1, (0., 0., 0.), None),
            PoseSample(.2, (0., 0., 0.), None),
            PoseSample(.3, (.1, 0., 0.), None),
            PoseSample(.4, (.2, 0., 0.), None),
            PoseSample(.5, (.3, 0., 0.), None),
            PoseSample(.6, (.4, 0., 0.), None),
            PoseSample(.7, (.5, 0., 0.), None),
            PoseSample(.8, (.55, 0., 0.), None),
            PoseSample(.9, (.55, 0., 0.), None),
            PoseSample(1., (.55, 0., 0.), None),
            PoseSample(1.1, (.55, 0., 0.), None),
        ]
    if events is None:
        events = [
            InputEvent(.2, "W", "down"),
            InputEvent(.7, "W", "up"),
            InputEvent(.8, "D", "down"),
            InputEvent(1.0, "D", "up"),
        ]
    return MovementTrace(
        source_type="synthetic",
        source={"generator": "test-movement-observer"},
        frame={"frameId": "synthetic-local-xyz", "axisOrder": ["x", "y", "z"],
               "upAxis": "y", "units": "synthetic-units"},
        route_id="synthetic-qualifier",
        points=(Point("start", "guide", (0., 0., 0.)),
                Point("finish", "destination", (1., 0., 0.))),
        arrival_tolerance_xz=.3,
        window_start=poses[0].t,
        window_end=poses[-1].t,
        poses=tuple(poses), events=tuple(events),
        trace_sha256="b" * 64, verified_source_sha256=None,
    )


class TimingAnalysisTests(unittest.TestCase):
    def test_rates_by_stable_input_intervals_and_evidence_flags(self) -> None:
        doc = analyze_motion_timing(sample_trace())
        self.assertEqual(doc["schema"], "taxi.motion-timing-evidence/1")
        self.assertEqual(doc["classification"], "OFFLINE_TEMPORAL_ASSOCIATION_ONLY")
        self.assertEqual(doc["source"]["traceSha256"], "b" * 64)
        self.assertEqual(doc["source"]["originalSourceSha256"], None)
        self.assertEqual(doc["sampling"]["poseCount"], 12)
        self.assertGreater(doc["sampling"]["excludedInputTransitionIntervals"], 0)
        self.assertGreater(
            doc["observedIntervalSpeed"]["forwardKeyHeldIntervals"]["intervalCount"], 0
        )
        self.assertIsNone(doc["yawRate"]["medianDegreesPerSecondCandidate"])
        self.assertFalse(doc["qualifications"]["suitableForLiveSteeringCalibration"])
        self.assertFalse(doc["qualifications"]["movementCausedByWVerified"])

    def test_first_changed_pose_temporal_upper_bound_not_causal(self) -> None:
        doc = analyze_motion_timing(sample_trace())
        self.assertEqual(len(doc["firstChangedPoseAfterWDown"]), 1)
        first = doc["firstChangedPoseAfterWDown"][0]
        self.assertAlmostEqual(first["firstChangedPoseDelayUpperBoundSeconds"], .1)
        self.assertFalse(first["gameInputConsumptionVerified"])
        self.assertTrue(first["firstChangedPoseRequiresCausalVerification"])
        self.assertFalse(first["responseSearchSampleLimitReached"])

    def test_release_displacement_does_not_claim_coast(self) -> None:
        trace = sample_trace(events=[
            InputEvent(.2, "W", "down"), InputEvent(.7, "W", "up"),
            InputEvent(.95, "D", "down"), InputEvent(1.05, "D", "up"),
        ])
        doc = analyze_motion_timing(trace, coast_window_s=.3)
        self.assertEqual(len(doc["postWUpDisplacementProxies"]), 1)
        release = doc["postWUpDisplacementProxies"][0]
        self.assertGreater(release["postReleaseDisplacementProxyXZ"], 0.)
        self.assertFalse(release["physicalCoastingVerified"])
        self.assertFalse(release["gameKeyReleasedVerified"])
        self.assertTrue(release["censoredAtNextInputEdge"])

    def test_excludes_transition_and_oversized_pose_interval(self) -> None:
        poses = [
            PoseSample(0., (0., 0., 0.), None),
            PoseSample(.1, (0., 0., 0.), None),
            PoseSample(.9, (8., 0., 0.), None),
            PoseSample(1., (9., 0., 0.), None),
        ]
        doc = analyze_motion_timing(
            sample_trace(poses=poses,
                         events=[InputEvent(.05, "W", "down"),
                                 InputEvent(.95, "W", "up")]),
            max_interval_s=.25,
        )
        self.assertEqual(doc["sampling"]["excludedInputTransitionIntervals"], 2)
        self.assertEqual(doc["sampling"]["excludedExcessiveGapIntervals"], 1)
        self.assertEqual(
            doc["observedIntervalSpeed"]["forwardKeyHeldIntervals"]["intervalCount"], 0
        )

    def test_missing_response_returns_null_not_invented_zero(self) -> None:
        poses = [PoseSample(i * .1, (0., 0., 0.), None) for i in range(11)]
        result = analyze_motion_timing(
            sample_trace(poses=poses,
                         events=[InputEvent(.1, "W", "down"),
                                 InputEvent(.7, "W", "up")])
        )
        response = result["firstChangedPoseAfterWDown"][0]
        self.assertIsNone(response["firstChangedPoseAtSeconds"])
        self.assertIsNone(response["firstChangedPoseDelayUpperBoundSeconds"])
        self.assertEqual(
            result["observedIntervalSpeed"]["forwardKeyHeldIntervals"]["medianSourceUnitsPerSecond"],
            0.,
        )  # A measured zero in a stationary sample is not a qualified game response.
        self.assertFalse(result["qualifications"]["movementCausedByWVerified"])

    def test_response_and_coast_stop_at_next_input_edge(self) -> None:
        poses = [
            PoseSample(0., (0., 0., 0.), None),
            PoseSample(.1, (0., 0., 0.), None),
            PoseSample(.2, (0., 0., 0.), None),
            PoseSample(.3, (0., 0., 0.), None),
            PoseSample(.4, (2., 0., 0.), None),
            PoseSample(.5, (3., 0., 0.), None),
        ]
        events = [
            InputEvent(.1, "W", "down"),
            InputEvent(.2, "W", "up"),
            InputEvent(.3, "D", "down"),
            InputEvent(.5, "D", "up"),
        ]
        report = analyze_motion_timing(sample_trace(poses=poses, events=events))
        first = report["firstChangedPoseAfterWDown"][0]
        self.assertIsNone(first["firstChangedPoseAtSeconds"])
        self.assertTrue(first["censoredAtNextInputEdge"])
        release = report["postWUpDisplacementProxies"][0]
        self.assertTrue(release["censoredAtNextInputEdge"])
        self.assertIsNone(release["postReleaseDisplacementProxyXZ"])
        self.assertFalse(report["qualifications"]["coastingAfterReleaseVerified"])

    def test_yaw_rate_with_wrapped_synthetic_angles_cannot_verify_body(self) -> None:
        trace = sample_trace()
        poses = tuple(replace(p, actor_yaw_deg=(170. + i * 4) % 360 - 180)
                      for i, p in enumerate(trace.poses))
        doc = analyze_motion_timing(replace(trace, poses=poses))
        self.assertGreater(doc["yawRate"]["rateSampleCount"], 0)
        self.assertTrue(math.isfinite(doc["yawRate"]["medianDegreesPerSecondCandidate"]))
        self.assertFalse(doc["yawRate"]["bodyHeadingQualified"])

    def test_unbounded_dense_response_scanning_is_cut_off(self) -> None:
        poses = [PoseSample(i * .0005, (0., 0., 0.), None) for i in range(2001)]
        report = analyze_motion_timing(sample_trace(
            poses=poses,
            events=[InputEvent(.0, "W", "down"), InputEvent(.9, "W", "up")]))
        self.assertTrue(
            report["firstChangedPoseAfterWDown"][0]["responseSearchSampleLimitReached"]
        )
        self.assertFalse(report["qualifications"]["movementCausedByWVerified"])

    def test_invalid_parameters_are_fail_closed(self) -> None:
        for key, value in [
            ("movement_threshold_xz", 0.), ("movement_threshold_xz", True),
            ("max_interval_s", float("nan")), ("max_interval_s", 0.),
            ("response_horizon_s", 999.), ("coast_window_s", -2.),
        ]:
            with self.subTest(key=key), self.assertRaises(TraceError):
                analyze_motion_timing(sample_trace(), **{key: value})

    def test_real_hermetic_synthetic_fixture_keeps_source_kind(self) -> None:
        trace = load_trace(ROOT / "samples" / "synthetic_continuous.json")
        report = analyze_motion_timing(trace)
        self.assertEqual(report["source"]["sourceType"], "synthetic")
        self.assertIsNone(report["source"]["originalSourceSha256"])
        self.assertFalse(report["source"]["historicalAuthenticityEstablished"])
        self.assertFalse(report["qualifications"]["keySendEventsObservedInGame"])

    def test_cli_writes_new_json_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "model.json"
            argv = [
                "measure-motion-timing",
                str(ROOT / "samples" / "synthetic_continuous.json"),
                "--out", str(target),
            ]
            self.assertEqual(main(argv), 0)
            self.assertEqual(json.loads(target.read_text())["schema"],
                             "taxi.motion-timing-evidence/1")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(argv), 2)

    def test_doctor_keeps_live_game_input_disabled(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(main(["doctor"]), 0)
        d = json.loads(stdout.getvalue())
        self.assertTrue(d["offlineMotionTimingAvailable"])
        self.assertFalse(d["gameInputEnabled"])
        self.assertFalse(d["nativeCandidateQualifiedForMovement"])


if __name__ == "__main__":
    unittest.main()
