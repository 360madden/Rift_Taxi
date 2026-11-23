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
**Progress (Nov 23):** Offline CLI, strict `taxi.motion-trace/1`, source-hashed RR2 import, stop/go metrics, synthetic Pure Pursuit preview, a **driver-neutral W/A/D + watchdog STOP gate**, read-only Win32 **process/window identity inspector**, **bounded native memory access** and **source-pinned XYZ/yaw candidate decoder** are implemented (**98/98 tests**, including real Win32 self-process metadata and read-only buffer tests). **RIFT-live XYZ freshness, body-heading qualification, Windows input, independent release proof and physical acceptance remain open.** [M1 implementation](M1_IMPLEMENTATION.md) · [Control boundary](M1_CONTROL_BOUNDARY.md) · [Windows identity probe](M1_WIN32_IDENTITY.md) · [Native read-only candidate path](M1_NATIVE_READONLY.md).
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

1. **Complete M1 live boundaries.** The trace/CLI and driver-neutral W/A/D/STOP watchdog gate are offline-tested. Next run read-only current-build RIFT observations using Taxi's new native candidate decoder, independently qualify body-facing yaw/XYZ freshness and bind them to the OS desktop identity. Then implement a bounded Windows backend with external release supervision and obtain physical readback. The serialized `taxi.pose/1`, `taxi.control-event/1` and `taxi.journey/1` live receipts remain unimplemented.
2. **Source-verified movement model.** One RR2 build-1179 original JSONL receipt with 72 timed poses and 14 key-send events is imported and hash-validated. Expand to multiple same-epoch sources, independently qualify actor yaw and actual game response, and measure turn/coast/latency before claiming calibrated physical motion. The 15-point bridge route remains a **staged** historical composite.
3. **Closed-loop steering comparison.** A synthetic Pure Pursuit lookahead intent preview exists, but does not simulate physics or actuate A/D. Build a source-calibrated closed-loop simulator and Stanley-style comparator, record path/corridor error and true forward-key duty, then qualify a controller with bounded physical tests.

## Intentional sequencing

- **Not first:** polished Taxi GUI, map editor, general NPC research takeover, another world exporter, generalized microservice framework, full Silverwood travel, or reimplementing old RR2 controller behavior.
- **Independent optional research:** observe NPC trajectories as a *benchmark*, not a claim that Taxi can call internal NPC AI.
- **Failure feedback:** a failed multi-bend physical run takes priority over feature expansion; fix the measured control problem before expanding to new world zones.
- **Git:** small meaningful commits, source provenance for imported algorithms, no generated captures or sensitive local configs in commits. GitHub remote is optional and separate.
