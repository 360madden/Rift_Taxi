"""Read-only raw self-zone-key candidate tests; no RIFT process or input access.

Minimal typed self-owner chain adapted from source-hashed RR2 current-build
research. Never infer public zone ID or world instance from this raw u32.
"""
from __future__ import annotations

from dataclasses import replace
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rift_taxi.native_candidate import (
    NativeCandidateUnavailable, ZoneKeyCandidate, decode_current_build_candidate,
)
from rift_taxi.native_capture import CandidateCaptureRefused
from rift_taxi.cli import main
from rift_taxi.native_series import SeriesUnavailable
from test_native_candidate import MemoryFixture, OLD, NEW
from test_native_capture import CaptureFixture
from test_native_series import SeriesHarness


class ZoneFixture(MemoryFixture):
    def __init__(self, build=NEW, raw=0x10203040):
        super().__init__(build)
        self.health = 0x200A0000
        self.self_owner = 0x200B0000
        updated = build == NEW
        self.health_selector = self.base + (0x2F68850 if updated else 0x2F57850)
        self.owner_vptr = self.base + (0x2933218 if updated else 0x2927448)
        self.owner_getter = self.base + (0x19D2020 if updated else 0x19D21E0)
        self.put(self.health_selector, struct.pack("<i", 7))
        self.overwrite(self.entity + 0x18 + 7, b"\x06")
        self.put(self.components + 6 * 8, struct.pack("<Q", self.health))
        health = bytearray(0x48)
        struct.pack_into("<Q", health, 0x10, self.entity)
        struct.pack_into("<Q", health, 0x40, self.self_owner)
        self.put(self.health, health)
        owner = bytearray(0x154)
        struct.pack_into("<Q", owner, 0, self.owner_vptr)
        struct.pack_into("<I", owner, 0x150, raw)
        self.put(self.self_owner, owner)
        self.put(self.owner_vptr + 0x40, struct.pack("<Q", self.owner_getter))


class RawZoneDecoderTests(unittest.TestCase):
    def test_off_by_default_and_opt_in_on_both_supported_builds(self):
        for build in (OLD, NEW):
            with self.subTest(build=build[:9]):
                f = ZoneFixture(build)
                base = decode_current_build_candidate(f)
                self.assertIsNone(base.zone_key_candidate)
                result = decode_current_build_candidate(f, include_zone_key_candidate=True)
                z = result.zone_key_candidate
                self.assertEqual(z.raw_zone_key, 0x10203040)
                self.assertEqual(z.public_zone_id_status, "not-derived")
                self.assertEqual(z.world_instance_status, "unavailable")
                self.assertFalse(z.authoritative_zone_qualified)
                self.assertEqual(result.owner_key, f.key)

    def test_zero_raw_key_remains_unqualified_not_missing_world(self):
        f = ZoneFixture(raw=0)
        z = decode_current_build_candidate(f, include_zone_key_candidate=True).zone_key_candidate
        self.assertEqual(z.raw_zone_key, 0)
        self.assertFalse(z.authoritative_zone_qualified)

    def test_self_health_missing_slot_and_wrong_selector_fail_closed(self):
        for bad in ("missing", "selector"):
            f = ZoneFixture()
            if bad == "missing":
                f.overwrite(f.entity + 0x18 + 7, b"\xff")
            else:
                f.overwrite(f.health_selector, struct.pack("<i", 200))
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    NativeCandidateUnavailable, "health"):
                decode_current_build_candidate(f, include_zone_key_candidate=True)

    def test_health_backlink_and_alias_fail_closed(self):
        f = ZoneFixture()
        f.overwrite(f.health + 0x10, struct.pack("<Q", f.entity + 8))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "health component owner backlink"):
            decode_current_build_candidate(f, include_zone_key_candidate=True)
        f = ZoneFixture()
        f.overwrite(f.components + 6*8, struct.pack("<Q", f.component))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "alias"):
            decode_current_build_candidate(f, include_zone_key_candidate=True)

    def test_owner_type_and_getter_fingerprint_fail_closed(self):
        for bad in ("vptr", "getter"):
            f = ZoneFixture()
            if bad == "vptr":
                f.overwrite(f.self_owner, struct.pack("<Q", f.owner_vptr + 8))
            else:
                f.overwrite(f.owner_vptr + 0x40, struct.pack("<Q", f.owner_getter + 8))
            with self.subTest(bad=bad), self.assertRaisesRegex(
                    NativeCandidateUnavailable, "type/getter"):
                decode_current_build_candidate(f, include_zone_key_candidate=True)

    def test_changed_raw_zone_key_inside_capture_refused(self):
        f = ZoneFixture()
        original = f.read_exact
        flipped = [False]
        def read(address, size):
            raw = original(address, size)
            if address == f.self_owner + 0x150 and not flipped[0]:
                flipped[0] = True
                f.overwrite(f.self_owner + 0x150, struct.pack("<I", 0x87654321))
            return raw
        f.read_exact = read
        with self.assertRaisesRegex(NativeCandidateUnavailable, "changed during capture"):
            decode_current_build_candidate(f, include_zone_key_candidate=True)

    def test_switch_must_be_literal_bool(self):
        f = ZoneFixture()
        for bad in (1, None, "yes"):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "include_zone_key"):
                decode_current_build_candidate(f, include_zone_key_candidate=bad)


class ZoneReportingTests(unittest.TestCase):
    def test_one_shot_option_propagates_raw_not_world_id(self):
        c = CaptureFixture()
        c.result = replace(c.result, zone_key_candidate=ZoneKeyCandidate(4321))
        out = c.capture(include_zone_key_candidate=True)
        self.assertEqual(out["zoneKeyEvidence"]["rawSelfZoneKey"], 4321)
        self.assertEqual(out["zoneKeyEvidence"]["rawSelfZoneKeyHex"], "0x000010E1")
        self.assertFalse(out["zoneKeyEvidence"]["authoritativeZoneQualified"])
        self.assertEqual(out["zoneKeyEvidence"]["publicZoneIdStatus"], "not-derived")
        self.assertTrue(out["evidence"]["zoneKeyEvidenceRequested"])

    def test_missing_or_promoted_candidate_rejected(self):
        c = CaptureFixture()
        with self.assertRaisesRegex(CandidateCaptureRefused, "zone-key candidate missing"):
            c.capture(include_zone_key_candidate=True)
        c = CaptureFixture()
        c.result = replace(c.result, zone_key_candidate=ZoneKeyCandidate(
            4, authoritative_zone_qualified=True))
        with self.assertRaisesRegex(CandidateCaptureRefused, "unqualified"):
            c.capture(include_zone_key_candidate=True)

    def test_series_remains_candidate_and_one_raw_key(self):
        h = SeriesHarness()
        decode = h.decode
        def with_zone(*args, **opts):
            record = decode(*args, **opts)
            return replace(record, zone_key_candidate=ZoneKeyCandidate(1234))
        h.decode = with_zone
        out = h.run(include_zone_key_candidate=True)
        self.assertEqual(out["completedSamples"], 4)
        self.assertTrue(out["optionalEvidenceRequested"]["zoneKey"])
        self.assertEqual(
            [row["zoneKeyEvidence"]["rawSelfZoneKey"] for row in out["observations"]],
            [1234] * 4)
        self.assertFalse(out["qualifications"]["worldInstanceVerified"])
        self.assertFalse(out["qualifications"]["publicZoneIdVerified"])

    def test_series_zone_change_aborts_whole_report(self):
        h = SeriesHarness()
        decode = h.decode
        def changing(*args, **opts):
            record = decode(*args, **opts)
            return replace(record, zone_key_candidate=ZoneKeyCandidate(
                4567 if h.decodes <= 2 else 4568))
        h.decode = changing
        with self.assertRaisesRegex(SeriesUnavailable, "raw self-zone key changed"):
            h.run(include_zone_key_candidate=True)

    def test_one_shot_cli_opt_in_is_forwarded_without_game_action(self):
        with tempfile.TemporaryDirectory() as temp:
            output = str(Path(temp) / "one-shot.json")
            argv = [
                "inspect-native-candidate", "--pid", "7",
                "--start-ticks", "638000000000000000",
                "--exe-path", r"C:\Games\RIFT\RIFT.exe",
                "--sha256", NEW, "--hwnd", "9999", "--host", "LEGION",
                "--include-zone-key-candidate", "--out", output,
            ]
            with patch("rift_taxi.cli.capture_native_candidate",
                       return_value={"status": "candidate-only"}) as call:
                self.assertEqual(main(argv), 0)
                self.assertIs(call.call_args.kwargs["include_zone_key_candidate"], True)
                self.assertEqual(Path(output).read_text().strip(), '{\n  "status": "candidate-only"\n}')

    def test_pinned_series_cli_zone_opt_in_is_forwarded(self):
        with tempfile.TemporaryDirectory() as temp:
            output = str(Path(temp) / "series.json")
            argv = [
                "observe-native-series", "--pid", "7",
                "--start-ticks", "638000000000000000",
                "--exe-path", r"C:\Games\RIFT\RIFT.exe",
                "--sha256", NEW, "--hwnd", "9999", "--host", "LEGION",
                "--include-zone-key-candidate", "--samples", "4", "--out", output,
            ]
            with patch("rift_taxi.cli.observe_native_series",
                       return_value={"status": "candidate-only"}) as call:
                self.assertEqual(main(argv), 0)
                self.assertIs(call.call_args.kwargs["include_zone_key_candidate"], True)
                self.assertEqual(call.call_args.kwargs["samples"], 4)
                self.assertTrue(Path(output).is_file())

    def test_series_invalid_zone_evidence_rejected(self):
        h = SeriesHarness()
        with self.assertRaisesRegex(SeriesUnavailable, "raw same-owner zone key missing"):
            h.run(include_zone_key_candidate=True)
        with self.assertRaisesRegex(ValueError, "optional native field"):
            h.run(include_zone_key_candidate=1)


if __name__ == "__main__":
    unittest.main()
