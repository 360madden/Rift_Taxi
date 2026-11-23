"""Synthetic exact-build candidate decoder tests; no game or OS process opened."""
from __future__ import annotations

from dataclasses import replace
import math
import struct
import unittest

from rift_taxi.native_candidate import (
    NativeCandidateUnavailable, bucket_index, decode_current_build_candidate,
)
from rift_taxi.native_memory import MainModule, ProcessPin

OLD = "1935a05c9db6d468e34e0055014a4a99c1b5afceb1695884e24600f5c20a4be8"
NEW = "df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01"
LAYOUTS = {
    OLD: (0x33624A8, 0x33623E0, 0x2F588A0, 0x26B4FB0, 0x2F58490),
    NEW: (0x3373C68, 0x3373BA0, 0x2F698A0, 0x26C35C0, 0x2F69490),
}


class MemoryFixture:
    """Simple in-memory byte segments; no real memory reads."""
    def __init__(self, build: str = NEW, key: int = 12345) -> None:
        self.base = 0x140000000
        self.manager = 0x20020000
        self.system = 0x20010000
        self.header = 0x20030000
        self.buckets = 0x20040000
        self.entity = 0x20050000
        self.components = 0x20060000
        self.component = 0x20070000
        self.actor = 0x20080000
        self.renderer = 0x20090000
        self.count = 8
        self.key = key
        self.pin = ProcessPin(24, 638_000_000_000_000_000, r"C:\RIFT\RIFT.exe", build)
        self.module = MainModule(self.base, 0x4000000, self.pin.executable_path)
        self.regions: dict[int, bytearray] = {}
        self.calls = 0
        self.mutate_on_yaw = False
        self.mutate_actor_matrix_after_read = False
        manager_rva, system_rva, index_rva, vptr_rva, actor_selector_rva = LAYOUTS[build]

        self.put(self.base + system_rva, struct.pack("<Q", self.system))
        self.put(self.base + manager_rva, struct.pack("<Q", self.manager))
        self.put(self.base + index_rva, struct.pack("<i", 3))
        self.put(self.base + actor_selector_rva, struct.pack("<i", 5))
        self.put(self.manager + 0x50, struct.pack("<Q", self.header))
        self.put(self.header, struct.pack("<QQQ", self.buckets, 24, self.count))
        bucket = self.buckets + bucket_index(key, self.count) * 24
        self.put(bucket, struct.pack("<QQQ", 0, key, self.entity))
        entity = bytearray(128)
        entity[0x18 + 3] = 2
        entity[0x18 + 5] = 4
        struct.pack_into("<Q", entity, 0x78, self.components)
        self.put(self.entity, entity)
        self.put(self.components + 2 * 8, struct.pack("<Q", self.component))
        self.put(self.components + 4 * 8, struct.pack("<Q", self.actor))
        c = struct.unpack("<f", struct.pack("<f", math.cos(math.pi / 6)))[0]
        s = struct.unpack("<f", struct.pack("<f", math.sin(math.pi / 6)))[0]
        self.matrix = struct.pack("<9f", c, 0., -s, 0., 1., 0., s, 0., c)
        actor_payload = bytearray(0x77C)
        actor_payload[0x398:0x3BC] = self.matrix
        struct.pack_into("<fff", actor_payload, 0x3BC, 14.5, 2.75, -10.25)
        struct.pack_into("<fff", actor_payload, 0x4F8, 1.5, 0., -2.0)
        struct.pack_into("<fff", actor_payload, 0x770, .5, -.25, 1.0)
        struct.pack_into("<Q", actor_payload, 0x410, self.renderer)
        self.put(self.actor, actor_payload)
        renderer_bytes = bytearray(0xD0)
        struct.pack_into("<fff", renderer_bytes, 0xC4, 14.5, 2.75, -10.25)
        self.put(self.renderer, renderer_bytes)
        payload = bytearray(0x110)
        struct.pack_into("<Q", payload, 0, self.base + vptr_rva)
        struct.pack_into("<Q", payload, 0x10, self.entity)
        struct.pack_into("<fff", payload, 0x48, 12.5, 3.0, -9.25)
        struct.pack_into("<fff", payload, 0x88, 12.5, 3.0, -9.25)
        payload[0x94:0xB8] = self.matrix
        self.put(self.component, payload)
        self.put(self.system + 0x360, struct.pack("<Q", key))
        self.put(self.system + 0x3F8, struct.pack("<Q", self.entity))
        self.put(self.system + 0x304, struct.pack("<f", math.pi / 2.0))

    def put(self, address: int, data: bytes | bytearray) -> None:
        self.regions[address] = bytearray(data)

    def overwrite(self, address: int, data: bytes) -> None:
        for start, region in self.regions.items():
            if start <= address and address + len(data) <= start + len(region):
                region[address-start:address-start+len(data)] = data
                return
        raise AssertionError(f"no fixture allocation at {hex(address)}")

    def read_exact(self, address: int, size: int) -> bytes:
        self.calls += 1
        for start, region in self.regions.items():
            if start <= address and address + size <= start + len(region):
                raw = bytes(region[address-start:address-start+size])
                if self.mutate_on_yaw and address == self.system + 0x304:
                    self.mutate_on_yaw = False
                    self.overwrite(self.component + 0x48, struct.pack("<f", 42.0))
                if self.mutate_actor_matrix_after_read and address == self.actor + 0x398:
                    self.mutate_actor_matrix_after_read = False
                    self.overwrite(self.actor + 0x398, struct.pack("<f", 0.0))
                return raw
        raise NativeCandidateUnavailable(f"unmapped read: {address:x}/{size}")


class DecoderTests(unittest.TestCase):
    def test_updated_and_historical_builds_remain_candidates(self) -> None:
        for build in (OLD, NEW):
            with self.subTest(build=build[:8]):
                fixture = MemoryFixture(build)
                sample = decode_current_build_candidate(fixture, clock=lambda: 90.0)
                self.assertEqual(sample.owner_key, 12345)
                self.assertEqual(sample.xyz_candidate, (12.5, 3.0, -9.25))
                self.assertAlmostEqual(sample.yaw_bearing_deg_candidate, 90, places=4)
                self.assertEqual(sample.build_sha256, build)
                self.assertFalse(sample.actor_heading_qualified)
                self.assertFalse(sample.passive_position_freshness_qualified)
                self.assertEqual(sample.observed_monotonic_s, 90)
                self.assertGreater(fixture.calls, 20)

    def test_opt_in_refresh_guard_diagnostics_from_same_component(self) -> None:
        for build in (OLD, NEW):
            with self.subTest(build=build[:8]):
                fixture = MemoryFixture(build)
                ordinary = decode_current_build_candidate(fixture)
                self.assertIsNone(ordinary.refresh_guard_candidate)
                guard = decode_current_build_candidate(
                    fixture, include_refresh_guard_candidate=True
                ).refresh_guard_candidate
                self.assertEqual(guard.handle_decimal, "0")
                self.assertEqual(guard.flag_raw, 0)
                self.assertEqual(guard.top_level_branch,
                                 "both-known-top-level-routes-ineligible-candidate")
                self.assertFalse(guard.known_writer_executed)
                self.assertFalse(guard.passive_xyz_freshness_qualified)

    def test_refresh_handle_precedes_flag_and_never_claims_writer(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.component + 0x100, struct.pack("<Q", 0x12345678))
        fixture.overwrite(fixture.component + 0x108, b"\x07")
        guard = decode_current_build_candidate(
            fixture, include_refresh_guard_candidate=True
        ).refresh_guard_candidate
        self.assertEqual(guard.handle_decimal, str(0x12345678))
        self.assertEqual(guard.handle_hex, "0x0000000012345678")
        self.assertEqual(guard.flag_raw, 7)
        self.assertEqual(guard.top_level_branch, "handle-present-guard-candidate")
        self.assertFalse(guard.known_writer_executed)

    def test_nonzero_flag_without_handle_is_only_branch_candidate(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.component + 0x108, b"\x02")
        guard = decode_current_build_candidate(
            fixture, include_refresh_guard_candidate=True
        ).refresh_guard_candidate
        self.assertEqual(guard.top_level_branch, "alternate-flag-guard-candidate")
        self.assertEqual(guard.flag_raw, 2)
        self.assertFalse(guard.passive_xyz_freshness_qualified)

    def test_refresh_guard_option_requires_boolean(self) -> None:
        fixture = MemoryFixture()
        with self.assertRaisesRegex(ValueError, "refresh_guard"):
            decode_current_build_candidate(
                fixture, include_refresh_guard_candidate=1
            )

    def test_optional_actor_world_translation_reconstructs_same_owner(self) -> None:
        for build in (OLD, NEW):
            with self.subTest(build=build[:8]):
                fixture = MemoryFixture(build)
                ordinary = decode_current_build_candidate(fixture)
                self.assertIsNone(ordinary.actor_translation_candidate)
                sample = decode_current_build_candidate(
                    fixture, include_actor_translation_candidate=True
                )
                translation = sample.actor_translation_candidate
                self.assertEqual(translation.secondary_cache_xyz, (12.5, 3., -9.25))
                self.assertEqual(translation.actor_stored_xyz, (14.5, 2.75, -10.25))
                self.assertEqual(translation.reconstructed_actor_xyz, (14.5, 2.75, -10.25))
                self.assertEqual(translation.reconstruction_max_abs_delta, 0.)
                self.assertEqual(translation.primary_secondary_max_abs_delta, 0.)
                self.assertEqual(translation.actor_flags, 0)
                self.assertEqual(translation.render_xyz, (14.5, 2.75, -10.25))
                self.assertEqual(translation.render_status, "normal-render-translation-candidate")
                self.assertFalse(translation.independently_fresh)
                self.assertFalse(translation.authoritative_player_position)

    def test_actor_translation_relation_mismatch_is_candidate_only(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.actor + 0x3BC, struct.pack("<f", 50.))
        value = decode_current_build_candidate(
            fixture, include_actor_translation_candidate=True
        ).actor_translation_candidate
        self.assertGreater(value.reconstruction_max_abs_delta, 30.)
        self.assertFalse(value.authoritative_player_position)

    def test_actor_translation_alternate_branch_not_followed(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.actor + 0x1C0, struct.pack("<I", 1))
        fixture.overwrite(fixture.actor + 0x410, struct.pack("<Q", 0xFFFFFFFFFFFFFFFF))
        value = decode_current_build_candidate(
            fixture, include_actor_translation_candidate=True
        ).actor_translation_candidate
        self.assertEqual(value.render_status, "alternate-render-reference-not-followed")
        self.assertIsNone(value.render_xyz)

    def test_actor_translation_normal_null_renderer_is_optional(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.actor + 0x410, b"\0" * 8)
        value = decode_current_build_candidate(
            fixture, include_actor_translation_candidate=True
        ).actor_translation_candidate
        self.assertEqual(value.render_status, "normal-render-pointer-absent")
        self.assertIsNone(value.actor_render_max_abs_delta)

    def test_actor_translation_nonfinite_and_bad_renderer_refused(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.actor + 0x4F8, struct.pack("<f", float("nan")))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "nonfinite"):
            decode_current_build_candidate(fixture, include_actor_translation_candidate=True)
        fixture = MemoryFixture()
        fixture.overwrite(fixture.actor + 0x410, struct.pack("<Q", 999))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "pointer"):
            decode_current_build_candidate(fixture, include_actor_translation_candidate=True)

    def test_actor_translation_source_change_during_capture_refused(self) -> None:
        fixture = MemoryFixture()
        original = fixture.read_exact
        mutated = False
        def read_changing(address: int, length: int) -> bytes:
            nonlocal mutated
            data = original(address, length)
            if address == fixture.actor + 0x770 and not mutated:
                mutated = True
                fixture.overwrite(fixture.actor + 0x4F8, struct.pack("<f", 7.))
            return data
        fixture.read_exact = read_changing
        with self.assertRaisesRegex(NativeCandidateUnavailable, "changed during capture"):
            decode_current_build_candidate(fixture, include_actor_translation_candidate=True)

    def test_actor_translation_option_requires_bool(self) -> None:
        fixture = MemoryFixture()
        with self.assertRaisesRegex(ValueError, "include_actor_translation"):
            decode_current_build_candidate(
                fixture, include_actor_translation_candidate=1
            )

    def test_opt_in_same_owner_matrix_bits_and_planar_angle(self) -> None:
        for build in (OLD, NEW):
            with self.subTest(build=build[:8]):
                fixture = MemoryFixture(build)
                standard = decode_current_build_candidate(fixture)
                self.assertIsNone(standard.matrix_copy_candidate)
                sample = decode_current_build_candidate(fixture, include_matrix_candidate=True)
                matrix = sample.matrix_copy_candidate
                self.assertIsNotNone(matrix)
                self.assertTrue(matrix.exact_bits_match)
                self.assertEqual(len(matrix.position_secondary_raw_bits), 9)
                self.assertEqual(matrix.position_secondary_raw_bits, matrix.actor_raw_bits)
                self.assertAlmostEqual(matrix.actor_planar_angle_degrees_candidate, 30., places=4)
                self.assertAlmostEqual(matrix.position_planar_angle_degrees_candidate, 30., places=4)
                self.assertEqual(matrix.actor_matrix_status, "structural-y-planar-matrix-candidate")
                self.assertFalse(matrix.body_heading_qualified)
                self.assertFalse(sample.actor_heading_qualified)

    def test_matrix_bits_mismatch_is_reported_not_heading_qualified(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.actor + 0x398, struct.pack("<f", 0.0))
        matrix = decode_current_build_candidate(fixture, include_matrix_candidate=True).matrix_copy_candidate
        self.assertFalse(matrix.exact_bits_match)
        self.assertFalse(matrix.body_heading_qualified)
        self.assertEqual(matrix.actor_matrix_status, "unqualified-matrix-shape")
        self.assertIsNone(matrix.actor_planar_angle_degrees_candidate)

    def test_nonfinite_actor_matrix_remains_raw_unqualified_diagnostic(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.actor + 0x398, struct.pack("<f", float("nan")))
        matrix = decode_current_build_candidate(fixture, include_matrix_candidate=True).matrix_copy_candidate
        self.assertFalse(matrix.exact_bits_match)
        self.assertEqual(matrix.actor_matrix_status, "nonfinite-matrix")
        self.assertIsNone(matrix.actor_planar_angle_degrees_candidate)

    def test_opt_in_actor_owner_selector_refused_on_invalid_or_missing(self) -> None:
        for invalid in (-1, 0x60):
            fixture = MemoryFixture()
            actor_selector = LAYOUTS[NEW][-1]
            fixture.overwrite(fixture.base + actor_selector, struct.pack("<i", invalid))
            with self.subTest(invalid=invalid), self.assertRaisesRegex(NativeCandidateUnavailable, "actor component selector"):
                decode_current_build_candidate(fixture, include_matrix_candidate=True)
        fixture = MemoryFixture()
        fixture.overwrite(fixture.entity + 0x18 + 5, b"\xff")
        with self.assertRaisesRegex(NativeCandidateUnavailable, "lacks actor"):
            decode_current_build_candidate(fixture, include_matrix_candidate=True)
        fixture = MemoryFixture()
        fixture.overwrite(fixture.components + 4 * 8, struct.pack("<Q", fixture.component))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "alias"):
            decode_current_build_candidate(fixture, include_matrix_candidate=True)

    def test_matrix_bytes_change_during_capture_rejected(self) -> None:
        fixture = MemoryFixture()
        fixture.mutate_actor_matrix_after_read = True
        with self.assertRaisesRegex(NativeCandidateUnavailable, "changed during capture"):
            decode_current_build_candidate(fixture, include_matrix_candidate=True)

    def test_matrix_option_requires_boolean(self) -> None:
        fixture = MemoryFixture()
        with self.assertRaisesRegex(ValueError, "must be bool"):
            decode_current_build_candidate(fixture, include_matrix_candidate=1)

    def test_unknown_build_is_refused_before_any_read(self) -> None:
        fixture = MemoryFixture()
        fixture.pin = replace(fixture.pin, executable_sha256="e" * 64)
        with self.assertRaisesRegex(NativeCandidateUnavailable, "unqualified"):
            decode_current_build_candidate(fixture)
        self.assertEqual(fixture.calls, 0)

    def test_module_too_small_is_refused(self) -> None:
        fixture = MemoryFixture()
        fixture.module = MainModule(fixture.base, 0x200000, fixture.pin.executable_path)
        with self.assertRaisesRegex(NativeCandidateUnavailable, "module too small"):
            decode_current_build_candidate(fixture)

    def test_owner_component_dispatch_mismatch_is_refused(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.component, struct.pack("<Q", 0x140001000))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "dispatch pointer mismatch"):
            decode_current_build_candidate(fixture)

    def test_owner_backlink_mismatch_is_refused(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.component + 0x10, struct.pack("<Q", fixture.manager))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "backlink mismatch"):
            decode_current_build_candidate(fixture)

    def test_player_system_backlink_mismatch_is_refused(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.system + 0x3F8, struct.pack("<Q", fixture.manager))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "backlink mismatch"):
            decode_current_build_candidate(fixture)

    def test_component_absent_refused(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.entity + 0x18 + 3, b"\xff")
        with self.assertRaisesRegex(NativeCandidateUnavailable, "lacks position"):
            decode_current_build_candidate(fixture)

    def test_nonfinite_xyz_and_yaw_refused(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.component + 0x48, struct.pack("<f", float("nan")))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "XYZ"):
            decode_current_build_candidate(fixture)
        fixture = MemoryFixture()
        fixture.overwrite(fixture.system + 0x304, struct.pack("<f", float("inf")))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "yaw"):
            decode_current_build_candidate(fixture)

    def test_mutating_position_payload_detected(self) -> None:
        fixture = MemoryFixture()
        fixture.mutate_on_yaw = True
        with self.assertRaisesRegex(NativeCandidateUnavailable, "changed during capture"):
            decode_current_build_candidate(fixture)

    def test_missing_player_key_refused(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.system + 0x360, b"\0" * 8)
        with self.assertRaisesRegex(NativeCandidateUnavailable, "unit key absent"):
            decode_current_build_candidate(fixture)

    def test_bad_table_stride_and_chain_cycle_refused(self) -> None:
        fixture = MemoryFixture()
        fixture.overwrite(fixture.header + 8, struct.pack("<Q", 7))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "table layout"):
            decode_current_build_candidate(fixture)
        fixture = MemoryFixture()
        bucket = fixture.buckets + bucket_index(fixture.key, fixture.count) * 24
        fixture.overwrite(bucket, struct.pack("<QQQ", bucket | 1, fixture.key + 1, 0))
        with self.assertRaisesRegex(NativeCandidateUnavailable, "cyclic"):
            decode_current_build_candidate(fixture)

    def test_signed_32_bit_hash_uses_truncating_division(self) -> None:
        self.assertEqual(bucket_index(12345, 8), 7)
        self.assertEqual(bucket_index(0xFFFFFFFF, 8), (2147466840 % 8))
        self.assertEqual(bucket_index(0x100000000, 8), 0)
        with self.assertRaises(ValueError):
            bucket_index(0, 8)

    def test_invalid_timestamp_rejected(self) -> None:
        fixture = MemoryFixture()
        with self.assertRaisesRegex(NativeCandidateUnavailable, "timestamp"):
            decode_current_build_candidate(fixture, clock=lambda: float("nan"))


if __name__ == "__main__":
    unittest.main()
