# RIFT Taxi — repository working instructions
Established 2026-11-23. This repository is **Rift_Taxi** at `C:\work\Rift_Taxi`.

## Mission and acceptance

RIFT Taxi is a standalone, offline-decision, destination-first RIFT navigation application. A journey runs automatically from start to final destination **without needing an AI agent**. Waypoints are usually pass-through guidance and may be skipped. Only explicitly designated hard stops, mandatory traversal constraints, actual hazards, termination, and final arrival warrant a stop. Optimize smooth movement and steering while running, rather than per-waypoint positional precision.

**No live capability claim without an actual, bounded, fresh live-game receipt.** A simulated trajectory, packet of input, or static map route is not a completed journey.

## Ownership boundaries

- RIFT Taxi **owns** its runtime, navigation logic, packaging, pose/acquisition and input components. Python-first; a narrowly scoped bundled native helper is allowed after timing evidence.
- RR2 (`C:\work\riftreader2`) and RiftWorld (`C:\work\RiftWorld`) are **read-only references** during Taxi work. Never change, rebuild in-place, or alter their running services as an incidental Taxi task.
- Telara Fly (`C:\work\telarafly`) is **permanently read-only**, including Git, builds, running its source checkout, generated caches and metadata. Only RiftWorld's existing **separately owned** TelaraHook performs source research. No direct importer or runtime dependency on Telara Fly is allowed.
- No runtime imports of sibling repositories, path-dependent executables, Git worktrees, Workbridge, ChatGPT, cloud AI or a remote decision service. Existing source can inform a selective, attributed, reviewed Taxi-owned adaptation.
- RiftWorld produces source-backed map/collision/route research; Taxi consumes **versioned local packages** and owns runtime route acceptance and following. Do not duplicate HKX decoding or terrain reconstruction.
- Preserve source SHA, game build, zone, transform, clearance and confidence metadata when importing evidence. A candidate route is not proven traversable merely because a pathfinder returned it.
- Keep Git identity scoped to this repo as `360madden <360madden@gmail.com>`. Do not overwrite global Git settings, edit sibling repos, or create/push a remote without a user request.

## Development loop

1. Choose the smallest valuable outcome and inspect the closest proven prior implementation/evidence.
2. Build a minimal, testable slice; run focused deterministic replay and failure cases.
3. For live tests, verify the physical machine (LEGION versus AMD-DESKTOP), RIFT executable hash/build, PID/start, character and session, reader freshness, window ownership and current authorization. Never reuse stale addresses or pre-patch calibrations.
4. Obtain exclusive input ownership, keep STOP/release independent of normal steering, observe actual down/up and post-release position/facing. No automatic re-arm after a restart or crash.
5. Record measured movement quality (forward-duty ratio, guide stops, simultaneous W+turn, path error, arrival, speed, latency). Avoid broad test suites for tiny changes; use full validation before release claims.
6. Commit meaningful tested slices with concise evidence and known limits. Preserve unrelated work; do not invent progress to occupy workers.

## Architectural guardrails

- **Control and observations are separate channels.** `SendInput` insertion is not verified movement. Cached native coordinates are not fresh pose.
- **Continuous steering** targets a path arc or corridor, not a strict next waypoint. Project motion onto path progress, look ahead and turn while W is down. Point types: optional, guide, mandatory passage, hard stop, final destination.
- **Non-negotiable:** binding to current client and actor, canceled input release, fail closed on stale/contradictory telemetry, bounded time, explicit STOP and independent key-up recovery. Do not replace these controls with a generic time-delay loop.
- NPC/service destinations stay **curated and travel-only**: Sanctum Porticulum Master, personal bank, healer, auctioneer, mailbox (auction collection), and selected storyline NPCs. Auction retrieval uses mailboxes, **not** an invented separate collection NPC; no mail UI automation in the initial scope. Do not delay M1–M3 continuous steering for NPC catalogs.
- No network/API requirement in execution. GUI optional for early milestones; CLI must be scriptable and replayable.
- If future changes demand privileges, system configuration, game memory writes, or intrusive instrumentation, make the impact explicit before acting. The initial product uses read-only observation and controlled standard game input.
- Do not over-engineer planners before clear-ground smooth motion passes. Measure end-to-end latency; optimize the actual bottleneck.
- Document actual failures and corrections, not just successful screenshots.

Before any whole-file edit based on tool-returned text, confirm its read was **not truncated** and reached EOF; M1 already experienced and fixed an accidental partial-read write. Run `python -B -m unittest discover -s tests -v` from the Taxi root after changing Python. The CLI supports **offline replay/import/synthetic steering**, plus opt-in **read-only** `inspect-native-candidate` and bounded `inspect-native-burst` commands requiring a fully pinned process/build/window and producing candidate-only evidence. `rift_taxi.control` supplies an **offline-tested, driver-neutral** input gate with latched STOP and watchdog; its injected test backend never sends RIFT input. `rift_taxi.win32_identity` separately provides a read-only Windows process/window identity candidate (not actor identity or pose), tested with fake endpoints and the test runner's own process. `rift_taxi.native_memory` and `native_candidate` add a bounded read-only Win32 memory session and exact-build player XYZ/yaw **candidate** decoding (synthetic fixture tests only for RIFT fields). `rift_taxi.native_capture` brackets each candidate with two OS identity/focus checks; `native_burst` compares 2–8 separately bracketed samples without asserting real game motion; synthetic tests prove failure behavior, not live RIFT correctness. Native RIFT position freshness and actor yaw qualification, bounded Windows input, independent release and physical game-state evidence remain open. Never claim a running Taxi game controller from these outputs.

Read `docs/PRODUCT_SPEC.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/INTEGRATION_CONTRACTS.md` and `docs/VALIDATION.md` before implementing navigation behavior. For provenance and evidence limitations consult `docs/RESEARCH_IMPORTS.md` and the individual RR2/RiftWorld/Telara Fly handoffs; distinguish existing upstream schema names from **proposed, unimplemented Taxi contracts**.
