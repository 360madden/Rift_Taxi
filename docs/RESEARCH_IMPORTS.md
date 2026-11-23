# Existing research as scaffolding — read-only reuse plan
**LEGION read-only survey 2026-11-23.** These references are development evidence, **not** executable Taxi dependencies or proof of future-build compatibility.

## RR2 — what exists already

Repository: `C:\work\riftreader2`, branch observed as `codex/modular-foundation`, November 23 HEAD observed `ce8f073`.

Verified source for architecture comparison:
- `docs/workflows/physical-waypoints.md`, movement modes section: forward hold through guides, lookahead polyline progression, hard stops, strict 0.30-unit endpoint and 0.50-unit corridor controls. The same document states the existing continuous controller settles an initial turn **before** travel and uses sparse steering nudges with settle intervals; this is not the smooth-turning product target.
- `docs/status.md`, November 22/23 entries: exact-build native XYZ/facing available for physical RIFT 1179 on LEGION; fixed Watch pillar out-and-back route arrived with 0.127 and 0.220 XZ error, zero manual replans, but prior overshoot. Imported RiftWorld Watch destination also arrived with 0.260 error under 0.30 tolerance.
- Retained 2026 experiment evidence: OS `SendInput` key delivery, true player movement, and failures involving timing, stale references, lost focus and lease conditions. Successful insertion does not imply movement.
- Reader and controller source are design candidates for **selective reviewed adaptation** only: retain current-build identity, actor facing semantics, freshness, input down/up timing, independent release and STOP, but avoid cloning the older stop-turn-steer architecture wholesale.

**Taxi import policy:** First record exact upstream file/commit/hash and test behavior; design a Taxi-owned, independently packaged implementation or small approved native helper. Check source licenses and attribution before copying. Do not use absolute sibling paths in installed code. A successful historical pose root is never an automatically supported post-patch root.

## RiftWorld — what exists already

Repository: `C:\work\RiftWorld`, consulted read-only.

Grounded architecture:
- `README.md` and `ARCHITECTURE.md` describe WorldPatch from source geometry, an offline Recast/Detour navigation build, persisted `detour.bin` and an RR2 review adapter.
- WorldPatch, navigation build, candidate path and retained provenance are a useful **offline export boundary**, not a promise of fully qualified world collision.
- November 22 project status records one LEGION runtime Havok pillar-contact observation; broader static obstacle completeness and fully connected zone navigation remain unqualified.
- Existing RiftWorld → RR2 Watch destination was replayed and physically adopted in a scoped LEGION test.

**Taxi import policy:** Consume validated local **data packages** with explicitly qualified transforms, source/build hashes, corridor/height/clearance and route status. Do not modify RiftWorld to force a Taxi format before confirming the existing export adapter is sufficient. Never mutate `C:\work\telarafly` or take over its reference-repo work.

## Tooling and Windows

- Verified workstation: `LEGION`, Windows; local Git author `360madden <360madden@gmail.com>`.
- RR2's current Python-based Waypoints experiments are useful reference, but its installed native reader or local calibration files in `.local` must never be a runtime requirement for Taxi.
- Reuse selected **facts, tests, wire formats and techniques**, not developer daemons or absolute machine paths.
- If a map or calibration must be refreshed at build time, document a separate reproducible import command. A distributed version must still run without the source checkout.

## First targeted source audit (implementation kickoff)

1. Pin RR2 native read commands/position-and-facing source, actual Windows held-key controller and key-release implementation to tested commits and read their failure receipts.
2. Identify a small bounded LEGION trace: timed XYZ, actor heading, actual W/A/D down/up, same game/build and verified start/end samples.
3. Inspect RiftWorld's versioned WorldPatch and persisted Detour schema for transform/corridor/clearance fields; record missing evidence as unavailable, not invented.
4. Write **Taxi's own trace schema and simulator**, compare candidate controllers using the same replay.
5. Selectively port a small tested observation/input boundary, then validate full runtime independence.

Do not start broad new memory scanning, collision extraction or multi-agent process infrastructure solely because Taxi is a new repository.
