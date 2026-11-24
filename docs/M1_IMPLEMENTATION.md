# M1 offline implementation and handoff — 2026-11-23

> **Historical M1 baseline (63 tests).** This document preserves the original offline implementation state. Later Taxi-owned live read-only native evidence, the separate supervised-input prototype, and the source-aware RR2 motion timing analyzer are documented in the [current roadmap](ROADMAP.md) and [movement-timing/Telemetry audit](M1_MOTION_TIMING_AND_TELEMETRY_AUDIT_2026-11-23.md). The regression total has advanced; see [current validation](VALIDATION.md), not the historical count below. The historical statements below should not be interpreted as current capability claims.

**Host:** LEGION. **Repository:** C:\work\Rift_Taxi. **Status:** M1 **in progress**, not complete. The offline Python CLI, original RR2 importer, synthetic geometric steering preview and driver-neutral W/A/D + watchdog STOP gate are implemented. There is **no Taxi native pose reader, no Windows game actuator and no tested Taxi live movement**.

## Implemented

| Area | Files | State |
|---|---|---|
| Versioned motion trace | `rift_taxi/contracts.py` | Real strict validation of `taxi.motion-trace/1`, XYZ/Y-up, pass/stop/final, timestamps, raw source hash and normalized-original agreement |
| Offline analysis/compare | `rift_taxi/replay.py` | `taxi.replay-metrics/1`, `taxi.replay-comparison/1`; forward duty, forward releases, estimated guide releases, W+turn overlap, final XZ |
| RR2 original import | `rift_taxi/import_rr2.py` | Copies original native-continuous-move JSONL into an independent local evidence bundle; retains process/build/player and original bytes |
| Synthetic steering preview | `rift_taxi/steering.py` | Geometric Pure Pursuit lookahead and along-route progress, positive/negative yaw *intents* only, no RIFT key mapping or corridor clearance |
| Driver-neutral held-input and STOP | `rift_taxi/control.py` | Exact-session/actor gate, freshness, W+A/D transition ordering, latched STOP, watchdog lease and fault-ledger; **no OS or RIFT input**. See [control boundary](M1_CONTROL_BOUNDARY.md). |
| CLI | `rift_taxi/cli.py` | `doctor`, `replay`, `compare`, `import-rr2`, `preview-steering`; standard library at runtime, no sibling imports/network/game input |
| Regression suite | `tests/test_*.py` | **63/63** offline tests passing on Python 3.14 / LEGION; **29** new input-gate fault/continuity tests |

## Run commands — PowerShell 7

Run from C:\work\Rift_Taxi:

- `python -B -m rift_taxi doctor` — check offline capability.
- `python -B -m rift_taxi replay samples\synthetic_stop_go.json`
- `python -B -m rift_taxi compare samples\synthetic_stop_go.json samples\synthetic_continuous.json`
- `python -B -m rift_taxi preview-steering samples\synthetic_continuous.json --lookahead 2`
- `python -B -m unittest discover -s tests -v`

Optional **offline** original-RR2 import; use a new output directory, never overwrite a prior capture:

```powershell
Set-Location C:\work\Rift_Taxi
python -B -m rift_taxi import-rr2 "C:\work\riftreader2\artifacts\waypoint-input-ae9c97f21e7d41f89c053249f03a2c4f.jsonl" --source-commit a192b839dc7c08689008051110484e07a63c1f8e --out-dir artifacts\rr2-watch-return-NEW
python -B -m rift_taxi replay artifacts\rr2-watch-return-NEW\trace.json
```

The source commit is a reference to the observed code snapshot, **not proof that commit generated the capture**. The created directory includes `trace.json`, `manifest.json` and `sources/original.jsonl`. Every subsequent replay checks original source SHA and recomputes the normalized events/poses. Captured input/pose artifacts stay under Git-ignored `artifacts/`, not in the repository commit.

## Synthetic fixtures (not measured RIFT)

The same hand-authored three-bend route yields a stop/go example with **76.9%** W duty, three guide releases, no steering overlap; and an illustrative continuous example with **100%** W duty, zero guide releases and three in-motion turn intervals. Both have **0** final error by construction. The synthetic preview shows geometric steering intents, **not closed-loop game physics or real A/D keypresses**.

## Later replay metric correction — November 23, 3:05 PM ET

The original replay mixed scopes: W duty was clipped to the movement window, but turning overlap, direction alternations and early W releases could include events outside that window. The existing replay now measures those input-quality metrics consistently over the declared eligible window. A W-up exactly at either boundary is not an intermediate release; a turn already held at window start contributes only its overlapping duration. Hard-stop proximity proxies, trajectory metrics and trace-end release retain the full observed timeline. New report fields label both scopes explicitly. An ordered linear interval sweep replaces the pairwise overlap calculation; 100 seeded interval-set comparisons matched the independent pairwise oracle. Four new tests passed, **24/24 focused replay tests and 376/376 full regressions**. The two original synthetic fixtures retained their benchmark expectations; no new physical arrival or movement qualification is claimed.

## Closed-loop synthetic feedback experiment — November 23, 3:10 PM ET

`python -B -m rift_taxi simulate-route samples/synthetic_continuous.json --out artifacts/new-synthetic-feedback.json` runs an ideal planar feedback model, reusing the existing arc-length and lookahead geometry. Only the route and initial synthetic pose are used; all later positions are generated from the preceding simulated state. Synthetic heading feedback is rate limited, forward velocity slows near the destination, and projected progress is monotonic with a per-step movement-derived advance budget. Unsupported constraints, historical routes and nonflat geometry are refused. Cross-track and time limits produce terminal failure reports rather than false arrival. Parameters are assumptions, not measured RIFT physics.

Default 50 ms step, 3 synthetic units/s speed, 1.5-unit lookahead and 180 degrees/s yaw cap: 105 frames, 5.20 s, 100% forward duty, 3.50 s turning while moving, three turn-sign runs, 0.4473 maximum cross-track error, 0.2842 final XZ error (0.30 tolerance). The locally ignored report `artifacts/m2-m3-synthetic-feedback-20261123-1510.json` has SHA-256 `2cb960fefcc00b6168ebcca51f6bb3dbdd7cb364990ba78fc081b960e768b5c2`. Nine focused tests and **385/385 full regressions** passed. This is ideal kinematic feedback, not a calibrated physical game, obstacle clearance, position freshness, A/D mapping, or a completed M2/M3 milestone.

## Fixed synthetic sensitivity baseline — November 23, 3:14 PM ET

Run `python -B -m rift_taxi stress-route samples/synthetic_continuous.json --out artifacts/new-stress-report.json`. The benchmark reuses `simulate_route` unchanged and exhaustively combines lateral offsets −0.5/0/+0.5 units, initial yaw offsets −90/−45/0/+45/+90 degrees, speeds 2/3 units/s, yaw caps 60/120/180 degrees/s and timesteps 0.05/0.10 s (180 cases). All input overrides and per-case terminal status/metrics are retained. Fixed lookahead 1.5, time limit 30 s, cross-track limit 2 units and fixture arrival tolerance 0.30. Baseline: 165 arrivals, 131 arrivals with ≥95% forward duty, and 15 cross-track-limit failures. At the 60°/s cap, 45/60 arrive and 11/60 meet both metrics; at 120°/s and 180°/s, all 60 cases per cap meet both. The unchanged model has a measured synthetic low-turn-rate weakness; do not interpret the percentages as live success probabilities. Local ignored report `artifacts/m2-m3-synthetic-stress-20261123.json`, SHA-256 `54f951279066da5a17bf6c93c2dc0e13417bb15e3d5e711d49182fa35ce072d1`. Five new regressions, **390/390 full tests passed**. Next compare speed adaptation under limited turn rate on this same grid before considering actuator lag/disturbance modeling. No game input or physical M2/M3 qualification.

## Paired synthetic speed-policy comparison — November 23, 3:20 PM ET

`python -B -m rift_taxi compare-speed-policies samples/synthetic_continuous.json --out artifacts/new-speed-comparison.json` runs both controllers on the unchanged 180-case development grid. `simulate-route` and `stress-route` accept `--speed-policy turn-limited`; the default `fixed` preserves the original movement behavior. The idealized candidate limits positive forward velocity using a lookahead curvature estimate `2*abs(sin(heading error))/chord` and 80% of the synthetic maximum yaw rate in radians/s. Existing heading gate, yaw cap, terminal approach and cross-track/time bounds remain in force. The policy represents continuous synthetic velocity, not a demonstrated RIFT movement control.

| Metric | Fixed | Turn-limited |
|---|---:|---:|
| Arrivals | 165/180 | 180/180 |
| Arrival + at least 95% forward duty | 131/180 | 180/180 |
| Cross-track-limit failures | 15 | 0 |
| Worst cross-track error (synthetic units) | 2.0420 | 0.9357 |
| Mean time across 165 common successful cases (s) | 9.4700 | 7.1755 |
| Mean moving speed across common successful cases (synthetic units/s) | 2.2342 | 2.0887 |

All 15 failed arrivals and 49 combined-target misses are rescued with zero lost successes. At 60 degrees/s, the candidate meets both targets in 60/60 cases versus 11/60 fixed. The two faster yaw caps retain 60/60 combined successes each. Full paired report in ignored `artifacts/m2-m3-synthetic-speed-comparison-20261123.json`, SHA-256 `34039d0dcae55bfee5faba50431d1ebe449bfb3201639932bf1717aa6856d46f`. Six new regressions; **396/396 full tests passed**. The tuning grid is not independent evidence, and the idealized policy has not been tested under actuator lag, collision, physical speed constraints or live movement. Next use independently defined synthetic holdouts before promoting any simulation default. No M1/M2/M3 physical completion claimed.

## Untuned route-shape holdout v1 — November 23, 4:08 PM ET

Run `python -B -m rift_taxi evaluate-holdout --out artifacts/new-holdout.json`. Six authored flat synthetic route shapes and out-of-grid starting conditions/model profiles yield 162 matched scenarios. Both policies retain their original behavior; all scenario definitions, hashes, terminal statuses and metrics are preserved. Fixed: 112 arrivals, 80 combined arrival/duty successes. Turn-limited: 135 arrivals, 101 combined successes, 38 rescued arrivals and 15 lost baseline arrivals. The candidate fails all 27 short-zigzag cases with coincident lookahead; the other five shapes reach 135/135. Mean matched-arrival time over 97 cases: 8.1207 versus 8.2423 simulated seconds. The candidate remains opt-in. Original local report SHA-256 `1ec0b5f5bf2b2f097ddb1be4f18bf0a152981c8634fa777dd3a9420b10f75195` (`artifacts/m2-m3-synthetic-holdout-v1-20261123.json`). Five new tests; **401/401 full regressions passed**. No physical RIFT capability is inferred.

The user also directed that scripts and code be heavily commented for future AI maintenance. This is a durable repository requirement in AGENTS.md and AUTONOMY_POLICY.md; the current simulator and benchmark modules received explanatory comments without changing policy behavior.

## Synthetic local-projection rejoin experiment — November 23, 4:14 PM ET

The original short-zigzag failure was reproduced on scenario 95: route progress 3.9231 of 12.7213 units, local projection deviation 1.1279 units, and the lookahead point essentially coincident with the vehicle. The curvature-based speed cap collapsed velocity below 1e-8 units/s while progress stayed unchanged. The third opt-in policy `turn-limited-rejoin` temporarily targets the already-admissible local arc projection when the lookahead chord is <=20% of lookahead and projection deviation >35% of lookahead; it exits that mode at <=15% deviation. Hysteresis avoids switching targets on every step. The existing time/deviation bounds, heading gate, displacement-derived arc-progress cap and arrival test remain unchanged. This is an idealized geometric recovery, not physical collision clearance or real game movement.

Run `python -B -m rift_taxi evaluate-holdout --include-rejoin --out artifacts/new-rejoin-comparison.json` for the three-policy comparison. The two-policy default still reproduces the original report byte-for-byte, SHA-256 `1ec0b5f5bf2b2f097ddb1be4f18bf0a152981c8634fa777dd3a9420b10f75195`. Rejoin report: `artifacts/m2-m3-synthetic-rejoin-comparison-20261123.json`, SHA-256 `f6ecf0fece221f33c571cbd129b905f9ec24b25646466e599b9a01fd1997fb74`. It reaches all 162 destinations, rescues all 27 zigzag cases, loses no previous arrivals, retains 101/162 combined successes, and leaves mean time over the 135 common arrivals unchanged (8.5583 s). The prior 180-case development grid retains 180/180 combined successes; report `artifacts/m2-m3-synthetic-rejoin-dev-grid-20261123.json`, SHA-256 `c55d085bbe5985a34843322f774f2002fde5186bf973e33b41525fadd9525c60`. Three new tests; **404/404 regressions passed**. Do not treat the repaired v1 holdout as independent validation of the third policy. Future work should examine recovery efficiency and new synthetic conditions. No live qualification or default change.

## Synthetic recovery phase audit (2026-11-23)

Recovery phase audit: 162 synthetic cases, mean stationary 0.631944 s, positive velocity duty 0.941658, no near-zero moving steps below 0.05 synthetic units/s. Zigzag mean stationary 2.31 s (startup 0.294259, lookahead 0.760741, rejoin 1.255); other five shapes have no post-start stops. These are model diagnostics, not physical game measurements. The proactive corner-lookahead experiment was rejected (140/162 arrivals, versus 162/162 baseline); original controller restored byte-for-byte.

`python -m rift_taxi audit-recovery --out NEW` reruns the unchanged rejoin model on the existing 162-case synthetic set, checks each result against the holdout evaluator, and partitions each interval by startup, lookahead or local-projection-rejoin phase. Stationary time means exactly zero modeled speed; near-zero positive speed is a separate diagnostic. No historical duty denominator changes. The final zero-duration frame is excluded. The audit rejects inconsistent timing and metrics. Three new regression tests cover the phase partition, validation and all cases. Report `artifacts/m2-m3-synthetic-recovery-phase-audit-20261123.json`, SHA-256 `a567c66d34b1569417f9ac341125a8c13c069b156ab5f09d3dda2013a512c66b` (local ignored artifact).

## Fresh synthetic route-shape validation v2 (2026-11-23)

Frozen v2 validation: 108 scenarios per policy (324 simulations), six new synthetic shapes. Fixed speed 93 arrivals / 41 combined successes; turn-limited 60 / 40; rejoin 72 / 40. Rejoin rescues 12 compact-switchback cases and loses no turn-limited successes, but all 18 crossing-bow cases time out and all 18 acute-return cases terminate with degenerate lookahead. Fixed speed remains stronger overall on this set; no default promotion. All generated trajectories passed internal progress/time/endpoint consistency checks; not physical ground truth.

Run `python -B -m rift_taxi evaluate-holdout-v2 --out artifacts/new-holdout-v2.json`. The new module reuses the trace builder and phase audit, leaves the controller unchanged, and independently recomputes terminal endpoint distance and route length from frames/source geometry. Six authored shapes, two lateral offsets, three heading offsets, three coupled speed/yaw/timestep profiles. The exact closed-loop-start regression confirms that endpoint proximity alone does not cause premature arrival. The v1 report regenerated byte-for-byte with SHA-256 `1ec0b5f5bf2b2f097ddb1be4f18bf0a152981c8634fa777dd3a9420b10f75195`. New local ignored report `artifacts/m2-m3-synthetic-holdout-v2-20261123.json`, SHA-256 `546c3d92de3ab55cbbaac75ebe850a2498006122982ae090b2f3b13516008921`. Three new tests, **410/410 full regressions passed**. Keep v2 definitions fixed; any later tuning against v2 requires another fresh evaluation set. Next diagnose progress/target collapse at acute returns and timeout at crossings before adding model latency.

## Ordered sharp-corner synthetic experiment (2026-11-23)

Experimental ordered sharp-corner policy: v1 162/162 arrivals and 112/162 combined successes (previous 101); v2 108/108 arrivals (previous 72), combined successes unchanged at 40. All 36 crossing/acute-return failures rescued, no lost arrivals or combined successes. Original 180-case development grid unchanged at 180 combined successes. Independent internal frame/geometry checks verify ordered passage witnesses; both scenario sets informed tuning, not fresh validation.

`python -B -m rift_taxi compare-ordered-corners --out artifacts/new-ordered-comparison.json` compares the opt-in `turn-limited-ordered` variant against rejoin on unchanged v1/v2 scenarios. Corners at heading change >=100 degrees are approached sequentially within min(0.10*lookahead, 0.5*arrival tolerance) in both position and arc distance. Pending corner bounds the projection interval and target; completion never directly assigns progress, and the displacement-derived advance cap remains. Each passage records model timestamp, position, route arc and progress. The comparison recomputes geometry and matches witnesses to frames. V1 mean common arrival time 9.2034 -> 8.5644 s; v2 common 72 arrivals unchanged at 9.5558 s. All 413 regression tests pass. Original v2 report SHA-256 unchanged `546c3d92de3ab55cbbaac75ebe850a2498006122982ae090b2f3b13516008921`. New local report `artifacts/m2-m3-synthetic-ordered-comparison-20261123.json` SHA-256 `b90e2320f7fde58fec40b06bd0e0768d81bcc0efa28a638febf1367f4730b4fb`. New policy remains synthetic and opt-in; no physical clearance or actual movement established. Next fresh evaluation and explicit model delay sensitivity.

## Synthetic transport-delay sensitivity (2026-11-23)

Synthetic whole-step command FIFO delay study: 432 cases (108 scenarios x 0/1/2/4 delayed steps). Geometric arrivals 108/106/96/72; arrival plus >=95% modeled forward duty 40/35/24/17. Every successful nonzero-delay observation ended with queued nonzero motion (106/96/72), so no settled arrival is established. Delay is idealized, not a measured game actuator response. Zero-delay reports remain unchanged.

Run `python -B -m rift_taxi study-synthetic-delay --out artifacts/new-delay-study.json`. The simulator optionally queues requested velocity and yaw rate for 0–10 whole integration steps. Nonzero-delay frames distinguish requested from applied motion; only applied motion contributes to trajectory, progress and duty. Initial queue is stationary. At the original geometric arrival criterion the observation stops; queued commands are retained and settling is explicitly unverified. The frozen v2 scenarios use nominal delays of 60–120 ms, 120–240 ms and 240–480 ms for 1, 2 and 4 steps respectively. A final partial step may be shorter. Four tests cover FIFO order, invalid delay, zero-delay compatibility and all study outcomes. **417/417 full tests passed**. Original v2 report SHA-256 remains `546c3d92de3ab55cbbaac75ebe850a2498006122982ae090b2f3b13516008921`. New ignored report `artifacts/m2-m3-synthetic-delay-study-20261123.json`, SHA-256 `732d117ba9a70ad10b0153917e5f9056eb8d992993f874de2ba041d0258b548e`. Next: separately model bounded terminal command drain and verify settled position without changing the historical arrival metric. No live input or physical calibration.

## Synthetic terminal settling study (2026-11-23)

Synthetic terminal FIFO drain: 432 cases (108 scenarios x 0/1/2/4 delayed steps); first geometric arrivals 108/106/96/72, final model positions within tolerance 108/106/91/67. Ten delayed arrivals finish outside the 0.30-unit tolerance; worst settled error at four steps is 0.468429. Mean post-arrival motion for delayed geometric arrivals is 0.065454/0.144018/0.236179 synthetic units. This is idealized queue drain plus one stationary model interval, not physical stopping or collision evidence. Original controller and delay report unchanged.

Run `python -B -m rift_taxi study-synthetic-settling --out artifacts/new-settling-study.json`. A separate offline audit reproduces the first-arrival trajectory, verifies each retained queue against the final requested command history, and applies remaining commands in FIFO order using nominal dt and the same ideal midpoint integration. One extra zero-command interval witnesses stationary model behavior. This is an extension of the observation after arrival, not part of the original 40-second approach budget; failed approaches are not promoted. Error extrema are sampled at step boundaries only. Four tests cover original-report immutability, queue order and forgery rejection, failed approaches, and frozen study outcomes. **421/421 tests passed**. Original delay report SHA-256 remains `732d117ba9a70ad10b0153917e5f9056eb8d992993f874de2ba041d0258b548e`. New ignored report `artifacts/m2-m3-synthetic-settling-study-20261123.json`, SHA-256 `973c725aaa8b2f1c94619a383c5e02acade6805bbfcf0a9f91f8634795a1ff43`. Next: investigate a separate model-only stopping analysis using the observed terminal error distribution, without retuning the historical benchmark. No live input or physical qualification.

## Synthetic signed terminal-error analysis (2026-11-23)

Synthetic terminal-error audit: all 432 frozen delay cases retained. Ten final tolerance failures separate into five two-step failures before the endpoint plane (four longitudinal-dominant, one lateral-dominant) and five four-step failures beyond it (all lateral-dominant). No sampled transient exit then return. Mean absolute final longitudinal/lateral error across geometric arrivals at 0/1/2/4 delay steps is 0.273217/0.013706, 0.194025/0.020124, 0.149091/0.053017, 0.052445/0.084670 synthetic units respectively. These are local final-leg components, not physical stopping or movement evidence. Controller unchanged.

Run `python -B -m rift_taxi study-terminal-errors --out artifacts/new-terminal-errors.json`. The diagnostic reuses the original settling audit and frozen v2 scenario builder. It resolves the error vector onto the final authored XZ leg tangent and left normal, checks scenario identity, independently recomputes sampled radial error, and retains failed approaches separately. No controller modifications or stopping-policy tuning. Three new tests cover signed/rotation-invariant geometry, degenerate legs, and the frozen failure distribution. **424/424 full tests passed**. Original settling report SHA-256 reproduced byte-for-byte `973c725aaa8b2f1c94619a383c5e02acade6805bbfcf0a9f91f8634795a1ff43`. Separate ignored report `artifacts/m2-m3-synthetic-terminal-errors-20261123.json`, SHA-256 `65670fd42574987987baea59380f7633e7f1f795f0f55274c8b27b7ef142d9fa`. The results indicate that the term overshoot alone is insufficient; no physical inference or production promotion.

## Synthetic trajectory integrity validation (2026-11-23)

Independent synthetic trajectory consistency audit now checks source identity/classification, finite bounded numeric fields, elapsed timestamps and integration durations, midpoint position/yaw integration, displacement-derived progress bounds, requested/applied FIFO history and pending queue, recalculated motion totals/duty/turn counts, and terminal status/geometry. Seven corruption regressions; no controller change. This is internal model consistency, not authentication, collision clearance, or physical ground truth.

The reusable `simulation_integrity.verify_synthetic_trajectory` is called by the existing v2 validator, including downstream ordered-corner, delay, settling and terminal-error studies. It independently integrates the recorded applied steps, validates the source identity and model bounds, and recalculates report totals; the simulator and original reports are unmodified. Seven focused tests exercise valid reports, corrupt source/flags, intermediate pose and time corruption, invalid numbers, false summaries, FIFO inconsistencies and honest timeout versus terminal frame corruption. **431/431 full tests passed**. The prior 432-case settling report regenerated byte-for-byte with SHA-256 `973c725aaa8b2f1c94619a383c5e02acade6805bbfcf0a9f91f8634795a1ff43`. Next: evaluate unchanged policies on a genuinely fresh authored synthetic validation set. No live qualification.

## Historical LEGION RR2 source actually imported

Original source: `C:\work\riftreader2\artifacts\waypoint-input-ae9c97f21e7d41f89c053249f03a2c4f.jsonl`.
SHA-256: `3d11d21c39520df31f674ad9e3e407239c40e4b5a5b2ac674d74230194622278` (also recorded by RiftWorld November 22 pillar verification).

- **72** source XYZ poses, **14** key-send events; UTC timestamps from the same host.
- **16.3%** forward-key insertion duty over that **single short control window**, including initial turns and pauses. This **does not** describe all RR2 movement.
- **2** intermediate W releases, **0** key-send intervals with W+A/D overlap.
- Recorded final horizontal error **0.220358** source units. Source reported arrived; **Taxi did not execute a journey**.
- Native `bearing` remains candidate-only; Taxi intentionally imports actor yaw as **unavailable**. No steering from this real historical trace is permitted.
- UTC is not a guaranteed monotonic timing source. OS input insertion does not prove game consumption.

Independently replayable local result: `artifacts/rr2-watch-return-original-20261122/` (ignored by Git). It has `trace.json`, `metrics.json`, `manifest.json` and SHA-verified original JSONL.

## Failures caught and corrected

An initially truncated tool file-read led to a truncated `contracts.py` during an update and a test-detected `IndentationError`. The missing tail was restored, and tests passed. Before future whole-file edits, ensure the read response says `truncated=false` and includes EOF.

The first historical loader checked raw-source SHA but not whether the normalized pose/key events matched it. A tampering regression led to a new **source-to-trace normalization check**: altering the normalized poses while retaining a matching raw SHA now causes rejection.

The new W/A/D control tests initially expected stale command rejection even when the independently running watchdog had already latched `pose-expired`; the tests were corrected to accept the earlier watchdog STOP. Another review hardened immutable pose XYZ, bounded key-set input, and advancing source timestamps; new regressions cover these conditions. [Full driver-neutral scope](M1_CONTROL_BOUNDARY.md).

## What's next

1. **M1 remains open:** implement Taxi-owned current-build native actor XYZ/facing reader, independently qualified yaw source, identity/process-start/freshness and source-time measurements.
2. Connect the now-tested driver-neutral W/A/D and STOP gate to a separately supervised native Windows input backend, cross-process ownership and independent post-release game readback. **No game input was attempted in this milestone.**
3. Complete M1 with a bounded authorized physical test, including real measured yaw/turn response and end-to-end latency.
4. For M2/M3, add real closed-loop motion simulation and Stanley comparison, then test sustained W and gradual turns physically. **M3 requires zero unnecessary guide stops**.

No RR2, RiftWorld or Telara Fly files were modified for this implementation.
