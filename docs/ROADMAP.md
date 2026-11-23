# Development roadmap — from bootstrap to autonomous taxi
**Planning baseline: 2026-11-23.** M0 documentation/bootstrap is complete; M1 is partially implemented offline. M2–M6 remain planned. No estimates substitute for milestone evidence.

## Product success hierarchy

1. **Reliable end-to-end destination arrival** through an admissible route.
2. **Smooth continuous forward progression** across guides; steering during the run.
3. **Respect mandatory topology and explicitly requested hard stops.**
4. **Automatic local diagnosis and recovery** of recoverable deviations.
5. **Useful destination UI, installation and replayability.**

Note: arrival is not permission to traverse unknown geometry. Failure-to-plan is better than pretending an unqualified shortcut is open.

## Critical path

`M0 → M1 → M2 → M3 → M4 → M5 → M6`. Implement narrow vertical slices and run replay in parallel with live-scope investigation. Do not postpone a working multi-bend controller until every zone is mapped.

### M0 — Repository, requirements and evidence baseline
**Status:** Bootstrap and expanded source/architecture documents completed. Offline trace contracts, CLI and replay fixtures now implemented under M1; no live native reader or movement actuator exists.
- Git main, scoped author, README/AGENTS, specs, architecture and validation plan.
- Identify exact reusable RR2 native pose/facing and input behavior and RiftWorld route export contracts, with upstream commits/file hashes. **Completed as a read-only source audit** in [research index](RESEARCH_IMPORTS.md), [RR2 handoff](RR2_HANDOFF.md), [RiftWorld handoff](RIFTWORLD_HANDOFF.md) and [Telara Fly reference](TELARA_FLY_REFERENCE.md). Recheck hashes and actual raw receipts at implementation time.
- Define minimal typed trace fixtures and clear source attribution; do not copy entire upstream applications. Existing upstream formats and **proposed Taxi** contract fields are separated in [integration contracts](INTEGRATION_CONTRACTS.md). Actual fixtures remain M1 work.
**Exit:** documentation coherent, Git initial commit, no runtime dependencies silently introduced.

### M1 — Standalone pose, input and trace/replay substrate [P0]
**Progress (Nov 23):** Offline CLI, strict `taxi.motion-trace/1`, source-hashed RR2 import, stop/go metrics, synthetic Pure Pursuit preview, a **driver-neutral W/A/D + watchdog STOP gate**, read-only Win32 **process/window identity inspector**, **bounded native memory access**, **source-pinned XYZ/yaw candidate decoder**, optional **position/actor raw matrix comparison**, and **explicit pinned one-shot/matrix-enabled burst read-only capture commands** and a **five-phase offline-facing comparison CLI** are implemented. **A physical Taxi-owned RIFT read-only XYZ/yaw and 9/9 actor/position matrix candidate capture succeeded on LEGION**, including a stable four-sample burst. A separate Windows **W/A/D scan-code backend** now exists behind explicit verified-pose arming and inert sender tests. A separate-process release-supervisor **prototype** now passes TTL/pipe-EOF/STOP/mutex tests with simulated senders (**261/261 regressions**). An optional read-only **W/A/D keyboard-state snapshot** now accompanies the same-handle native series; the third live 24-sample run collected 48 W/A/D polls per key with no observed down states, and 261 regression tests pass. It never sends input or proves game consumption. [Key observation evidence](M1_READONLY_MANUAL_KEY_OBSERVATION_LEGION_2026-11-23.md). A new **same-handle 24-sample native time series** on the physical RIFT client reached a **99.8 ms median observed sample gap**, rechecking process epoch/HWND before and after each candidate; no gameplay input was sent and this stationary experiment does not qualify freshness. [Pinned live series](M1_LIVE_NATIVE_SERIES_LEGION_2026-11-23.md). A newer **read-only live one-shot and 4-sample current-player cache-refresh guard study** found both known top-level conditional refresh guards zero at each sample. Another **same-process/same-owner native capture** reconstructed the actor model-world translation within float32 precision, and a source-hashed offline comparison found changed XYZ/yaw/matrices across 24 minutes even though both top-level guard pairs remained zero. [Changed-state handoff](M1_ACTOR_TRANSLATION_CHANGED_STATE_LEGION_2026-11-23.md). **Other possible writers, passive XYZ freshness, body-heading qualification, real crash/late-DOWN release behavior and physical game-input acceptance remain open.** [M1 implementation](M1_IMPLEMENTATION.md) · [Control boundary](M1_CONTROL_BOUNDARY.md) · [Windows identity probe](M1_WIN32_IDENTITY.md) · [Native read-only candidate path](M1_NATIVE_READONLY.md) · [Actor/position matrix candidate](M1_MATRIX_CANDIDATE.md) · [Offline-facing signature](M1_FACING_SIGNATURE.md) · [First physical native candidate](M1_LIVE_NATIVE_LEGION_2026-11-23.md) · [Win32 input backend](M1_WIN32_INPUT.md) · [External release supervisor](M1_RELEASE_SUPERVISOR.md) · [Live refresh-guard evidence](M1_LIVE_XYZ_REFRESH_GUARDS_LEGION_2026-11-23.md) · [Actor-world changed-state evidence](M1_ACTOR_TRANSLATION_CHANGED_STATE_LEGION_2026-11-23.md) · [Movement timing and addon API audit](M1_MOTION_TIMING_AND_TELEMETRY_AUDIT_2026-11-23.md) · [Pinned live native series](M1_LIVE_NATIVE_SERIES_LEGION_2026-11-23.md) · [Read-only W/A/D observations](M1_READONLY_MANUAL_KEY_OBSERVATION_LEGION_2026-11-23.md).
- Implement `taxi replay` reading deterministic observation/input/route traces; publish first benchmark JSON. First inspect original Legion pose/facing plus key-down/up source receipts for **same-clock or explicitly calibrated cross-clock timestamps**; never synthesize omitted fields while labeling them historical.
- Implement Taxi-owned exact-process/build/player/zone pose and actor-facing acquisition, initially on verified Windows RIFT build.
- Implement independently releasable bounded W/A/D state control with STOP; capture actual timing and fresh post-action movement evidence.
- Measure acquisition and actuation latency, update frequency, stale/frozen source behavior and restart rebind.
**Exit:** On a properly authorized physical client, fresh native XYZ/facing + short controlled movement + independent settled/released confirmation, entirely without sibling processes. Missing/restarted game yields clean unavailable, not cached data.

### M2 — Continuous straight travel and final arrival [P0]
- Run one open-ground start-to-destination segment: W stays held through the travel span.
- Implement measured speed/coast and final approach; prevent overshoot while distinguishing source lag from character motion.
- Produce trajectory replay, action trace and metric summary.
**Exit:** Repeated scoped physical runs reach destination with measured final tolerance; no intermediate W release, release succeeds at finish and STOP.

### M3 — Smooth multi-bend trajectory tracking [P0, PRIMARY PRODUCT MILESTONE]
- Add route arc-length projection and lookahead/trajectory controller, compare Pure Pursuit and Stanley in deterministic replay.
- Steer with A/D **concurrent with W** through at least three gentle/moderate bends; tune corrections to prevent repeated stop/turn.
- Auto-skip/merge ordinary guide points; implement explicit hard-stop semantics with resume to final destination.
- Quantify real yaw/translation response and controller delays. Add recovery from mild lateral deviation without route-index rollback.
**Exit:** On a preverified clear-ground physical course with **≥3 bends**, zero unnecessary stops at guides; W is active for **≥95% of movement-eligible time**; steering actions overlap forward travel; final arrival independently confirmed; no STOP/release failure or dangerous oscillation. If target fails, publish measured trace and fix the cause; do not declare success from unit tests.

### M4 — Local destination planning from verified world packages [P1]
- Define/version package loader for RiftWorld WorldPatch/Detour-derived evidence; include hashes, transforms, clearance and zone/build scope. Start with a pre-exported scoped corridor and original source manifests; a raw Detour binary requires independently qualified local runtime-reader compatibility.
- Local route query + corridor/trajectory generation, preserving mandatory passages, elevations and hard stops.
- Prune guide points only when the smoothed trajectory remains within verified free space.
- Introduce a small **curated service-destination registry** (Sanctum Porticulum Master, personal banker, healer, auctioneer, separate **mailbox for auction collection**, selected main-story quest NPCs); verify reachable approach points. Do **not** build a general NPC search system or assume that collecting auction items uses an NPC.
- Test a second independent destination route without RR2/RiftWorld/Workbridge installed or active.
**Exit:** Select destination, plan and follow a scoped Detour-backed corridor from local package with fresh final-arrival evidence; invalid/stale packages fail clearly. Candidate routes not falsely promoted to cleared routes.

### M5 — Robust local recovery and constrained avoidance [P1]
- Detect stopped progress, lateral drift, lost pose, narrow bends and blockage with distinct counters.
- Bound correction/replan attempts; choose a verified alternate corridor when available; keep destination primary. Include the **November 23 missing banner pole** as a negative world-coverage case; do not assume render-visible corridor means collision-free.
- Add dynamic avoidance only when independently located obstacle data are timely enough.
**Exit:** Seeded replay cases and physical bounded cases show appropriate recovery versus blocked outcomes; never loop indefinitely at an obstacle or silently bypass hard stops.

### M6 — Taxi UI, distribution and documented operation [P2]
- Minimal PySide6 dark UI: current pose, destination search, route preview, Go/Pause/STOP, progress, reasoned blocked state and trace view.
- Packaged Windows portable app or installer with bundled Python/runtime/native helpers/maps; configuration, diagnostics and export.
- Test on a Windows install **without** Python developer environment, sibling repos, Workbridge or network.
**Exit:** User can launch, pick destination, run, stop, observe the outcome and inspect a reproducible receipt with no AI.

## Next three concrete tasks (do these first)

1. **Complete M1 live boundaries.** Taxi-owned current-build read-only XYZ and matrix observations are now demonstrated on LEGION; a bounded W/A/D Win32 sender is implemented but unarmed in physical tests. Use the bounded pinned native series and opt-in Windows W/A/D snapshots to bracket an independently observed manual action with same-session native-before/native-after readings; the stationary series and two older snapshots lack an action-clock timeline, so do not promote them to motion proof. Account for `Inspect.Unit.Detail` possibly refreshing cached XYZ, qualify actor/zone identity, qualify **true physical release and crash/late-DOWN recovery** beyond the new independent-process lease/mutex prototype, and then obtain a controlled insertion/readback receipt. The serialized `taxi.pose/1`, `taxi.control-event/1` and `taxi.journey/1` live receipts remain unimplemented.
2. **Source-verified movement model.** One RR2 build-1179 original JSONL receipt with 72 timed poses and 14 key-send events is imported, hash-validated and analyzed with a new temporal-metrics CLI: 15 stable W-held speed intervals show a **6.632 source-units/s median**, with first changed XYZ samples about 29–31 ms after W-down in that short historical window. These are **candidate timing associations, not proven input response/physics**; yaw and W+A/D overlaps are absent. Expand to independently qualified same-epoch sources and turn/coast tests before claiming a calibrated model. The 15-point bridge route remains a **staged** historical composite.
3. **Closed-loop steering comparison.** A synthetic Pure Pursuit lookahead intent preview exists, but does not simulate physics or actuate A/D. Build a source-calibrated closed-loop simulator and Stanley-style comparator, record path/corridor error and true forward-key duty, then qualify a controller with bounded physical tests.

## Intentional sequencing

- **Not first:** polished Taxi GUI, map editor, general NPC research takeover, another world exporter, generalized microservice framework, full Silverwood travel, or reimplementing old RR2 controller behavior.
- **Independent optional research:** observe NPC trajectories as a *benchmark*, not a claim that Taxi can call internal NPC AI.
- **Failure feedback:** a failed multi-bend physical run takes priority over feature expansion; fix the measured control problem before expanding to new world zones.
- **Git:** small meaningful commits, source provenance for imported algorithms, no generated captures or sensitive local configs in commits. GitHub remote is optional and separate.
