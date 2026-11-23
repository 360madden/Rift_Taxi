# RIFT Taxi — repository working instructions
Established 2026-11-23. This repository is **Rift_Taxi** at `C:\work\Rift_Taxi`.

## Mission and acceptance

RIFT Taxi is a standalone, offline-decision, destination-first RIFT navigation application. A journey runs automatically from start to final destination **without needing an AI agent**. Waypoints are usually pass-through guidance and may be skipped. Only explicitly designated hard stops, mandatory traversal constraints, actual hazards, termination, and final arrival warrant a stop. Optimize smooth movement and steering while running, rather than per-waypoint positional precision.

**No live capability claim without an actual, bounded, fresh live-game receipt.** A simulated trajectory, packet of input, or static map route is not a completed journey.

## Ownership boundaries

- RIFT Taxi **owns** its runtime, navigation logic, packaging, pose/acquisition and input components. Python-first; a narrowly scoped bundled native helper is allowed after timing evidence.
- RR2 (`C:\work\riftreader2`) and RiftWorld (`C:\work\RiftWorld`) are **read-only references** during Taxi work. Never change, rebuild in-place, or alter their running services as an incidental Taxi task.
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
- No network/API requirement in execution. GUI optional for early milestones; CLI must be scriptable and replayable.
- If future changes demand privileges, system configuration, game memory writes, or intrusive instrumentation, make the impact explicit before acting. The initial product uses read-only observation and controlled standard game input.
- Do not over-engineer planners before clear-ground smooth motion passes. Measure end-to-end latency; optimize the actual bottleneck.
- Document actual failures and corrections, not just successful screenshots.

Read `docs/PRODUCT_SPEC.md`, `docs/ROADMAP.md` and `docs/VALIDATION.md` before implementing navigation behavior.
