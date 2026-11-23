# Verification and navigation-quality benchmark
**Physical movement metrics below remain proposed acceptance criteria**, not verified Taxi live results. As of 2026-11-23, the repository has **271 passing regression tests**, including an inert-tested Win32 W/A/D scan-code backend and a separate child-process release lease with actual Windows process, synthetic parent-crash and delayed-DOWN compensation regressions. **Taxi itself obtained real read-only native XYZ/yaw, matrix, cache-refresh guard, actor-world translation and 24-sample ~10 Hz series observations on LEGION**, including an opt-in series with 48 Windows W/A/D high-bit polls per key, and has since completed **two real bounded physical A/D turn pulses with visual scene rotation, native orientation changes, OS DOWN/UP acceptance and supervised release ledgers**. Actor body-heading calibration, camera-only negative control, passive XYZ refresh, physical W translation and crash-recovery acceptance remain unverified. [Control gate](M1_CONTROL_BOUNDARY.md) · [First live candidate evidence](M1_LIVE_NATIVE_LEGION_2026-11-23.md) · [Win32 backend](M1_WIN32_INPUT.md) · [Release supervisor prototype](M1_RELEASE_SUPERVISOR.md) · [Live cache-refresh guards](M1_LIVE_XYZ_REFRESH_GUARDS_LEGION_2026-11-23.md) · [Two-sample changed-state study](M1_ACTOR_TRANSLATION_CHANGED_STATE_LEGION_2026-11-23.md) · [Historical motion timing + addon source audit](M1_MOTION_TIMING_AND_TELEMETRY_AUDIT_2026-11-23.md) · [Pinned live native series](M1_LIVE_NATIVE_SERIES_LEGION_2026-11-23.md) · [Read-only W/A/D poll handoff](M1_READONLY_MANUAL_KEY_OBSERVATION_LEGION_2026-11-23.md) · [Physical A/D turn calibration](M1_PHYSICAL_AD_TURN_CALIBRATION_2026-11-23.md).

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

## Sister-repository regression evidence

- **RR2**: replay the build-1179 physical Watch pillar forward/return routes (0.127 / 0.220 horizontal error), but explicitly count their corner settlements and any forward-input releases. The first 72-pose/14-input original return segment now has an **offline timing profile** (15 W-held stable samples, 6.63 source-units/s median, zero W+A/D overlap); it is **not** a verified current Taxi speed or angular-response model. Do not call precise arrival continuous steering.
- **RiftWorld Watch**: reproduce the scoped mapped face-90 obstruction/Detour clearance and confirm that map evidence does not silently describe unmodeled collision as absent.
- **November 23 Guardian bridge**: a staged 15-point Watch-to-Tavril route, **not** one uninterrupted accepted run. Its banner pole was absent from the assembled map. A Taxi controller must not classify it as safely clear without coverage evidence or claim full-run acceptance from the composite.
- **Telara Fly provenance**: test a deliberate Unity OBJ **Z-negation** mix-up against a RiftWorld original-source XYZ bundle. The import should reject mismatched coordinate/landmark evidence, not flip it silently.
- **Standalone**: verify the final packaged runtime has zero imports/file reads/process launches from RR2, RiftWorld, Telara Fly or Workbridge, and never attempts a cloud AI call during a journey.

**Source details and original hashes:** [RR2](RR2_HANDOFF.md), [RiftWorld](RIFTWORLD_HANDOFF.md), [Telara Fly](TELARA_FLY_REFERENCE.md), [import contracts](INTEGRATION_CONTRACTS.md).

## Immediate reproducible baseline

Before adding a full UI, establish a deterministic 3-bend course with optional guides and one separate hard-stop variant. Demonstrate that a stop-turn-run controller fails the smoothness gate despite good final accuracy; new steering must clear both the smoothness gate and the same final-arrival gate.
