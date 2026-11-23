"""Pure offline tests for exact SHA-pinned physical forward-bearing comparison.

Fixtures are synthetic; original RIFT game/OS input are never touched by tests.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from rift_taxi.forward_bearing import analyze_forward_bearing, ForwardBearingError
from rift_taxi.cli import main


def _wrapped(v: float) -> float:
    return (v + 180) % 360 - 180


def fixture() -> tuple[dict, list[dict]]:
    before = [1., 2., 3.]
    after = [.5, 2., 4.]
    yaw = math.degrees(math.atan2(.5, 1.))
    def candidate(xyz, scalar, clock):
        return {
            "ownerKeyDecimal": "1234",
            "xyzCandidate": xyz,
            "playerSystemBearingDegreesCandidate": scalar,
            "actorMatrixPlanarAngleDegreesCandidate": yaw,
            "observedMonotonicSeconds": clock,
            "actorHeadingVerified": False,
            "passivePositionFreshnessVerified": False,
        }
    doc = {
        "schema": "taxi.m1-bounded-forward-probe/1",
        "status": "calibration-candidate-only",
        "probeKind": "forward",
        "dryRun": False,
        "source": {
            "host": "LEGION", "pid": 424, "startUtcTicks": 639310421805307472,
            "executablePath": r"C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe",
            "onDiskExecutableSha256": "a"*64,
            "windowHandle": 1968794, "ownerKeyDecimalCandidate": "1234",
            "reviewedSceneImageSha256": "b"*64,
        },
        "action": {
            "requestedKey": "W", "requestedHoldMilliseconds": 100,
            "keyDownAtMonotonicSeconds": 10.3,
            "keyUpAtMonotonicSeconds": 10.4,
            "downAcceptedBySender": True, "upAcceptedBySender": True,
            "osKeyDownAccepted": True, "osKeyUpAccepted": True,
            "externalLeaseClearObserved": True,
            "sampledDuringHeldKey": {"W": True, "A": False, "D": False},
            "sampledAfterKeyUp": {"W": False, "A": False, "D": False},
            "inputInjectedByTaxi": True, "gameInputConsumptionVerified": False,
            "physicalKeyReleaseConsumedByGameVerified": False,
        },
        "candidateBefore": candidate(before, -yaw-.6, 10.),
        "candidateAfter": candidate(after, -yaw, 10.6),
        "candidateSettledAfterRelease": candidate(after, -yaw, 11.),
        "candidateChanges": {
            "deltaXYZ": [-.5, 0., 1.],
            "settledDeltaXYZCandidate": [-.5, 0., 1.],
            "planarDistanceXZCandidate": math.hypot(.5, 1.),
            "playerSystemYawDeltaDegrees": .6,
            "actorMatrixAngleDeltaDegrees": 0.,
            "nativeXYZChanged": True, "nativeYawChanged": True,
            "bodyHeadingQualified": False,
            "passiveXYZFreshnessQualified": False,
            "gameMotionIndependentlyVerified": False,
        },
    }
    def event(name, t, **kwargs):
        return {"event": name, "monotonicSeconds": t, **kwargs}
    def state(held, stopped):
        return {"possibleHeld": held, "stopped": stopped,
                "gameResponseVerified": False}
    audit = [
        event("ready", 10.1, pid=424, dryRun=False),
        event("command", 10.2, action="reserve", key="W",
              status=state(["W"], False)),
        event("command", 10.29, action="renew", key=None,
              status=state(["W"], False)),
        event("command", 10.41, action="clear", key="W",
              status=state([], False)),
        event("command", 10.42, action="stop", key=None,
              status=state([], True)),
        event("stop", 10.43, possibleHeld=[], stopped=True,
              gameResponseVerified=False),
    ]
    return doc, audit


class ForwardBearingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
    def inputs(self, doc=None, audit=None, *, name="report"):
        if doc is None or audit is None:
            original_doc, original_audit = fixture()
            doc = original_doc if doc is None else doc
            audit = original_audit if audit is None else audit
        report_path = self.folder / (name + ".json")
        release_path = self.folder / (name + ".jsonl")
        body = json.dumps(doc, allow_nan=False).encode()
        ledger = ("\n".join(json.dumps(s, allow_nan=False) for s in audit) + "\n").encode()
        report_path.write_bytes(body)
        release_path.write_bytes(ledger)
        return {
            "report": report_path, "report_sha256": hashlib.sha256(body).hexdigest(),
            "release_audit": release_path,
            "release_audit_sha256": hashlib.sha256(ledger).hexdigest(),
        }
    def analyze(self, doc=None, audit=None):
        return analyze_forward_bearing(**self.inputs(doc, audit))

    def test_aligned_vector_and_scalar_convergence_are_candidate_only(self):
        result = self.analyze()
        self.assertEqual(result["schema"], "taxi.m1-forward-bearing-comparison/1")
        theta = math.degrees(math.atan2(.5, 1.))
        self.assertAlmostEqual(result["observed"]["nativeTravelAngleDegreesPositiveTowardNegativeX"],
                               theta, places=10)
        self.assertAlmostEqual(result["headingCandidates"]["travelMinusActorMatrixDegreesByPhase"][0],
                               0., places=10)
        self.assertAlmostEqual(result["headingCandidates"]["travelMinusNegatedScalarDegreesByPhase"][0],
                               -.6, places=8)
        self.assertAlmostEqual(result["headingCandidates"]["travelMinusNegatedScalarDegreesByPhase"][1],
                               0., places=8)
        self.assertTrue(result["releaseLedger"]["childReservedBeforeDown"])
        self.assertFalse(result["releaseLedger"]["gameConsumedReleaseVerified"])
        self.assertFalse(result["qualification"]["actorHeadingVerified"])
        self.assertFalse(result["qualification"]["continuousNavigationAuthorized"])
        self.assertTrue(result["observed"]["settledXZEqualsAfter"])

    def test_requires_original_exact_hashes(self):
        inputs = self.inputs()
        with self.assertRaisesRegex(ForwardBearingError, "physical forward report original SHA-256"):
            analyze_forward_bearing(**{**inputs, "report_sha256": "0"*64})
        with self.assertRaisesRegex(ForwardBearingError, "release audit original SHA-256"):
            analyze_forward_bearing(**{**inputs, "release_audit_sha256": "0"*64})
        inputs["report"].write_text("{}")
        with self.assertRaisesRegex(ForwardBearingError, "original SHA-256"):
            analyze_forward_bearing(**inputs)

    def test_dry_run_never_accepted_as_physical(self):
        d, a = fixture()
        d["dryRun"] = True
        with self.assertRaisesRegex(ForwardBearingError, "real physical W"):
            self.analyze(d, a)

    def test_wrong_key_held_and_unverified_release_refused(self):
        for field, value in [
            ("requestedKey", "D"),
            ("osKeyUpAccepted", False),
            ("gameInputConsumptionVerified", True),
            ("externalLeaseClearObserved", False),
            ("sampledDuringHeldKey", {"W": False,"A": False,"D": False}),
            ("sampledAfterKeyUp", {"W": True,"A": False,"D": False}),
        ]:
            d, a = fixture()
            d["action"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                ForwardBearingError, "input/release"):
                self.analyze(d, a)

    def test_actor_epoch_screenshot_and_candidate_cannot_be_fabricated(self):
        bad = [
            ("source", "ownerKeyDecimalCandidate", "0"),
            ("source", "reviewedSceneImageSha256", None),
            ("source", "startUtcTicks", True),
            ("candidateAfter", "ownerKeyDecimal", "wrong"),
            ("candidateBefore", "actorHeadingVerified", True),
            ("candidateAfter", "passivePositionFreshnessVerified", True),
        ]
        for section, field, value in bad:
            d, a = fixture()
            d[section][field] = value
            with self.subTest(field=field, section=section), self.assertRaises(
                ForwardBearingError):
                self.analyze(d, a)

    def test_source_deltas_must_match_individual_samples(self):
        bad = [
            ("deltaXYZ", [-1., 0., 1.]),
            ("settledDeltaXYZCandidate", [0., 0., 0.]),
            ("planarDistanceXZCandidate", 99.),
            ("playerSystemYawDeltaDegrees", .8),
            ("actorMatrixAngleDeltaDegrees", 3.),
            ("bodyHeadingQualified", True),
            ("nativeXYZChanged", False),
        ]
        for field, value in bad:
            d, a = fixture()
            d["candidateChanges"][field] = value
            with self.subTest(field=field), self.assertRaises(ForwardBearingError):
                self.analyze(d, a)

    def test_insufficient_xz_displacement_refused(self):
        d, a = fixture()
        d["candidateAfter"]["xyzCandidate"] = [1.,2.,3.]
        d["candidateSettledAfterRelease"]["xyzCandidate"] = [1.,2.,3.]
        d["candidateChanges"]["deltaXYZ"] = [0.,0.,0.]
        d["candidateChanges"]["settledDeltaXYZCandidate"] = [0.,0.,0.]
        d["candidateChanges"]["planarDistanceXZCandidate"] = 0.
        d["candidateChanges"]["nativeXYZChanged"] = True
        with self.assertRaisesRegex(ForwardBearingError, "displacement"):
            self.analyze(d, a)

    def test_timestamp_order_and_bounded_hold_required(self):
        for path, value in [
            (("action", "keyUpAtMonotonicSeconds"), 10.25),
            (("action", "keyDownAtMonotonicSeconds"), 9.9),
            (("candidateSettledAfterRelease", "observedMonotonicSeconds"), 10.59),
        ]:
            d, a = fixture()
            d[path[0]][path[1]] = value
            with self.subTest(path=path), self.assertRaisesRegex(
                    ForwardBearingError, "timeline"):
                self.analyze(d, a)

    def test_child_missing_renew_or_bad_audit_sequence_refused(self):
        d, a = fixture()
        for bad in [
            a[:2] + a[3:],
            [*a[:3], {**a[3], "monotonicSeconds": 10.35}, *a[4:]],
            [*a[:2], {**a[2], "status": {**a[2]["status"],
                                         "possibleHeld": []}}, *a[3:]],
            [*a[:3], {**a[3], "action": "renew"}, *a[4:]],
        ]:
            with self.subTest(bad=bad), self.assertRaises(ForwardBearingError):
                self.analyze(d, bad)

    def test_child_mismatch_and_emergency_path_refused(self):
        d, a = fixture()
        wrong_pid = copy.deepcopy(a)
        wrong_pid[0]["pid"] += 1
        with self.assertRaisesRegex(ForwardBearingError, "wrong physical target"):
            self.analyze(d, wrong_pid)
        abnormal = copy.deepcopy(a)
        abnormal.insert(3, {"event":"native-key-up-attempt",
                            "monotonicSeconds":10.31, "key":"W"})
        with self.assertRaisesRegex(ForwardBearingError, "nonordinary release"):
            self.analyze(d, abnormal)

    def test_nan_and_bad_json_are_not_accepted(self):
        d, a = fixture()
        d["candidateBefore"]["xyzCandidate"][0] = float("nan")
        # Exercise parser's explicit nonfinite rejection, not json.dumps default.
        inputs = self.inputs()
        bad = inputs["report"].read_bytes().replace(b"1.0", b"NaN", 1)
        inputs["report"].write_bytes(bad)
        inputs["report_sha256"] = hashlib.sha256(bad).hexdigest()
        with self.assertRaises(ForwardBearingError):
            analyze_forward_bearing(**inputs)

    def test_cli_does_not_overwrite_and_reports_offline_result(self):
        inputs = self.inputs()
        out = self.folder / "analysis.json"
        args = [
            "analyze-forward-bearing", "--report", str(inputs["report"]),
            "--report-sha256", inputs["report_sha256"],
            "--release-audit", str(inputs["release_audit"]),
            "--release-sha256", inputs["release_audit_sha256"],
            "--out", str(out),
        ]
        self.assertEqual(main(args), 0)
        self.assertIn("offline-candidate-heading-alignment-only", out.read_text())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 2)
        self.assertFalse(json.loads(out.read_text())["qualification"]["actorHeadingVerified"])


if __name__ == "__main__":
    unittest.main()
