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
