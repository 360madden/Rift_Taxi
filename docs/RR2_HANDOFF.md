# RR2 research handoff for RIFT Taxi

**Read-only source audit:** LEGION, 2026-11-23. **RR2 repository:** `C:\work\riftreader2`, `codex/modular-foundation`; audit began at `6b4e840b2e476599bfd2726d9546dd884f7615f7` and its dynamic status page was rechecked after upstream advanced to `a192b839dc7c08689008051110484e07a63c1f8e`. Original RR2 files/artifacts are **not** dependencies of Taxi's installed application.

## What RR2 has actually established

| Area | Verified RR2 evidence | What Taxi can build from it | Limit |
|---|---|---|---|
| Physical actor XYZ / facing | `scripts/physical_rift.py` exposes exact-build `position` and `facing` read commands; newer build-1179 LEGION movement uses them | Taxi-owned current-build read-only pose and actor-yaw acquisition | Old locators cannot be reused after game builds/process epochs change |
| Longitudinal input | Physical Waypoints continuous controller uses sustained W along spans, with native feedback and release | Input/state model, timestamps, independent STOP/release, native before/after proofs | Existing steering still settles initial turn and uses sparse in-run nudges |
| Guide semantics | `run_continuous_route` accepts pass/stop kinds, treating last point as stop | Preserve guide vs hard-stop separation while making arc-length progress primary | RR2's automatic corner pause may stop for geometry / speed constraints |
| Known local navigation | Watch pillar fixed forward/return, imported Detour destination with verified end poses | Physical regression routes and evidence qualification | Narrow route/specific build; not whole-zone autonomy |
| Nearby unit read | Native unit-positions, keyed unit-names, unit-levels, selected target and NPC survey tooling | Later curated NPC destination recognition | Loaded subset only; name != role, live presence or approachable service |
| Replay/diagnostics | Saved source reports, hashes, fixed player/process, exit/readback receipts | Recorded source-normalized test fixtures and fault reproduction | Artifacts under `artifacts/` are often untracked; commit does not prove artifact backup |

### Exact native reader command map

In `scripts/physical_rift.py`, `NATIVE_READS` maps these public choices to the C# executable: `position → sample-current-position`; `facing → sample-current-facing`; `orientation → sample-current-orientation`; `actor-pose → sample-current-actor-pose`; `unit-positions`; `selected-position`; `player-context`; `selected-target`; `unit-names`; `unit-levels`; `zone-context`, and others. Every result is labeled by a *distinct source schema*, for example `native-current-facing-summary/1` and `native-current-position-candidate-summary/1`. These are **RR2 formats**, not yet Taxi's schema.

`RR2_NATIVE_READER` permits a separately published native executable, with checks before selecting RIFT; this is useful for test provenance, **not** a runtime parameter or default path for Taxi. Runtime Taxi must package its own independently tested reader.

Current physical-read workflow and sample commands live in `docs/workflows/development.md`. It distinguishes a physical LEGION process from guests and read-only sample receipts from live game actions.

### Windows input and release

`src/RiftReader2.Live/Control/WindowsControlDesktop.cs` provides bounded native Windows input and pinned process/window checks; its key-control path uses scan-code `SendInput`, and a release-only background `WM_KEYUP` fallback is expressly labeled "queued-game-consumption-unverified." At `IsCurrent()` it checks foreground/window/owner and geometry; no raw insertion count proves the character moved.

`scripts/continuous_move.py` refuses further control if an earlier held-key release remains unverified, tracks native action launch versus trusted result, and preserves an explicit separate STOP file. `run_continuous_route` admits typed pass/stop points with a shared route reservation and deadline. Taxi should **reuse lessons and independently implement** the release behavior rather than calling this script as its movement engine.

### Why RR2's current navigation is not the Taxi target

`docs/workflows/physical-waypoints.md`, "Movement modes and map destinations," describes a continuous W span through ordinary guides, but **initial turn is settled before running**, corrections are intentionally sparse and separated by settling time, and the final 1.5 source units use a straight approach. Its corridor guard can halt a tight turn rather than dynamically negotiate it. A 72.802-unit eight-leg reference reports **zero A/D corrections inside forward holds**—a good straight stability result, **not** smooth in-run cornering evidence. The physical Watch pillar out-and-back settled at its turns: precise arrival and zero manual replans are not evidence of uninterrupted motion.

Implementation source `scripts/continuous_move.py` computes corner runout with response/coast allowances and may mark tight/adjacent incompatible corners as *automatic pauses*. `run_continuous_route` treats a `pass` point as traversable guidance, but the optimizer's segmentation still prioritizes reliable local settling over the continuous NPC-like cornering sought here.

**Taxi-specific research task:** use the same recorded XYZ/yaw and W/A/D down/up trace as a regression comparison between RR2's route behavior and a new arc-length/predictive steering controller.

## Actual movement receipts (historical, not Taxi results)

- **November 22, LEGION, build 1179:** fixed Watch pillar route completed outbound/return with final XZ errors **0.127** and **0.220** source units, key release and zero manual replans after overshoot recovery. See RR2 `docs/status.md` and RiftWorld `START-HERE.md`.
- **November 23, LEGION:** a Detour-derived Watch destination was adopted and completed with fresh final XZ error **0.260 ≤ 0.300**, but the runner still made turns/stops. See RR2 `docs/status.md` and RiftWorld `START-HERE.md`.
- **November 23, LEGION:** staged Watch-temple → Guardian bridge → Tavril Plaza traversal with **15 measured points**, median east-half moving speed **6.1 source units/s**. Its full continuous replay is **untested** and banner pole was absent from assembled map. See RiftWorld `HANDOFF-2026-11-23-SANCTUM-BRIDGE.md`. Never call this one continuous demonstrated trip.
- Historical attempts document timing failures, expired control leases and feedback delays. Query `docs/validation/*` and the supplied November 10 movement-input research report before assigning any failure to RIFT's unknown internal input handling.

## Intake checklist for Taxi M1/M2/M3

1. Locate the precise source+test for `position`, `facing`, actual key-down/up, STOP and background release. Pin commit SHA and **executable SHA/target build** for each retained receipt. Recheck source licensing before copying code.
2. Read and normalize same-epoch source receipts into Taxi `PoseSample` and `InputEvent`: host, process PID/start, build SHA, player key, XYZ, actor yaw, monotonic sample times, actual W/A/D transitions and original source hash. Distinguish camera versus actor yaw.
3. Compute measured forward speed, yaw/s by key direction, release coast, sample age and input-to-observation lag. No extrapolation across mounts, speed toggles or builds.
4. Create replay regressions: straight course, multiple bends, guide skipping, hard stop, overshoot, long input hold, stale pose, focus loss and release failure.
5. Build **Taxi-owned** read-only + input boundary. Test on LEGION with fresh game identity before claiming M1 live operation. Do not import `scripts/continuous_move.py` wholesale: it preserves the old sparse steering policy.

## NPC evidence useful later, not M1–M3 priority

`scripts/physical_nearby_units.py` joins bounded native unit positions with exact keyed name reports. A November 21 AMD-DESKTOP sample saw **17 nearby units / 15 named candidates** within 35 units. On LEGION, November 22 reports include 10 matching native level candidates in a scoped batch. `scripts/prepare_physical_npc_survey.py` prepares nonce-bound addon survey; activation/advancing live NPC-source agreement remained pending in the latest November 23 status.

NPC label, quest role, banker/mailbox function, present location, same floor and path clearance need separate evidence. Temporary unit IDs are not durable destination IDs. Source guidance: `docs/reference/physical-native-nearby-units-2026-11-21.md`, `docs/reference/physical-nearby-npc-correlation-2026-11-21.md`.

## Pinned source register (evidence, not packaged assets)

| Relative path at observed RR2 HEAD | SHA-256 (local file) | Why read |
|---|---|---|
| `scripts/physical_rift.py` | `a994eaa48cfc5556c07695a247186e433fe299ae9588b1ffaa3acffed105bb66` | Exact native reader names and source schema labels |
| `scripts/continuous_move.py` | `b1a0c149f1398e82b5bb835dc4de47d4d2d8df7a1d006a9990a39ff5999823b7` | Existing movement policy, segmentation, STOP and receipt contracts |
| `src/RiftReader2.Live/Control/WindowsControlDesktop.cs` | `7152c6db5222fe1bdc6ca2c8a7f817a043ccdea0f534f6f6dc2617ba4bbdd83e` | Win32 ownership/release semantics |
| `docs/workflows/physical-waypoints.md` | `06e4f8ffb87a310dbc8facc587a3e57948014b762346eb5a5edc5eb8d5a2a6ef` | Pass/stop guides, sparse steering and bounded corridor rules |
| `docs/reference/physical-native-nearby-units-2026-11-21.md` | `04ea4d9ab508e288c7d1594ef6b9198617618f48721a174b35d5cfe3a7bfdcb8` | NPC readout and limitations |
| `docs/status.md` | `e997df47e25bc37e632dbcbfbfbaca1e83b513a2d61e7c313e22efe2320bbed9` | Latest verified physical results at audit time |

**Live source drift:** RR2's `docs/status.md` changed while this read-only review was underway; the table pins its later observed hash, while older extracted route results remain explicitly dated and scoped. Recheck HEAD before implementing; don't treat live `docs/status.md` as immutable.

No sibling repo was changed during this source survey. These hashes verify **surveyed file bytes only**; source builds, generated captures and field behavior must be independently validated for the eventual Taxi runtime.
