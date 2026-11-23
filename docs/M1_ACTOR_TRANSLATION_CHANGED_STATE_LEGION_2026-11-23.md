# M1 actor-world translation and same-epoch native change — LEGION

**Date:** Monday, November 23, 2026 (Eastern)  
**Status:** First Taxi-owned **read-only physical actor-world translation candidate**, plus deterministic offline comparison of two original same-process captures. **No game input and no motion acceptance.**

## What changed in this cycle

Taxi now optionally reads the **same-player actor component** through the existing source-pinned dynamic selector instead of duplicating RR2's running reader. It compares a cached secondary XYZ vector, two actor transform offsets and an actor-owned stored translation. When the normal renderer branch is available it may read a bounded renderer translation; otherwise the alternate reference path is **not followed**.

This is valuable structural/transform evidence, not a new independently fresh player position. The actor stored translation can be **derived from the same secondary cache**. It cannot be used as a `LivePose` until independent movement and actor/zone semantics are established.

Taxi's `compare-native-candidates` CLI also validates and source-hashes two complete one-shot capture files, checks Windows process/build/HWND/player-owner continuity and compares XYZ, player-system yaw, optional raw matrix and refresh-guard evidence **offline**. The comparison always leaves game input, passive freshness, body heading and movement verification false.

## Original live evidence

| Field | Verified physical RIFT client on LEGION |
|---|---|
| Executable | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |
| SHA-256 on disk | `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01` |
| PID / process creation UTC ticks | `31684` / `639310312490361378` |
| HWND | `22022232` |
| Current player-owner key | `239816685251645959` |
| Native primary XYZ candidate | `(7207.4033203125, 871.7473754882812, 3021.016357421875)` |
| Native secondary XYZ candidate | `(7207.4033203125, 871.7473754882812, 3021.016357421875)` |
| Actor stored translation `+0x3BC` | `(7207.4033203125, 871.6873779296875, 3021.016357421875)` |
| Actor offset `+0x4F8` | `(0, 0, 0)` |
| Actor offset `+0x770` | `(0, -0.05999999865889549, 0)` |
| Reconstructed actor translation | `(7207.4033203125, 871.6873754896224, 3021.016357421875)` |
| Maximum reconstruction residual | **0.0000024401** source coordinate units |
| Actor flags `+0x1C0` | `68184257` (low bit set) |
| Render branch | **Alternate reference branch** — not followed |
| Actor/secondary-position orientation | **9/9 raw float32 bits matched** |
| Actor matrix planar candidate | **−4.0425441664°** |
| Player-system yaw candidate | **+4.0425439367°** |
| Position cache refresh guard handle/flag | **0 / 0** |
| Native capture bracket | 0.60961 seconds; foreground/process pins passed |

All additional actor and optional renderer reads use bounded `ReadProcessMemory` and are rechecked after acquisition against the same owner and process. The alternate render-reference branch had no qualified pointer path, so no renderer-world position was invented.

The game was temporarily restored for observation and returned to the prior **minimized** window state afterward. The previous foreground window was restored. **No W/A/D, game memory writes, addon deployment, game restart or native getter execution** occurred.

## Two genuine changed native snapshots — same Windows process and player

Compare an earlier one-shot physical report (~07:47 Eastern) with the actor-translation one-shot (~08:11 Eastern), 1,464.704 seconds apart:

| Native candidate measurement | Earlier | Later | Delta |
|---|---:|---:|---:|
| X | 7208.7431641 | 7207.4033203 | −1.33984375 |
| Y | 871.6995850 | 871.7473755 | +0.04779053 |
| Z | 3020.6420898 | 3021.0163574 | +0.37426758 |
| Player-system scalar yaw | −23.1655445° | +4.0425439° | +27.2080884° |
| Actor/position secondary planar matrix | +23.1661547° | −4.0425442° | −27.2086988° |
| Position cache refresh handle `+0x100` | 0 | 0 | unchanged |
| Position cache refresh flag `+0x108` | 0 | 0 | unchanged |

**XZ displacement candidate = 1.3911353** source units; full XYZ displacement candidate = **1.3919560** source units.

The matrix angle and player-system scalar yaw are nearly equal and opposite at both endpoints. Residuals of their **sum** are +0.00061016° (before) and approximately −0.00000023° (after). This indicates a plausible sign-conversion relationship **across two different orientations**. It still does **not** prove avatar-body heading, compass convention or camera-only invariance.

Two captured cache guard pairs remain zero despite changed XYZ. This means the two *known conditional top-level* cache-refresh branches were not eligible under **either sampled state**. It does **not** establish which other engine writer, addon getter, user action, zone transition or background update caused the value change in the ~24-minute gap.

**The elapsed gap is not a synchronized action timeline.** There are no independently verified game input receipts, API call order, character name/zone pairing or video at the transition. Do not infer physical travel speed, continuous freshness, game-control responsiveness or path traversability.

## Preserved original source hashes (all locally ignored)

| Original evidence under `C:\work\Rift_Taxi` | SHA-256 |
|---|---|
| `artifacts/native-refresh-guard-20261123-0747-p31684.json` | `d857055b68d99b9230c9c064513af95e01c289ac583d9ffb1cd4c70d8c57191c` |
| `artifacts/native-actor-world-20261123-0811-p31684.json` | `433c7aae14b9dba6a1f60ef8cc3262f31c1df36a01aa719d90b8e7e88c52b3fb` |
| `artifacts/native-pair-20261123-0818-p31684.json` | `fc15464eebe074955ac6dc822eed406f3c04d9a4d5190b53d3f39317ce022c79` |

The first pair is the **original raw one-shot JSON files**, not reconstruction from the table above. The pair report was generated from these exact files by the new offline CLI. All three raw files stay out of Git.

## Exact RR2 source basis, inspected read-only

- `C:\work\riftreader2\src\RiftReader2.Live\CurrentBuildActorPoseCandidateReader.cs`, observed source SHA-256 `57fe4b4cf4f50fa2f82a4868a0d1e58460d450f646a14181558da0b72417f073`.
- `C:\work\riftreader2\docs\reference\native-current-coordinate-code-map.md`, source-backed `0x687320` source relationship and `0x688F20` conditional normal renderer translation. The actor +0x3BC world translation is composed from **secondary XYZ + offset +0x4F8 + offset +0x770**; the render object's normal branch carries translation at `+0xC4`. Do not read alternate bit0 branch without separate verification.
- `C:\work\riftreader2\docs\reference\current-native-xyz-writer-evidence.md` documents why neither `Inspect.Unit.Detail` nor the zero/zero top-level refresh guards prove passive cache freshness.

The current Taxi code has no RR2 runtime import or external service dependency. No RR2/RiftWorld/Telara Fly project files or services were modified.

## How to reproduce (read-only and offline)

The one-shot CLI requires the same explicit PID/start ticks, executable hash/path, HWND and host described in [M1 native capture](M1_NATIVE_READONLY.md#explicit-pinned-candidate-capture-cli-m1-diagnostic-only). Add `--include-actor-translation-candidate`, optionally alongside `--include-matrix-candidate` and `--include-refresh-guard-candidate`. Choose a **new** output filename. The game must be foreground during actual read-only capture.

To compare *existing saved files without running RIFT*, open PowerShell in `C:\work\Rift_Taxi`:

```powershell
python -B -m rift_taxi compare-native-candidates `
  --before .\artifacts\native-refresh-guard-20261123-0747-p31684.json `
  --after .\artifacts\native-actor-world-20261123-0811-p31684.json `
  --out .\artifacts\native-pair-another-unique-name.json

python -B -m unittest discover -s tests -v
```

The comparator requires two **distinct complete** `taxi.native-candidate/1` reports with advancing monotonic timestamps, exact source identity and owner match. It uses original file SHA-256s, validates optional raw matrix and refresh guard statuses, checks actor translation reconstruction and rejects altered/falsely qualified evidence. New test coverage includes mismatched actors, process epochs, windows, invalid float32 evidence, forged qualification flags, bad actor reconstruction and non-overwriting CLI output.

**Regression state:** **221/221 tests** passed on LEGION after this M1 change. Physical position-body-yaw qualification remains **pending**.

## Critical next experiment

Collect actual independently observed character displacement or deliberate A/D turn with ordered **native-before / action / native-after** records and a same-actor/zone source (such as in-game telemetry or observed screen). Account for addon `Inspect.Unit.Detail` polling as a potential cache writer, and capture camera-only negative control. Only that can begin qualifying an authoritative live `LivePose`. Until then keep actual W/A/D control disarmed.
