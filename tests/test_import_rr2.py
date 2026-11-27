"""RR2 original-receipt importer tests; no RIFT or sister-repo execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.contracts import TraceError, load_trace
from rift_taxi.import_rr2 import import_rr2
from rift_taxi.replay import analyze


def source_record() -> dict:
    def event(key: str, phase: str, at: str) -> dict:
        return {
            "key": key, "phase": phase, "inserted": True,
            "callStartedAtUtc": "2026-11-23T04:00:" + at + "+00:00",
            "callCompletedAtUtc": "2026-11-23T04:00:" + at + "+00:00",
        }

    return {
        "kind": "native-continuous-move",
        "target": {
            "machineName": "LEGION", "processId": 12345,
            "processStartUtcTicks": 639309941054346253,
            "executableSha256": "a" * 64,
        },
        "playerKey": "123456",
        "status": "arrived",
        "releaseSucceeded": True,
        "goal": {"x": 1, "y": 0, "z": 0},
        "path": [
            {"x": 0, "y": 0, "z": 0, "bearing": 12,
             "observedAtUtc": "2026-11-23T04:00:00.000+00:00"},
            {"x": 0, "y": 0, "z": 0, "bearing": 25,
             "observedAtUtc": "2026-11-23T04:00:00.400+00:00"},
            {"x": 0.5, "y": 0, "z": 0, "bearing": 25,
             "observedAtUtc": "2026-11-23T04:00:00.700+00:00"},
            {"x": 1, "y": 0, "z": 0, "bearing": 25,
             "observedAtUtc": "2026-11-23T04:00:01.100+00:00"},
        ],
        "keySendEvents": [
            event("d", "key-down", "00.100"),
            event("d", "key-up", "00.400"),
            event("w", "key-down", "00.500"),
            event("w", "key-up", "01.000"),
        ],
        "passedWaypoints": [{
            "name": "Source guide",
            "position": {"x": 0.5, "y": 0, "z": 0},
            "source": "settled-corner",
        }],
    }


class ImportTests(unittest.TestCase):
    def create_input(self, directory: Path, *, record: dict | None = None) -> Path:
        source = directory / "original-rr2.jsonl"
        source.write_text(json.dumps(record or source_record()) + "\n", encoding="utf-8")
        return source

    def test_import_is_self_contained_and_does_not_promote_actor_yaw(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inp = self.create_input(root)
            original_hash = hashlib.sha256(inp.read_bytes()).hexdigest()
            output = root / "imported"
            result = import_rr2(inp, output, source_commit="a" * 40)
            self.assertTrue(result["sourceIntegrityVerified"])
            self.assertEqual(result["originalSourceSha256"], original_hash)
            trace = load_trace(output / "trace.json")
            self.assertEqual(len(trace.poses), 4)
            self.assertTrue(all(p.actor_yaw_deg is None for p in trace.poses))
            self.assertEqual(trace.source["timeBasis"], "same-host-utc")
            self.assertEqual(trace.points[1].kind, "guide")
            report = analyze(trace)
            self.assertFalse(report["arrival"]["liveArrivalVerified"])
            self.assertEqual(report["trace"]["clock"], "declared-same-host-utc")
            self.assertEqual(report["movement"]["actorYawAvailableSamples"], 0)
            # Preserve original source even after removal from import location.
            inp.unlink()
            self.assertEqual(
                hashlib.sha256((output / "sources" / "original.jsonl").read_bytes()).hexdigest(),
                original_hash,
            )
            self.assertEqual(len(trace.events), 4)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["snapshotCommitAuthenticatesCapture"])
            self.assertEqual(manifest["target"]["machineName"], "LEGION")

    def test_reject_invalid_or_missing_insertions(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record = source_record()
            record["keySendEvents"][0]["inserted"] = False
            inp = self.create_input(root, record=record)
            with self.assertRaises(TraceError):
                import_rr2(inp, root / "missing", source_commit="a" * 40)
            self.assertFalse((root / "missing").exists())

    def test_reject_invalid_source_sha_and_process(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record = source_record()
            record["target"]["executableSha256"] = "not-a-sha"
            inp = self.create_input(root, record=record)
            with self.assertRaises(TraceError):
                import_rr2(inp, root / "missing", source_commit="a" * 40)
            self.assertFalse((root / "missing").exists())

    def test_reject_multiple_jsonl_records(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inp = self.create_input(root)
            with inp.open("a", encoding="utf-8") as f:
                f.write(json.dumps(source_record()) + "\n")
            with self.assertRaisesRegex(TraceError, "single original"):
                import_rr2(inp, root / "missing", source_commit="a" * 40)

    def test_reject_duplicate_output_or_missing_revision(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inp = self.create_input(root)
            output = root / "imported"
            with self.assertRaises(TraceError):
                import_rr2(inp, output, source_commit="short")
            import_rr2(inp, output, source_commit="a" * 40)
            with self.assertRaisesRegex(TraceError, "output directory must be new"):
                import_rr2(inp, output, source_commit="a" * 40)

    def test_edited_normalized_poses_are_rejected_even_when_raw_sha_matches(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inp = self.create_input(root)
            output = root / "imported"
            import_rr2(inp, output, source_commit="a" * 40)
            trace_file = output / "trace.json"
            document = json.loads(trace_file.read_text(encoding="utf-8"))
            document["poses"][2]["xyz"][0] = 9000
            trace_file.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(TraceError, "normalization differs"):
                load_trace(trace_file)

    def test_reject_ambiguous_original_even_if_duplicate_last_value_valid(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inp = self.create_input(root)
            raw = inp.read_text(encoding="utf-8").replace(
                '"kind": "native-continuous-move"',
                '"kind": "unrelated", "kind": "native-continuous-move"', 1)
            inp.write_text(raw, encoding="utf-8")
            with self.assertRaisesRegex(TraceError, "duplicate JSON key"):
                import_rr2(inp, root / "missing", source_commit="a"*40)
            self.assertFalse((root / "missing").exists())

    def test_reject_numeric_alias_and_unhashable_phase(self):
        for value in (True, "1", []):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                record = source_record()
                record["path"][1]["x"] = value
                inp = self.create_input(root, record=record)
                with self.assertRaises(TraceError):
                    import_rr2(inp, root / "missing", source_commit="a"*40)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record = source_record()
            record["keySendEvents"][0]["phase"] = []
            inp = self.create_input(root, record=record)
            with self.assertRaises(TraceError):
                import_rr2(inp, root / "missing", source_commit="a"*40)

    def test_normalization_uses_exact_pinned_snapshot_not_reopened_file(self):
        from unittest.mock import patch
        from rift_taxi import contracts
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inp = self.create_input(root)
            output = root / "imported"
            import_rr2(inp, output, source_commit="a"*40)
            source = output / "sources" / "original.jsonl"
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            verify = contracts._verify_source_file

            def replace_after_pin(source_metadata, trace_path):
                verified = verify(source_metadata, trace_path)
                changed = source_record()
                changed["path"][2]["x"] = 999
                source.write_text(json.dumps(changed)+"\n", encoding="utf-8")
                return verified

            # The original, pinned snapshot is still valid for this
            # operation. A later independent load must reject the new bytes.
            with patch.object(contracts, "_verify_source_file", side_effect=replace_after_pin):
                trace = load_trace(output / "trace.json")
            self.assertEqual(trace.verified_source_sha256, before)
            self.assertEqual(trace.poses[2].xyz[0], .5)
            with self.assertRaisesRegex(TraceError, "SHA256 mismatch"):
                load_trace(output / "trace.json")

    def test_tampered_bundled_source_fails_replay(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inp = self.create_input(root)
            output = root / "imported"
            import_rr2(inp, output, source_commit="a" * 40)
            raw = output / "sources" / "original.jsonl"
            raw.write_bytes(raw.read_bytes() + b" ")
            with self.assertRaisesRegex(TraceError, "SHA256 mismatch"):
                load_trace(output / "trace.json")


if __name__ == "__main__":
    unittest.main()
