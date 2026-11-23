# M1 movement timing and installed addon producer audit — November 23, 2026

**Project:** Rift_Taxi on LEGION · **Scope:** source-hashed offline RR2 movement timing, plus **read-only** audit of the installed RIFT Telemetry addon. No RIFT input, game-memory writes, addon edits, reloads, restart or new Taxi journey.

## Result A — original RR2 movement timing, now measured by Taxi

`rift_taxi/motion_timing.py` is a standalone Python standard-library analysis of already validated `taxi.motion-trace/1` observations and supplied W/A/D key edges. It avoids interpolating key-transition boundaries into stable speed samples. It never turns raw **OS key-insertion claims** into independent **RIFT game input-consumption** proof.

The original RR2 bundle was imported previously under `artifacts/rr2-watch-return-original-20261122/`, verified against the SHA-256 of its original source JSONL, and re-read this cycle. The movement-timing report is **not** a new live Taxi movement or a full-route speed study.

| Provenance | Value |
|---|---|
| Original RR2 source SHA-256 | `3d11d21c39520df31f674ad9e3e407239c40e4b5a5b2ac674d74230194622278` |
| Normalized source-verified Taxi trace SHA-256 | `fda91945fb102a0ae1f4d3a4d9f59ec55616e37d785ed9a72010a8972fcc454e` |
| Input clock | Declared **same-host UTC**, not assured monotonic |
| Original source poses / key-insertion edges | **72 / 14** |
| Input-eligible control window | **3.54351 seconds** |
| Recorded W-held duration | **0.577978 seconds**, **16.31%** W duty |
| Maximum sample gap | **0.154526 seconds** |
| Clean pose intervals excluding input edges and large gaps | **57**, totaling 2.864471 seconds |
| W-held intervals | **15** |
| Not-W-held intervals | **42** |
| W+A/D overlap | **0** observed in this short source receipt |
| Validated actor-yaw samples | **0** |

### Observed timing association — candidate estimates only

| Measure | Observed result | Qualification |
|---|---:|---|
| Median XZ sample speed during recorded W-held, transition-free intervals | **6.631974 source units/s** | Correlation with submitted key timeline, not certified RIFT speed |
| 90th-percentile sampled W-held XZ speed | **7.457535 source units/s** | Nearest-rank p90; not speed-mode/mount calibrated |
| Highest sampled W-held XZ speed | **7.631627 source units/s** | Single interval; not a stable player speed setting |
| Median sampled XZ speed without W held | **0** | Valid stationary sample result; does not prove every non-W state stationary |
| Earliest sampled XYZ change after the three reported W-downs | **30.911, 30.518, 29.007 milliseconds** | Temporal **upper bounds to a first changed sample**, not causal reaction latency |
| Post-W-up displacement before the next input edge (first two releases) | **0.076266, 0.073457 source units** | Censored displacement proxies; not verified coast |
| Third release | **Unavailable** | No subsequent qualifying pose in the recorded window |
| Actor yaw rate and turning while W held | **Unavailable** | No qualified yaw samples or combined W/A/D holds |

The two post-up distances may include movement that began before the recorded key-up and are **not** a physics coast parameter. The initial-change timing can reflect sampling cadence or other state producers. A conservative analyzer now censors all W-down and W-up windows at the **next input edge** rather than absorbing later control actions. It excludes intervals touching key transitions and gaps over 0.25 seconds; first-change searches are capped at 512 samples with explicit truncation reporting.

The report sets `movementCausedByWVerified=false`, `gameKeyReleasedVerified=false`, `coastingAfterReleaseVerified=false`, `turnDirectionCalibrated=false` and `suitableForLiveSteeringCalibration=false`. These are deliberate evidence boundaries, **not defects**.

### Reproduce without a running game

Run in PowerShell from `C:\work\Rift_Taxi`:

```powershell
python -B -m rift_taxi measure-motion-timing .\artifacts\rr2-watch-return-original-20261122\trace.json --out .\artifacts\motion-timing-unique.json
python -B -m unittest discover -s tests -p test_motion_timing.py -v
python -B -m unittest discover -s tests -v
```

Output must use a **new** filename; the CLI refuses overwriting evidence.

The original source, normalized trace and derived report remain under Git-ignored `artifacts/`. The final refined report `artifacts/rr2-watch-return-original-20261122/timing-evidence-censored-20261123.json` has SHA-256 `8fa9ba095c16187d0995961d3a8dd33bf716c2db30468ebc498331fcb5c974ad`. Another earlier intermediate, pre-censoring report was superseded; use the final report as the retained reference.

## Result B — installed Telemetry addon can interfere with API-quiet native freshness tests

The addon installed under `%USERPROFILE%\OneDrive\Documents\RIFT\Interface\AddOns\Telemetry\` contains **two separate** handlers that, if loaded and started, read player details with `Inspect.Unit.Detail` on game update callbacks:

| Installed source | Observed SHA-256 | Relevant implementation |
|---|---|---|
| `main.lua` | `854734C431E1404849CE44044A4788EC55183ADC5F74E03154D6733AFC2E9F0A` | `SAMPLE_INTERVAL = 0.10` (line 22); `update` calls `render(unitDetail("player"))` (line 422); `unitDetail` calls `Inspect.Unit.Detail` (line 187); update bound to `Event.System.Update.Begin` (line 585) |
| `telemetry.lua` | `A08062A2299A5F723A19BAB759A4EB819C9C725939EF4E1D5CB22CB072EE41A2` | `FAST_PERIOD = .1` (line 6); `publish` calls `unitDetail(playerId)` (line 514); the update gate advances `nextFast = clock + FAST_PERIOD` (line 594); update bound to `Event.System.Update.Begin` (line 639) |

**Implication:** If these two addon paths are loaded and active, there can be approximately **two player-detail lookups per 0.10-second update period**, subject to actual frame scheduling. This is *configured polling*, not a measured callback count or verified live-loaded state. Additional installed RIFT addons (including RR2) may independently invoke the same API. No producer-side active-invocation receipt or API-quiet observation was captured in this cycle.

Because RR2's source review demonstrates that `Inspect.Unit.Detail` may refresh the native XYZ cache, a native XYZ record obtained after one of these calls may reflect the getter's own activity. **Do not use API/native agreement alone to certify passive XYZ freshness.** Conversely, the 0/0 refresh guard snapshots in Taxi do not prove all other engine writers are absent.

To test true passive advancement later, document loaded addons, arrange a verified API-quiet interval **without changing installed addons by default**, and record native-before/independently observed action/native-after with exact timing. If disabling addon polling is considered, that modifies the user's game configuration and should be explicitly planned and restored; no such change was made here.

The desktop screenshot adapter was attempted against the exact game HWND but returned an I/O error. Therefore no corroborating visual coordinate image was admitted in this cycle. The temporary game-window restore ended and the game returned to its minimized state.

## Development and acceptance status

- Source-aware motion timing code and tests run without RR2/RiftWorld/Telemetry services.
- The recorded speed estimates are candidates for **bounded simulation parameter exploration**, not approved constants for automatic live control.
- A future **A/D-turn + sustained W** trace with independently qualified body yaw is needed before calibrating turn rates or comparing real Pure Pursuit versus Stanley steering.
- M1 remains incomplete: full passive freshness, body-facing, physical input/release and arrival are not independently qualified.
- No sibling repo, permanent game addon, saved variable or executable was modified.

**Recorded regression result for this cycle:** 233/233 tests, Python 3.14.10 on LEGION.
