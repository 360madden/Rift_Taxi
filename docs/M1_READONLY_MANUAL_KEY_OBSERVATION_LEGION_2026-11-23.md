# M1 read-only Windows key-state snapshots alongside native RIFT series

**November 23, 2026 · LEGION · Python 3.14.10**

**State:** Implemented and physically verified as a **read-only observer**. No keyboard event was inserted. This is not a verified movement-action logger, a game-input acknowledgement, a calibrated heading source or an autonomous Taxi controller.

## Purpose

The existing `observe-native-series` command captures 3–128 owner-checked native position/yaw candidates with a single pinned read-only RIFT process handle, but did not show whether W, A or D happened to be held on Windows between pose observations. This addition provides an **explicitly opt-in** `--observe-manual-keys` switch. It polls the high bit of `GetAsyncKeyState` for only W, A and D **before and after each native read** while the exact RIFT window is foreground.

This is a narrow Windows desktop observation. It does **not** record all keystrokes, install a keyboard hook, call `SendInput`, initiate a turn or move, prove who pressed a key, or establish that the RIFT client accepted any input. Fast press/release pulses between polls can be missed. The documented addon `Inspect.Unit.Detail` polling may still affect XYZ cache freshness independently of keyboard observations.

The extra readings are available only if the caller explicitly requests them; the regular series code does not even instantiate the keyboard reader when the flag is absent.

## New data contract

Each `taxi.native-candidate-series/1` sample can contain `manualWindowsKeyStates` with:

- `beforeNativeRead` and `afterNativeRead`: exact W/A/D boolean snapshots and the capturing process's monotonic timestamp.
- `unchangedDuringNativeRead`: whether all three sampled high-bit states agreed at those two polls; this does not imply they were unchanged every instant between polls.
- `gameInputConsumptionVerified=false`.

The optional series-wide `manualWindowsKeyObservation` summarizes down-state poll counts, sample brackets with differing W/A/D states, and **candidate transition time windows** between consecutive sampled states. For each such window it retains lower/upper observed sample clocks, source/target key state, and explicit `transitionInstantVerified=false` / `gameInputConsumptionVerified=false`.

The observer also preserves exact process/build/HWND/foreground identity checks before and after every native sample, full executable SHA checks around the series, and same-player owner continuity. An invalid keyboard state, unexpected data shape, changed process/foreground, or a W/A/D poll taking **more than 50 milliseconds** aborts the whole series without publishing a completed report.

## Source implementation and tests

| Taxi-owned file | Role |
|---|---|
| `rift_taxi/key_observation.py` | Standard-library ctypes `GetAsyncKeyState` wrapper; only three virtual keys (`W=0x57`, `A=0x41`, `D=0x44`); interprets high bit, ignores the shared low press-since-last-query bit |
| `rift_taxi/native_series.py` | Optional before/after keyboard observations and conservative transition-window summary within the already pinned native series |
| `rift_taxi/cli.py` | `--observe-manual-keys`, opt-in only; `doctor` advertises observer separately from actual live-input qualification |
| `tests/test_key_observation.py` | High-bit, low-bit, invalid-result, error and actual read-only Win32 smoke tests |
| `tests/test_native_series.py` | Fake W/A/D transitions, stable/unstable brackets, invalid state/timing, CLI forwarding, absence of polling when disabled and no game-input qualification |

**PowerShell example** (inside `C:\work\Rift_Taxi`, after freshly verifying all process pins):

```powershell
python -B -m rift_taxi observe-native-series `
  --pid $rift.Id --start-ticks $startTicks `
  --exe-path $exe --sha256 $exeHash --hwnd $hwnd --host $computer `
  --samples 24 --interval-ms 100 --max-total-seconds 15 `
  --include-matrix-candidate --include-refresh-guard-candidate `
  --include-actor-translation-candidate --observe-manual-keys `
  --start-delay-seconds 5 `
  --out .\artifacts\native-series-with-keys-new-unique-name.json

python -B -m unittest discover -s tests -p test_key_observation.py -v
python -B -m unittest discover -s tests -p test_native_series.py -v
python -B -m unittest discover -s tests -v
```

When launching from PowerShell, the optional delay allows the game to become foreground; Taxi does not activate the window itself. An occupied output path is refused before reading any target bytes.

## Physical LEGION validation — no keyboard activity induced

The already running RIFT process was verified as PID **31684**, process start **639310312490361378** UTC .NET ticks, HWND **22022232**, executable SHA-256 **DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01**, same player-owner key **239816685251645959**. RIFT's window was temporarily foregrounded for this observation and restored to its original **minimized** state afterward; the prior foreground HWND `394414` was restored.

Original raw report saved locally under ignored `artifacts/`:

| File | SHA-256 |
|---|---|
| `artifacts/native-series-manual-keys-20261123-0950-p31684.json` | `65eff7fbe305c63000349baf1ecf535aad15a8bd09814b1477da71f893955c99` |

That original `taxi.native-candidate-series/1` report contains **24/24** complete owner-checked native samples, each with two W/A/D key-state snapshots (**48 polls per key**). All three keys were observed UP at all 48 individual polls; there were **no sampled key-state transitions** and no changing key states within a native-read bracket.

| Measured field | Observed |
|---|---:|
| Total elapsed including identity checks | **2.73136 s** |
| Minimum / median / maximum native sample gap | **78.9 / 100.6 / 122.9 ms** |
| Native XYZ / yaw distinct values | **1 / 1** |
| Actor vs position matrix raw equality | **24/24** |
| Sampled refresh handle / flag | **0 / 0** |
| Key-down polls for W/A/D | **0 / 0 / 0** |
| Physical W/A/D inserted by Taxi | **0** |

The RIFT client was not manually moved during this short capture. A key-state report with zero observed downs does **not** prove no key presses occurred between polls. Stationary native XYZ values do not prove passive refresh. The report keeps `externalActionReceiptsProvided=false`, `gameInputSent=false`, `nativeXYZPassiveFreshnessVerified=false`, `playerBodyHeadingVerified=false` and `liveJourneyVerified=false`.

## Next discriminating manual experiment

With a person actually at the game client, use a single exact-process series that includes: settled baseline, a manually observed A turn, a manually observed D turn, a camera-only negative control and a short manually observed forward W movement. Retain **the original on-screen/action timeline**, verify the operator actually performed each action, and compare native coordinates and matrix angle behavior while recording which addon API producers were loaded or called.

The new W/A/D key polling helps bracket manual key-state observations, but it **cannot log mouse-driven camera motion**, guarantee observing short taps, or prove the game consumed input. Those independent checks are still required before promoting a position or heading field into `LivePose` and enabling the Win32 movement controller.

**Repository rules:** do not modify RR2, RiftWorld or permanently read-only Telara Fly; do not modify installed addons. This implementation uses Taxi-owned standard-library Python only.

## Follow-up: restarted client correctly rebound (09:49–09:53 Eastern)

A **second physical observation** was collected after RIFT restarted. The previous PID/HWND admission was no longer valid, and the first attempt was refused **before any target memory read**. Taxi then independently requalified the replacement process:

| Process identity | Verified replacement |
|---|---|
| Host / PID | LEGION / **424** |
| Start .NET UTC ticks | `639310421805307472` (09:49:40.5307472 Eastern) |
| New HWND | `1968794` |
| Executable SHA-256 | `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01` |
| Candidate player owner key | `239816685251645959` |
| Session status | New epoch; **must not** be joined with old PID 31684 as a continuous capture |

The new original capture is locally retained and Git-ignored:

`artifacts/native-series-wad-20261123-0953-p424.json`

**Original SHA-256:** `6dda8246b0952de634f29760117395e0d3072389449556157b709036d5accb0c`.

It contains **32/32** complete read-only samples, 64 sampled Windows high-bit observations per key, **zero sampled W/A/D downs or transitions**, no XYZ/yaw/actor translation changes, and 32/32 raw actor-position matrix matches. The cache refresh guard handle and flag stayed at **0/0**. Total elapsed including OS admission was **3.5815 seconds**; minimum/median/maximum native sample spacing was **70.78/98.73/142.54 ms**. No manual action was induced or independently verified, and missed quick keypresses remain possible. The new RIFT window was already foreground and **not minimized**; it remained foreground without altering window state.

**Failure-path significance:** The original target HWND disappeared, and the observer failed closed rather than silently binding to a different process. The successful subsequent capture used fresh PID/epoch/HWND, with a freshly verified unchanged executable build. A matching player-key candidate across two game-process epochs is **not** proof of continuous actor identity, true position freshness, or game consumption.

After adding read-only key observation support, **261/261 LEGION regressions passed**, including real Windows `GetAsyncKeyState` smoke tests and synthetic key-transition windows. The complete implementation still does not press or release W/A/D keys during observation.

