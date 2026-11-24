"""Test saved synthetic V3 evidence without accessing a live game.

The frozen evaluator supplies the source fixture once. Corrupted copies
must be rejected without rewriting the original receipt. A caller's
separately retained digest checks byte identity, not source authenticity.
"""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.cli import main
from rift_taxi.contracts import TraceError
from rift_taxi.simulation_holdout_v3 import evaluate_holdout_v3
from rift_taxi.simulation_receipt_audit import audit_v3_receipt


class V3ReceiptAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluate_holdout_v3()
        cls.raw = json.dumps(cls.report,indent=2,allow_nan=False).encode("utf-8")

    def test_valid_receipt_and_pinned_bytes(self):
        """An exact digest and full synthetic replay establish reproducibility."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"report.json"
            path.write_bytes(self.raw)
            digest = hashlib.sha256(self.raw).hexdigest()
            audit = audit_v3_receipt(path,expected_sha256=digest)
            self.assertEqual(audit["sourceSHA256"],digest)
            self.assertTrue(audit["expectedSHA256Matched"])
            self.assertTrue(audit["aggregateCountsVerified"])
            self.assertTrue(audit["frozenReplayMatched"])
            self.assertFalse(audit["gameInputSent"])
            self.assertIsNone(audit_v3_receipt(path)["expectedSHA256Matched"])
            self.assertEqual(path.read_bytes(),self.raw)

    def test_reject_wrong_digest_and_ambiguous_json(self):
        """Refuse altered bytes, duplicate keys, and nonfinite JSON numbers."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"report.json"
            path.write_bytes(self.raw)
            with self.assertRaisesRegex(TraceError,"SHA-256 mismatch"):
                audit_v3_receipt(path,expected_sha256="0"*64)
            for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e400}'):
                path.write_bytes(raw)
                with self.subTest(raw=raw),self.assertRaises(TraceError):
                    audit_v3_receipt(path)

    def test_reject_missing_case_and_forged_aggregate(self):
        """Coverage and aggregate checks precede the deterministic replay."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"report.json"
            report = copy.deepcopy(self.report)
            report["cases"].pop()
            path.write_text(json.dumps(report),encoding="utf-8")
            with self.assertRaisesRegex(TraceError,"coverage mismatch"):
                audit_v3_receipt(path)
            report = copy.deepcopy(self.report)
            report["summary"]["fixed:0"]["geometricArrivals"] += 1
            path.write_text(json.dumps(report),encoding="utf-8")
            with self.assertRaisesRegex(TraceError,"aggregate mismatch"):
                audit_v3_receipt(path)

    def test_replay_rejects_coordinated_nonaggregate_edit(self):
        """A modified metric outside aggregate counts still fails replay."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"report.json"
            report = copy.deepcopy(self.report)
            report["cases"][0]["outcomes"]["fixed:0"]["metrics"]["simulatedDistanceXZ"] += .1
            path.write_text(json.dumps(report),encoding="utf-8")
            with self.assertRaisesRegex(TraceError,"differs from frozen synthetic replay"):
                audit_v3_receipt(path)

    def test_cli_does_not_overwrite_source_or_audit(self):
        """The CLI uses the shared new-file-only output writer."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"report.json"
            out = Path(folder)/"audit.json"
            path.write_bytes(self.raw)
            args = ["verify-v3-receipt",str(path),"--out",str(out)]
            self.assertEqual(main(args),0)
            original = out.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args),2)
            self.assertEqual(out.read_bytes(),original)
            self.assertEqual(path.read_bytes(),self.raw)


if __name__ == "__main__":
    unittest.main()
