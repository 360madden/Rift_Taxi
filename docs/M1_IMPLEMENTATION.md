# M1 offline implementation and handoff — 2026-11-23

> **Historical M1 baseline (63 tests).** This document preserves the original offline implementation state. Later Taxi-owned live read-only native evidence, the separate supervised-input prototype, and the source-aware RR2 motion timing analyzer are documented in the [current roadmap](ROADMAP.md) and [movement-timing/Telemetry audit](M1_MOTION_TIMING_AND_TELEMETRY_AUDIT_2026-11-23.md). The current regression total is **233**, not 63. The historical statements below should not be interpreted as current capability claims.

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
