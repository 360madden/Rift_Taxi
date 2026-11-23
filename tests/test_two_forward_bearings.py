"""Two-heading physical W kinematics comparison: offline fixture regressions only."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from rift_taxi.forward_bearing import compare_two_forward_bearings, ForwardBearingError
from rift_taxi.cli import main
from test_forward_bearing import fixture


class TwoHeadingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def _create(self, name, doc, audit):
        path = self.folder / f"{name}.json"
        rel = self.folder / f"{name}.jsonl"
        raw = json.dumps(doc, allow_nan=False).encode("utf8")
        log = ("\n".join(json.dumps(event, allow_nan=False) for event in audit)+"\n").encode()
        path.write_bytes(raw)
        rel.write_bytes(log)
        return path, hashlib.sha256(raw).hexdigest(), rel, hashlib.sha256(log).hexdigest()

    def pair(self, *, second_matrix_shift=0., same_heading=False,
             owner_change=False, reverse=False):
        a, first_audit = fixture()
        b, second_audit = fixture()
        # Genuine second-source form: a new pose, W movement and same game epoch
        # at a distinct facing angle, with its own physically accepted lease.
        angle = math.degrees(math.atan2(.5, 1.))
        b_angle = angle if same_heading else -angle
        b_angle += second_matrix_shift
        b["candidateBefore"]["xyzCandidate"] = [4., 2., 5.]
        b["candidateAfter"]["xyzCandidate"] = (
            [3.5,2.,6.] if same_heading else [4.5,2.,6.]
        )
        b["candidateSettledAfterRelease"]["xyzCandidate"] = (
            b["candidateAfter"]["xyzCandidate"][:]
        )
        vector = (
            [-.5,0.,1.] if same_heading else [.5,0.,1.]
        )
        b["candidateChanges"]["deltaXYZ"] = vector
        b["candidateChanges"]["settledDeltaXYZCandidate"] = vector
        b["candidateChanges"]["planarDistanceXZCandidate"] = math.hypot(.5,1.)
        b["candidateBefore"]["playerSystemBearingDegreesCandidate"] = -b_angle-.6
        b["candidateAfter"]["playerSystemBearingDegreesCandidate"] = -b_angle
        b["candidateSettledAfterRelease"]["playerSystemBearingDegreesCandidate"] = -b_angle
        b["candidateBefore"]["actorMatrixPlanarAngleDegreesCandidate"] = b_angle
        b["candidateAfter"]["actorMatrixPlanarAngleDegreesCandidate"] = b_angle
        b["candidateSettledAfterRelease"]["actorMatrixPlanarAngleDegreesCandidate"] = b_angle
        b["candidateChanges"]["playerSystemYawDeltaDegrees"] = .6
        # Keep each individual report valid while making the *pair* reverse.
        shift = -5 if reverse else 20
        for phase in ("candidateBefore", "candidateAfter", "candidateSettledAfterRelease"):
            b[phase]["observedMonotonicSeconds"] += shift
        b["action"]["keyDownAtMonotonicSeconds"] += shift
        b["action"]["keyUpAtMonotonicSeconds"] += shift
        for row in second_audit:
            row["monotonicSeconds"] += shift
        if owner_change:
            b["source"]["ownerKeyDecimalCandidate"] = "5678"
            for phase in ("candidateBefore", "candidateAfter", "candidateSettledAfterRelease"):
                b[phase]["ownerKeyDecimal"] = "5678"

        first = self._create("first", a, first_audit)
        second = self._create("second", b, second_audit)
        return {
            "first_report": first[0], "first_report_sha256": first[1],
            "first_release_audit": first[2], "first_release_audit_sha256": first[3],
            "second_report": second[0], "second_report_sha256": second[1],
            "second_release_audit": second[2], "second_release_audit_sha256": second[3],
        }

    def test_two_distinct_physical_angles_compare_without_yaw_promotion(self):
        out = compare_two_forward_bearings(**self.pair())
        self.assertEqual(out["schema"], "taxi.m1-two-heading-forward-comparison/1")
        self.assertEqual(out["status"], "two-distinct-heading-native-alignment-candidate")
        self.assertTrue(out["evidence"]["atLeast15DegreesObservedTravelVariation"])
        self.assertAlmostEqual(out["observed"]["travelHeadingSeparationDegrees"],
                               2*math.degrees(math.atan2(.5,1.)), places=6)
        self.assertAlmostEqual(out["observed"]["maxAbsoluteMatrixResidualDegrees"],
                               0, places=7)
        self.assertFalse(out["qualification"]["actorBodyYawVerified"])
        self.assertFalse(out["qualification"]["M1Complete"])
        self.assertFalse(out["qualification"]["productionNavigationArmed"])

    def test_unaligned_native_matrix_is_recorded_not_promoted(self):
        out = compare_two_forward_bearings(**self.pair(second_matrix_shift=5.))
        self.assertEqual(out["status"], "insufficient-or-inconsistent-heading-evidence")
        self.assertFalse(out["evidence"]["bothActorMatrixResidualsUnder1Degree"])
        self.assertFalse(out["qualification"]["actorBodyYawVerified"])

    def test_insufficient_heading_diversity_not_success(self):
        out = compare_two_forward_bearings(**self.pair(same_heading=True))
        self.assertFalse(out["evidence"]["atLeast15DegreesObservedTravelVariation"])
        self.assertEqual(out["status"], "insufficient-or-inconsistent-heading-evidence")

    def test_exact_actor_epoch_must_match(self):
        with self.assertRaisesRegex(ForwardBearingError, "different process/actor"):
            compare_two_forward_bearings(**self.pair(owner_change=True))

    def test_second_pulse_must_be_later(self):
        with self.assertRaisesRegex(ForwardBearingError, "overlap or reverse"):
            compare_two_forward_bearings(**self.pair(reverse=True))

    def test_duplicate_sources_rejected(self):
        args = self.pair()
        args["second_report"] = args["first_report"]
        args["second_report_sha256"] = args["first_report_sha256"]
        args["second_release_audit"] = args["first_release_audit"]
        args["second_release_audit_sha256"] = args["first_release_audit_sha256"]
        with self.assertRaisesRegex(ForwardBearingError, "two distinct"):
            compare_two_forward_bearings(**args)

    def test_second_release_source_hash_rejects_tamper(self):
        args = self.pair()
        args["second_release_audit"].write_bytes(b"malicious")
        with self.assertRaisesRegex(ForwardBearingError, "SHA-256 mismatch"):
            compare_two_forward_bearings(**args)

    def test_cli_output_and_nonoverwrite_are_offline_only(self):
        args = self.pair()
        out = self.folder / "comparison.json"
        argv = [
            "compare-two-forward-bearings",
            "--first-report", str(args["first_report"]),
            "--first-report-sha256", args["first_report_sha256"],
            "--first-release-audit", str(args["first_release_audit"]),
            "--first-release-sha256", args["first_release_audit_sha256"],
            "--second-report", str(args["second_report"]),
            "--second-report-sha256", args["second_report_sha256"],
            "--second-release-audit", str(args["second_release_audit"]),
            "--second-release-sha256", args["second_release_audit_sha256"],
            "--out", str(out),
        ]
        self.assertEqual(main(argv), 0)
        self.assertEqual(json.loads(out.read_text())["status"],
                         "two-distinct-heading-native-alignment-candidate")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(argv), 2)


if __name__ == "__main__":
    unittest.main()
