# Verification and navigation-quality benchmark
**All metrics below are proposed acceptance criteria**, not verified Taxi results. Defined 2026-11-23.

## Prove the behavior the user actually wants

A completed journey must be observed **from the first movement command through final settled arrival**. Reaching every guide with discrete starts/stops is a **failure** of the smooth-navigation milestone even if destination error is small.

### Required measurements per run

- **Observed pose series:** timestamp/age, game executable hash/build, PID and start, player/unit, zone, XYZ, actor facing, acquisition source and confidence.
- **Requested and actual key states:** W/A/D (plus other supported movement) down/up intervals, key ownership, insert result, STOP latch and independent release.
- **Route progress:** route hash, available corridor, projected arc-length, progress monotonicity, crossed/skipped guides, mandatory-passage evidence and hard-stop state.
- **Tracking quality:** cross-track distance, heading error, speed, angular rate, correction density, A↔D reversals, overshoot, time outside qualified corridor.
- **Latency:** pose age, sampling gaps, decision duration, actuation delay, first observed response, post-release settling time.
- **Outcome:** observed arrival versus worker completion, independent settled position, reason for blocked/stale/stopped; evidence file/hash.

### Metrics and gates

| Measure | Definition | Initial physical gate |
|---|---|---|
| Final XZ error | Euclidean distance from settled player X/Z to requested destination X/Z | ≤0.30 units on **scoped qualified clear ground**; height checked separately |
| Guide stops | Nonmandatory stationary/forward-release episodes attributed to ordinary guides | **0** |
| Continuous forward-duty ratio | Time W held / movement-eligible journey time (exclude explicit hard-stop dwell, pause/blocked states, final settle) | **≥95%** for known clear course; report denominator and sample gaps |
| Running turns | A or D input intervals overlapping W with verified heading change | Required at ≥3 bends |
| Skipped-guide handling | Pass a guide with the projected path without reverse-to-guide correction | All permitted skipped guides accepted |
| Corridor adherence | Current trajectory and predicted sweep remain within verified traversable envelope | Zero unexplained exits; stop/replan on violated bound |
| Hard-stop compliance | Arrive, release, confirm settle at each explicit hard stop | Every hard stop required and ordered |
| Recovery budget | Finite elapsed time and finite retries; no uncontrolled repeating inputs | Bounded and logged |
| Input release | Held input relinquished on arrival, STOP, stale data, identity change, process exit or error | Required in every tested terminal outcome |

Compare travel speed/trip time only on the **same route, build, mount/run mode and conditions**; do not treat a fast but unsafe shortcut as a better result.

## Test ladder

**Level A — pure geometry/unit tests.** Wraparound heading, local/world transforms, curved path projection, close guide spacing, hard-stop order, disconnected polygons, inverted elevation, missing provenance and invalid source hashes.

**Level B — deterministic closed-loop simulation.** Replay the same route under fixed speed/turn-rate/coast models, variable observation delay, key timing jitter, narrow turns, overshoot, stale source, user STOP, game restart and unexpected obstruction. Store JSON summaries and regressions.

**Level C — saved RR2/RiftWorld historical replay.** Use source-hashed, timestamped native XYZ/actor facing/action receipts without live input. Distinguish real observations from synthesized signals. Compare previous stop-start behavior against new continuous tracking.

**Level D — bounded physical RIFT clear-ground tests (explicitly authorized).** Verify LEGION or AMD-DESKTOP *per run*, exact client process/start/build, player, fresh pose, calibration, foreground/window focus and exclusive controller. Begin short straight; then ≥3 bends while W held; record actual keyboard overlaps and game response.

**Level E — verified corridor route and recovery.** Use a locally packaged RiftWorld route with trusted transform and sufficient clearance. Test destination and hard-stop compliance, then controlled obstruction/replanning where evidence exists.

**Level F — packaged acceptance.** Fresh Windows user context, no sibling projects, no Workbridge, no AI, no internet; CLI and GUI remain functional, including STOP, fresh native observation, local map route and trace export.

## Failure cases that cannot be waved away

- W release at each ordinary guide; rotating in place for planned moderate bends.
- Key-down report without independently fresher player XYZ/facing.
- Camera rotation mistaken for actor-facing changes.
- Old process/hash/offset or saved GPS pose reused after game restart.
- Out-of-corridor shortcut called successful because it reached the endpoint.
- Test passes in model but not current physical client.
- Controller times out while key remains held, or a second input owner takes over.
- Guide skipped illegally across mandatory passage, wall, floor change or stop.
- Destination arrival inferred only from the controller's own completion flag.

## Test evidence format

Retain under ignored `artifacts/<run-id>/`: immutable `route.json`, `source-manifest.json`, `telemetry.jsonl`, `input-events.jsonl`, `metrics.json`, optional camera/video evidence. A concise tracked validation note references exact hashes/build/host/date and classifies **simulation**, **offline historical replay**, or **live physical acceptance**. Never store credentials or private session tokens in Git.

## Immediate reproducible baseline

Before adding a full UI, establish a deterministic 3-bend course with optional guides and one separate hard-stop variant. Demonstrate that a stop-turn-run controller fails the smoothness gate despite good final accuracy; new steering must clear both the smoothness gate and the same final-arrival gate.
