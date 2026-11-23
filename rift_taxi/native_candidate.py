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
_BUILD_LAYOUTS = {
    "1935a05c9db6d468e34e0055014a4a99c1b5afceb1695884e24600f5c20a4be8": (
        0x33624A8, 0x33623E0, 0x2F588A0, 0x26B4FB0),
    "df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01": (
        0x3373C68, 0x3373BA0, 0x2F698A0, 0x26C35C0),
}


class NativeCandidateUnavailable(RuntimeError):
    """Build/ownership/field evidence was inadequate for a native candidate."""


class CandidateReadSource(Protocol):
    pin: ProcessPin
    module: MainModule

    def read_exact(self, address: int, size: int) -> bytes: ...


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
) -> PositionFacingCandidate:
    """Read an exact-known-build owner/XYZ/yaw candidate without game actions.

    This object is intentionally NOT a LivePose and cannot be passed directly
    to HeldInputController, whose verified yaw/freshness gates remain required.
    """
    if not isinstance(source.pin, ProcessPin) or not isinstance(source.module, MainModule):
        raise NativeCandidateUnavailable("pinned process and module identity required")
    pin = source.pin
    base = source.module.base
    size = source.module.size
    build_sha = pin.executable_sha256.lower()
    layout = _BUILD_LAYOUTS.get(build_sha)
    if layout is None:
        raise NativeCandidateUnavailable("unqualified executable build; no offsets available")
    manager_rva, system_rva, position_selector_rva, position_vptr_rva = layout
    if size <= max(manager_rva + 8, system_rva + 8, position_selector_rva + 4,
                   position_vptr_rva + 8):
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
        xyz, yaw_rad, bearing, observed,
    )
