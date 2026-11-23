# Research reuse index — sibling repositories as scaffolding

**Source check:** 2026-11-23 on verified LEGION. Every sibling repository was inspected **read-only**; this is a one-time documentation checkpoint, not an assumption that their HEADs will never change.

## Repository checkpoints

| Repository | Observed branch / HEAD | Primary role for Taxi | Runtime dependency? |
|---|---|---|---|
| `C:\work\riftreader2` | `codex/modular-foundation` / `a192b839dc7c08689008051110484e07a63c1f8e` (refreshed; initial audit at `6b4e840`) | Current build-1179 live read/input evidence, route failures, source receipts | **No** |
| `C:\work\RiftWorld` | `main` / `0f154804eabf54608216c2c84a05468d8076a5cb` | Source geometry, transforms, Detour/collision route evidence, NPC candidates | **No** |
| `C:\work\telarafly` | `master` / `41aacc0485ed2c90ceb1df7cdb7653853cc52d18` | Historical Unity/C# asset/CDR/NIF/OBJ implementation reference | **No, permanently read-only** |

**Git status at survey start:** RR2 `ahead 83` of its local tracking ref, RiftWorld `ahead 20`, Telara Fly clean, Taxi clean before these edits. RR2 acquired additional commits during this documentation pass; the refreshed RR2 checkpoint above supersedes the original SHA, and `docs/status.md` is not an immutable artifact. A local tracking ahead count is not proof of remote-server state; we performed no fetch or push.

The exact surveyed **file hashes** are in the per-repository guides:
[RR2_HANDOFF.md](RR2_HANDOFF.md) · [RIFTWORLD_HANDOFF.md](RIFTWORLD_HANDOFF.md) · [TELARA_FLY_REFERENCE.md](TELARA_FLY_REFERENCE.md).

## Minimal ownership split

`RiftWorld research/source → offline export → Taxi-owned local immutable world bundle`

`RR2 native/action research → offline trace import + selective, verified implementation knowledge → Taxi-owned reader/controller`

`Telara Fly historical CDR/NIF/asset source → **RiftWorld's existing TelaraHook** → RiftWorld world patch → Taxi import`

No change to source repos is required to *start* Taxi, and no source repo is required to **run** Taxi after installation. If new evidence extraction is needed, maintain source ownership: never make it a Telara Fly edit, and do not fork another Havok/CDR implementation into Taxi.

## Evidence hierarchy for importing facts

| Class | Examples | Allowed product use |
|---|---|---|
| **Source-only fact** | CDR scene name, asset hash, OBJ mesh, historical Magelo NPC coordinate | Map research, *not* live movement admission |
| **Generated candidate** | Complete Recast path in render geometry, native candidate yaw/XYZ from a frozen process | Offline route preview or replay; require qualification |
| **Independent physical observation** | Same-epoch player moved and settled; measured Havok face contact; native/other channel agreement | Scoped regression / calibration for the recorded build/route/host |
| **Qualified runtime Taxi input** | Fresh current actor, reader, world transform, corridor, key ownership, height and goal under Taxi's own checks | May start/continue a bounded journey |
| **Qualified Taxi completion** | Timed key release + advancing fresh final pose + all hard-stop/route obligations | Only state that merits `ARRIVED` |

A high hash integrity/confidence score does not establish current game identity or physical clearance. Capture machine, process start and field semantics still matter.

## Source-to-Taxi implementation handoff

| Intake priority | Evidence/source | Concrete output | Reject if |
|---|---|---|---|
| **P0 — actor pose** | RR2 `scripts/physical_rift.py` + published source/test for `position`, `facing` | Taxi own read-only X/Y/Z + actor yaw + acquisition age | Stale build/PID/player, unqualified actor yaw |
| **P0 — control** | RR2 `WindowsControlDesktop.cs` + `continuous_move.py`; timing failure records | Taxi exclusive input, finite W/A/D held states, verified release, STOP | Not foreground, stale owner, release fault |
| **P0 — motion trace** | Source-hashed LEGION movement calibration, pillar route and bridge sections | Taxi replay fixture: same-clock sample and input event timeline | Missing raw source, mismatched epochs or no actual key timing |
| **P0 — control quality** | RR2 sparse-controller evidence | Continuous Pure Pursuit/Stanley comparison with consistent physics | Only passes final accuracy but stops at guides |
| **P1 — map data** | RiftWorld `riftworld.patch/1` and `candidate-path/1`, `navigation-build/1` | Local `taxi.world-bundle/1` with verified transform and source IDs | Partial path, unknown floor, unqualified source-to-native alignment |
| **P1 — obstacle checks** | RiftWorld mapped obstacle layers and verified route/capsule reports | Scope-bound clearance/evidence, explicit unknown cells | Missing actors/collision shape and unsafe shortcut assumption |
| **P2 — NPC service anchors** | RiftWorld NPC location catalog, RR2 nearby name/position data | Few reachable service-approach records | Unverified current NPC role/floor/presence |
| **Research only** | Telara Fly CDR/NIF/OBJ/asset C# | Provenance and gap investigation | Source-tree mutations, running another asset streamer in Taxi |

Do not copy source with unknown license terms as a shortcut. Preserve attribution and review source licenses before porting implementation. Most fields are better reimplemented via small verified Taxi-owned boundaries.

## P0 regression set

**November 22 LEGION:** successful Watch pillar round trip with final **0.127/0.220** XZ error (yet corners settled and an overshoot was corrected). **November 23 LEGION:** imported Detour Watch destination with **0.260** XZ error. **November 23:** staged Guardian bridge crossing with 15 points and one absent banner pole; **no uninterrupted one-journey acceptance**. These give a strong baseline for measuring Taxi's actual improvement rather than claiming RR2 already feels like a taxi.

Refer to exact source hierarchy: `RR2/docs/status.md`, `RR2/docs/workflows/physical-waypoints.md`, `RiftWorld/START-HERE.md`, `RiftWorld/HANDOFF-2026-11-23-SANCTUM-BRIDGE.md`. The generated route file and game receipts may be ignored by Git and not present in another checkout—reopen hashes/files before treating them as replay inputs.

## Development gates / next steps

1. **M1:** schemas + offline CLI and original RR2 trace importer; inspect which recorded source material really includes time-aligned W/A/D, pose and yaw. Mark missing fields unavailable. Build standalone Taxi-owned current-client reader and input/release.
2. **M2–M3:** controller: sustained W, dynamic lookahead, A/D simultaneously while W held; center progress on corridor arc-length rather than guide index. Physical test with ≥3 bends and **zero unnecessary guide stops**.
3. **M4:** package scoped RiftWorld map/navigation data and prove offline import plus real physical route without source repositories running. Do not start with arbitrary Silverwood.
4. **M5–M6:** measured local obstruction recovery, small curated services and standalone PySide6 distribution.

**Read first:** [ARCHITECTURE.md](ARCHITECTURE.md), [INTEGRATION_CONTRACTS.md](INTEGRATION_CONTRACTS.md), [VALIDATION.md](VALIDATION.md), [ROADMAP.md](ROADMAP.md). No other repository was edited or launched in the read-only source audit.
