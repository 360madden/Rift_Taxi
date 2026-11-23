# M1 pinned native time series — physical LEGION evidence

**November 23, 2026 · LEGION · Python 3.14.10**  
**Status:** Taxi-owned read-only native candidate time-series sampler implemented, regression-tested, and exercised on the physical RIFT client. **It neither moves the game nor qualifies actor yaw, passive XYZ freshness or navigation.**

## Why this matters

The previous `inspect-native-burst` command acquired 2–8 candidates by **opening the RIFT process and hashing the 60 MB executable on each individual sample**. That was adequate for offline identity and stationary guard studies, but unsuitable for a time-resolved motion experiment.

The standalone `rift_taxi/native_series.py` module provides **3–128 candidate samples from one read-only, pinned process handle** (default 16; CLI `observe-native-series`). It performs a full executable path/SHA-256, process-start and HWND foreground check **before and after** the series and hashes the executable again when opening the single read-only memory session. Each candidate is separately resolved through the exact player-key → entity → position/actor component chain. The native reader itself checks the process epoch before and after every bounded memory read, and a lighter Windows process/window/foreground check runs around each candidate.

A changed owner, unexpected PID/start/path/window, missing foreground, changed executable identity, invalid timestamp, partial native read or expired total-time budget **aborts the whole operation without producing a completed report**. The output is an immutable-intended, new-path-only JSON report with original sample monotonic times, sample gaps, optional source-pinned raw actor/position matrices, refresh-guard inputs and actor stored-world translation candidates.

## Later cadence hardening — 3:01 PM ET

The initial-admission cadence fix did not prevent catch-up after a slow individual decode. The existing sampler now derives the next start from the actual preceding sample start, not an old ideal grid. A read overrun may delay future samples but does not cause a catch-up burst. A short sleep or backward/unrepresentable clock aborts the report. Each row records `captureStartMonotonicSeconds` and `captureEndMonotonicSeconds` alongside the native observation timestamp. The new `observedCaptureStartGapSeconds` summary and `sampleSchedule` distinguish acquisition starts from source observation cadence. Existing observation-gap semantics remain unchanged: variable read durations can still change source-observation gaps.

Five new synthetic regressions passed, including a 350 ms fake decode overrun and rollback at the final admission. The full suite passed **372/372** on LEGION. No physical acquisition was performed during this hardening cycle, and the historical physical receipts below remain unchanged. This does not establish passive native freshness, body yaw, or hard real-time scheduling.

## Live proof from physical RIFT client

Target process, verified for both experiments:

| Property | Exact value |
|---|---|
| Host / image | LEGION · `rift_x64.exe` |
| Executable | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |
| On-disk executable SHA-256 | `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01` |
| PID / start UTC ticks | `31684` / `639310312490361378` |
| Window handle | `22022232` |
| Native self-owner key | `239816685251645959` |
| XYZ candidate | `(7207.4033203125, 871.7473754882812, 3021.016357421875)` |
| Player-system yaw candidate | `+4.042543936694074°` |
| Render/actor/position source confidence | Candidate-only; no independently qualified body heading |

Both observations requested 24 samples at 100 ms spacing, including optional matrix/refresh-guard/actor-translation fields.

| Measure | Initial implementation | After cadence fix |
|---|---:|---:|
| Completed candidate samples | 24/24 | 24/24 |
| Total including initial/final OS/hash admissions | **2.4027 s** | **2.7799 s** |
| Minimum observed source sample gap | **6.06 ms** | **92.58 ms** |
| Median source sample gap | **99.57 ms** | **99.81 ms** |
| Maximum source sample gap | **103.65 ms** | **108.68 ms** |
| Median per-sample **identity checks + decode** bracket | **5.99 ms** | **9.02 ms** |
| Distinct XYZ / yaw candidates | 1 / 1 | 1 / 1 |
| Actor vs position matrix raw-bit agreement | 24/24 | 24/24 |
| Cache refresh guard handle/flag | 0 / 0 in every sample | 0 / 0 in every sample |

**Root-cause correction:** the first implementation started its sample-spacing schedule *before* the expensive initial executable admission. As a result, the first samples bunched together at 6 ms despite the 100 ms requested period. The fix anchors cadence **after** the initial admissions and process-handle open, avoiding this initial catch-up. The code does **not** claim hard real-time cadence or guarantee an upper bound on scheduling jitter. Full elapsed time includes all identity checks.

**Source SHA-256 receipts, locally retained outside Git:**

| Ignored artifact (relative to Taxi repository) | Original SHA-256 |
|---|---|
| `artifacts/native-series-20261123-0851-p31684.json` | `00721d05404af78e54cebcedfe8c1127a2c1240fde4d410c7fbe436c30220c6c` |
| `artifacts/native-series-cadence-fixed-20261123-0854-p31684.json` | `297b6128e9b68669266f8841346e91cde3676272df066e43fae51d65deb9c2a5` |

No synthetic source bytes were substituted for these originals. The SHA values establish the saved bytes' integrity, not semantic proof of character position. The observed RIFT window was initially minimized; it was temporarily restored/foregrounded for **read-only** observation and returned to its original minimized state afterward. Previous foreground window `328472` was restored. **No game movement, mouse/camera, addon changes, native writes, UI reload or restart** occurred.

## Why this still does not resolve M1 freshness

- The player was not independently commanded/observed moving during the two short series. **Unchanged native values do not establish whether they would change immediately during actual movement.**
- The installed Telemetry addon source contains **two potential 0.10-second `Inspect.Unit.Detail` polling paths**. If loaded and active, these may refresh the cache itself; a native/API match is not independent passive-freshness proof. See [the addon source audit](M1_MOTION_TIMING_AND_TELEMETRY_AUDIT_2026-11-23.md).
- Raw position/actor 3×3 matrices agreed on all samples, but body heading and camera independence remain unqualified.
- Process epoch/read-only identity checks do not provide an atomic world snapshot. Their purpose is to prevent silent process/actor substitution, not prove physics or game state.
- A command returning a full 24-row report does **not** establish actual RIFT input consumption, model calibration or destination arrival.

The report explicitly sets `addonApiProducerQuietVerified=false`, `externalActionReceiptsProvided=false`, `physicalMovementVerified=false`, `playerBodyHeadingVerified=false`, `nativeXYZPassiveFreshnessVerified=false` and `gameInputSent=false`.

## Reproduction — PowerShell on the physical host

After independently identifying a current game PID, process creation ticks, executable SHA/path, HWND and host (see [M1 native read-only setup](M1_NATIVE_READONLY.md)), run from `C:\work\Rift_Taxi`:

```powershell
# All pins must describe the PRESENT process; stale session values are refused.
python -B -m rift_taxi observe-native-series `
  --pid $rift.Id --start-ticks $startTicks `
  --exe-path $exe --sha256 $exeHash --hwnd $hwnd --host $computer `
  --samples 24 --interval-ms 100 --max-total-seconds 15 `
  --include-matrix-candidate --include-refresh-guard-candidate `
  --include-actor-translation-candidate --start-delay-seconds 5 `
  --out .\artifacts\native-series-new-unique-name.json

python -B -m unittest discover -s tests -p test_native_series.py -v
python -B -m unittest discover -s tests -v
```

The start delay only gives time to switch back to the game. The command **does not focus, launch, move or steer RIFT**. If a report path already exists, the CLI refuses it **before** reading the process.

## Test and development boundaries

The new sampler was tested with an injected fake Windows process/window API, a single fake read-only memory session, and a fake source-pinned decoder. **16 new focused tests** were added; the complete LEGION suite passed **249/249**. They cover one-handle reuse, full admission twice, per-sample process/window verification, source PID/epoch/build matching, wrong foreground or hidden window, player-owner changes, invalid timestamps, optional evidence, deadline expiry, stale SHA, occupied output paths, and slow-start cadence. A separate physical read-only run confirms successful actual Win32 behavior.

The standalone Taxi runtime remains Python standard-library only. No RR2, RiftWorld or Telara Fly repository or runtime service was modified. Original live raw JSON evidence stays in the ignored `artifacts/` folder.

**Later extension:** `--observe-manual-keys` now provides opt-in, read-only W/A/D snapshots before/after each native read; a third physical series captured 48 polls/key with no downs observed. See [M1 passive keyboard observation](M1_READONLY_MANUAL_KEY_OBSERVATION_LEGION_2026-11-23.md). This does not establish actual game input or replace an independently observed action receipt.

**Next experiment:** With independent game observation and manual action receipts (or otherwise separately qualified input), run a bounded same-session series through **settled → action → settled** phases. Explicitly record any Lua API getter calls that can refresh XYZ; compare camera-only changes against character turns and observed displacement. Do not promote the yaw or position candidate to an authenticated `LivePose` without that proof.
