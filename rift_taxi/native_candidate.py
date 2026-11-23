"""Exact-build read-only native player-position/facing *candidate* decoder.

Independent Taxi-owned implementation based on the source-pinned RR2 lookup
described in docs/RR2_HANDOFF.md. No game input, actor-heading promotion, cached
position freshness claim, global address caching or sibling runtime dependency.

Reads are bounded; each acquisition resolves player ownership afresh and checks
anchors and field payloads again. Sequential reads cannot exclude ABA.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
import time
from typing import Callable, Protocol

from .native_memory import MainModule, ProcessPin

_MIN_ADDR = 0x10000
_MAX_ADDR = 0x00007FFF_FFFF_FFFF

# Hashes and addresses originate in RR2's CurrentBuildPlayerLookup.cs,
# CurrentBuildPositionSampleCommand.cs and CurrentBuildFacingCandidateReader.cs.
# SHA pinning does NOT prove the current installed game is one of these builds.
# Entries: manager, player system, position selector, position vtable, actor selector.
_BUILD_LAYOUTS = {
    "1935a05c9db6d468e34e0055014a4a99c1b5afceb1695884e24600f5c20a4be8": (
        0x33624A8, 0x33623E0, 0x2F588A0, 0x26B4FB0, 0x2F58490),
    "df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01": (
        0x3373C68, 0x3373BA0, 0x2F698A0, 0x26C35C0, 0x2F69490),
}


class NativeCandidateUnavailable(RuntimeError):
    """Build/ownership/field evidence was inadequate for a native candidate."""


class CandidateReadSource(Protocol):
    pin: ProcessPin
    module: MainModule

    def read_exact(self, address: int, size: int) -> bytes: ...


@dataclass(frozen=True)
class MatrixCopyCandidate:
    """Two separately read matrix bytes, no actor-facing qualification."""

    position_secondary_raw_bits: tuple[int, ...]
    actor_raw_bits: tuple[int, ...]
    exact_bits_match: bool
    position_planar_angle_degrees_candidate: float | None
    actor_planar_angle_degrees_candidate: float | None
    position_matrix_status: str
    actor_matrix_status: str
    body_heading_qualified: bool = False


@dataclass(frozen=True)
class PositionFacingCandidate:
    process_id: int
    process_start_utc_ticks: int
    build_sha256: str
    owner_key: int
    xyz_candidate: tuple[float, float, float]
    yaw_radians_candidate: float
    yaw_bearing_deg_candidate: float
    observed_monotonic_s: float
    qualification: str = "candidate-only; passive-XYZ-freshness-and-body-yaw-unverified"
    actor_heading_qualified: bool = False
    passive_position_freshness_qualified: bool = False
    matrix_copy_candidate: MatrixCopyCandidate | None = None


def _matrix_descriptor(raw: bytes) -> tuple[tuple[int, ...], float | None, str]:
    """Source-pinned RR2 Y-planar diagnostics; candidate only, never body yaw."""
    if len(raw) != 36:
        raise NativeCandidateUnavailable("actor/position matrix read was not 36 bytes")
    bits = struct.unpack("<9I", raw)
    values = struct.unpack("<9f", raw)
    if not all(math.isfinite(v) for v in values):
        return (bits, None, "nonfinite-matrix")
    orthogonal_error = max(
        abs(sum(values[row * 3 + col] * values[other * 3 + col]
                for col in range(3)) - (1 if row == other else 0))
        for row in range(3) for other in range(3)
    )
    v = values
    det = (v[0] * (v[4] * v[8] - v[5] * v[7])
           - v[1] * (v[3] * v[8] - v[5] * v[6])
           + v[2] * (v[3] * v[7] - v[4] * v[6]))
    planar_error = max(abs(v[i]) for i in (1, 3, 5, 7))
    planar_error = max(planar_error, abs(v[4] - 1),
                       abs(v[8] - v[0]), abs(v[2] + v[6]))
    structural = max(orthogonal_error, abs(det - 1), planar_error) < 0.01
    if not structural:
        return (bits, None, "unqualified-matrix-shape")
    return (bits, math.degrees(math.atan2(v[6], v[0])),
            "structural-y-planar-matrix-candidate")


def _pointer(value: int, byte_count: int = 8) -> int:
    if (type(value) is not int or type(byte_count) is not int
            or byte_count < 1 or value < _MIN_ADDR or value % 8
            or value > _MAX_ADDR - byte_count):
        raise NativeCandidateUnavailable("native pointer outside bounded aligned user memory")
    return value


def _u64(raw: bytes) -> int:
    return struct.unpack("<Q", raw)[0]


def bucket_index(key: int, count: int) -> int:
    """Mirror the signed 32-bit Schrage hash in RR2's player-table lookup."""
    if type(key) is not int or not 0 < key < (1 << 64):
        raise ValueError("unit key must be a nonzero unsigned 64-bit integer")
    if type(count) is not int or not 1 <= count <= (1 << 24):
        raise ValueError("bucket count invalid")
    low = key & 0xFFFFFFFF
    if low >= 0x80000000:
        low -= 0x100000000
    quotient = (abs(low) // 127773) * (1 if low >= 0 else -1)
    remainder = low - quotient * 127773
    signed = (remainder * 16807 - quotient * 2836 + 0x80000000) % (1 << 32) - 0x80000000
    adjusted = signed if signed >= 0 else signed + 2147483647
    return (adjusted & 0xFFFFFFFF) % count


def decode_current_build_candidate(
    source: CandidateReadSource,
    *,
    clock: Callable[[], float] = time.monotonic,
    include_matrix_candidate: bool = False,
) -> PositionFacingCandidate:
    """Read an exact-known-build owner/XYZ/yaw candidate without game actions.

    This object is intentionally NOT a LivePose and cannot be passed directly
    to HeldInputController, whose verified yaw/freshness gates remain required.
    """
    if type(include_matrix_candidate) is not bool:
        raise ValueError("include_matrix_candidate must be bool")
    if not isinstance(source.pin, ProcessPin) or not isinstance(source.module, MainModule):
        raise NativeCandidateUnavailable("pinned process and module identity required")
    pin = source.pin
    base = source.module.base
    size = source.module.size
    build_sha = pin.executable_sha256.lower()
    layout = _BUILD_LAYOUTS.get(build_sha)
    if layout is None:
        raise NativeCandidateUnavailable("unqualified executable build; no offsets available")
    manager_rva, system_rva, position_selector_rva, position_vptr_rva, actor_selector_rva = layout
    if size <= max(manager_rva + 8, system_rva + 8, position_selector_rva + 4,
                   position_vptr_rva + 8,
                   (actor_selector_rva + 4 if include_matrix_candidate else 0)):
        raise NativeCandidateUnavailable("module too small for exact-build addresses")

    anchors: list[tuple[int, bytes]] = []

    def read(address: int, length: int, *, anchor: bool = True) -> bytes:
        if type(address) is not int or type(length) is not int or not 1 <= length <= 4096:
            raise NativeCandidateUnavailable("native candidate read is not bounded")
        if address < _MIN_ADDR or address > _MAX_ADDR - length:
            raise NativeCandidateUnavailable("native candidate read outside user address space")
        raw = source.read_exact(address, length)
        if not isinstance(raw, bytes) or len(raw) != length:
            raise NativeCandidateUnavailable("native candidate read incomplete")
        if anchor:
            anchors.append((address, raw))
        return raw

    def get_ptr(address: int, *, length: int = 8) -> int:
        return _pointer(_u64(read(address, 8)), length)

    def resolve_entity(key: int, manager: int) -> int:
        table = get_ptr(manager + 0x50)
        buckets, stride, count = struct.unpack("<QQQ", read(table, 24))
        _pointer(buckets)
        if stride < 24 or stride > 4096 or stride % 8 or not 1 <= count <= (1 << 24):
            raise NativeCandidateUnavailable("invalid owner table layout")
        bucket = _pointer(buckets + bucket_index(key, count) * stride, 24)
        visited: set[int] = set()
        current = bucket
        for index in range(8):
            if current in visited:
                raise NativeCandidateUnavailable("cyclic owner bucket chain")
            visited.add(current)
            tagged_next, candidate_key, entity = struct.unpack("<QQQ", read(current, 24))
            if (index > 0 or not tagged_next & 1) and candidate_key == key:
                return _pointer(entity, 128)
            next_address = tagged_next & ~1
            if not next_address:
                raise NativeCandidateUnavailable("player unit key not in native owner table")
            current = _pointer(next_address, 24)
        raise NativeCandidateUnavailable("owner bucket chain exceeds eight-node limit")

    # Resolve every pointer from the exact module and current player system.
    system = get_ptr(base + system_rva, length=0x400)
    key = _u64(read(system + 0x360, 8))
    if key == 0:
        raise NativeCandidateUnavailable("player unit key absent")
    manager = get_ptr(base + manager_rva, length=0x58)
    entity = resolve_entity(key, manager)
    entity_bytes = read(entity, 128)

    # Resolve position component selector and sparse entity slot mapping.
    selector = struct.unpack("<i", read(base + position_selector_rva, 4))[0]
    if not 0 <= selector < 0x60:
        raise NativeCandidateUnavailable("invalid native position selector")
    table = _pointer(_u64(entity_bytes[0x78:0x80]))
    slot = entity_bytes[0x18 + selector]
    if slot == 0xFF:
        raise NativeCandidateUnavailable("entity lacks position component")
    component = get_ptr(table + slot * 8, length=0x110)
    payload = read(component, 0x110)
    if _u64(payload[:8]) != base + position_vptr_rva:
        raise NativeCandidateUnavailable("position component dispatch pointer mismatch")
    if _u64(payload[0x10:0x18]) != entity:
        raise NativeCandidateUnavailable("position component owner backlink mismatch")
    xyz = struct.unpack("<fff", payload[0x48:0x54])
    if not all(math.isfinite(value) for value in xyz):
        raise NativeCandidateUnavailable("native XYZ contains nonfinite values")

    # Player-system yaw is a CANDIDATE, never a proven body heading.
    backlink = _u64(read(system + 0x3F8, 8))
    if backlink != entity:
        raise NativeCandidateUnavailable("player-system entity backlink mismatch")
    yaw_raw = read(system + 0x304, 4)
    yaw_rad = struct.unpack("<f", yaw_raw)[0]
    if not math.isfinite(yaw_rad):
        raise NativeCandidateUnavailable("player-system yaw nonfinite")
    bearing = ((math.degrees(yaw_rad) + 180.0) % 360.0) - 180.0

    matrix_copy = None
    if include_matrix_candidate:
        # RR2 CurrentBuildActorPoseCandidateReader resolves the actor component
        # from the SAME self entity, with a separate exact-build selector.
        actor_selector = struct.unpack("<i", read(base + actor_selector_rva, 4))[0]
        if not 0 <= actor_selector < 0x60:
            raise NativeCandidateUnavailable("invalid native actor component selector")
        actor_slot = entity_bytes[0x18 + actor_selector]
        if actor_slot == 0xFF:
            raise NativeCandidateUnavailable("self entity lacks actor component")
        actor = get_ptr(table + actor_slot * 8, length=0x3BC)
        if actor == component:
            raise NativeCandidateUnavailable("actor/position components unexpectedly alias")
        # Position +0x94 and actor +0x398 contain separately sourced 3x3 matrices.
        # A bitwise match is a copy/alias candidate, not proof of player body yaw.
        position_bits, position_angle, position_status = _matrix_descriptor(
            payload[0x94:0xB8])
        actor_bits, actor_angle, actor_status = _matrix_descriptor(
            read(actor + 0x398, 36))
        matrix_copy = MatrixCopyCandidate(
            position_bits, actor_bits, position_bits == actor_bits,
            position_angle, actor_angle, position_status, actor_status)

    # A changing pose or owner is refused rather than silently coalesced.
    for address, original in anchors:
        later = read(address, len(original), anchor=False)
        if later != original:
            raise NativeCandidateUnavailable("native owner or pose payload changed during capture")
    observed = float(clock())
    if not math.isfinite(observed) or observed < 0:
        raise NativeCandidateUnavailable("candidate timestamp invalid")
    return PositionFacingCandidate(
        pin.pid, pin.start_utc_ticks, build_sha, key,
        xyz, yaw_rad, bearing, observed, matrix_copy_candidate=matrix_copy,
    )
