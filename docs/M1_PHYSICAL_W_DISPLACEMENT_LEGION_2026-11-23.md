# M1 — First physical W-only forward displacement and release on LEGION

**November 23, 2026 · 12:36–12:38 PM Eastern · physical RIFT client**  
**Status:** **One real, bounded 100 ms W pulse was sent and released**, followed by same-owner native XYZ changes, source-hashed independent post-release evidence and screen captures. **M1 remains incomplete**: body heading, passive native freshness, game-consumed STOP and process-crash release are not qualified.

## Target and admission

| Item | Value |
|---|---|
| Host | LEGION (physical, not VM) |
| Executable | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |
| On-disk SHA-256 | `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01` |
| Process / creation epoch | PID `424`; `639310421805307472` .NET UTC ticks |
| Window | HWND `1968794`; foreground verified during capture and diagnostic |
| Native current self-owner key candidate | `239816685251645959` |
| Scene evidence | Screen-captured actual RIFT foreground window: player stationary on apparent open ground by healer/wagon; suitable for one short forward pulse, not an unrestricted route |
| Input | `probe-w-forward --execute-physical`; W only; requested 100 ms |
| Independent release | External release child with W reservation ACK/renew before DOWN, OS UP, CLEAR and STOP |
| Production navigation | **Disarmed**; no autonomous route or `LivePose` promotion |

The standard desktop screenshot endpoint returned `IO_ERROR`, so a separate **read-only OS foreground-window screenshot** was obtained with Windows `CopyFromScreen` and saved as a SHA-pinned original in the ignored `artifacts/` folder. The native baseline, scene and exact RIFT identity were checked before the physical pulse. Windows focus and current actor owner were rechecked by the diagnostic.

## Physical result

| Measurement | Observed |
|---|---:|
| Requested W hold | **100 ms** |
| Actual OS DOWN-to-UP monotonic interval | **100.7066 ms** |
| OS `SendInput` W DOWN/UP accepted | **Yes / Yes** |
| W high bit during hold | **True** |
| W/A/D all UP after release | **Yes** |
| External release child CLEAR/STOP | **Yes** |
| Native owner key before/after/after-delay | **Same** |
| Native XYZ before | `[7209.92626953125, 871.7515869140625, 3024.36328125]` |
| Native XYZ after W | `[7209.39794921875, 871.758544921875, 3024.7236328125]` |
| Native XYZ after an additional ~200 ms wait | **Unchanged** from after W |
| Delta X/Y/Z | `[-0.5283203125, +0.0069580078125, +0.3603515625]` |
| Horizontal displacement (XZ, game source units) | **0.639512** |
| Actor matrix angle candidate delta | **0.0°** |
| Player-system scalar delta | **+0.5714068°** |
| Independently qualified body heading | **No** |
| Game-consumed release after crash | **Not tested** |

The naive 0.639512 / 0.1007066 = **~6.35 source-units/s** is merely a *single-pulse displacement divided by OS hold time*. It is not a calibrated speed or a causally proved motion rate: the native before/after samples bracket a wider interval, and the cache may be refreshed by installed `Inspect.Unit.Detail` polling. It is broadly consistent in scale with the **6.632 source-units/s** median reported from one earlier RR2 trace, but the sources and input intervals differ. Avoid extrapolating these measurements to a driving model.

The initial physical post-release capture returned the changed XYZ; the diagnostic's delayed settled candidate was identical. This is stronger than the previous A/D-only experiment, which did not show changed XYZ. It still does not independently prove *which* native writer refreshed the values or whether all future releases will be consumed by the game.

## Separate post-release readback

At approximately **12:37–12:38 PM Eastern**, Taxi ran the separate `observe-native-series` read-only command against the same pinned process with **12 samples** and a requested 130 ms start spacing, along with sampled Windows W/A/D state bits.

- **12/12** same owner, **12/12** matching actor/position raw matrix bits.
- **One unique XYZ** across the 12 samples, matching the diagnostic's post-release settled XYZ.
- **24 keyboard snapshots** (before and after each native read), **no W/A/D down high bits**.
- Observed sample gaps **128.36–132.00 ms**, median **129.96 ms**.
- This series ran **after** the W pulse, not concurrently. It demonstrates sampled later stability, **not** an in-flight motion trajectory or game-consumed release under crash.

A separate RIFT screenshot was saved after the pulse. Static world framing and character position alone are inadequate to measure 0.64 source units exactly, so the screenshots are **scene corroboration**, not a pixel-based displacement proof.

## Original local receipts (Git ignored)

| Path relative to `artifacts/` | SHA-256 |
|---|---|
| `m1-physical-current-scene-20261123-1234.jpg` | `2608D820FBAAC267267CDF0CCF77852FC3A6BE802AEA429287505E762DF2792E` |
| `m1-fresh-beforeW-20261123-1236.json` | `6069a257730ec4d2a072eb3d79fc36a504251339aa1f3d4ccaa52f82b9369548` |
| `m1-W-physical-20261123-1238.json` | `fef24dd4ca8d8e0008ec1689b931ef5912d7ca21dfd920aa10028b6d9513a934` |
| `m1-W-physical-release-20261123-1238.jsonl` | `f2418aa87e619a6eb94ff3fa370d50cfeedab7e1e9c5f37505c43f0caf304e7d` |
| `m1-physical-afterW-20261123-1238.jpg` | `98F60F9EA48D3663C99CB319A283851E98C9ADFAD470A05701AA2AC5E43E9A02` |
| `m1-W-postrelease-series-20261123-1238.json` | `b73b7f974a810ddbae3a901b6a933716ff0c992a0739194eaa20c58d9cf133bb` |

## Next M1 acceptance gates

1. **Camera-only negative control:** use RIFT's documented left-mouse camera orbit, separate from A/D body-turning, and independent release; inspect native XYZ/matrix/scalar before/after and screen evidence.
2. **Heading semantics:** independently distinguish body heading, camera yaw and movement bearing. This physical W example does not qualify actor heading.
3. **Release under fault:** demonstrate that interrupted sender/parent and late DOWN cannot leave RIFT physically moving; the existing child lease is only an exercised release prototype.
4. **Freshness and zone:** independently qualify actor/zone and native position refresh (beware the installed Telemetry addon API polling).
5. **M1 final receipt:** only after the above, promote the qualified `LivePose` and assess initial controlled straight movement without sibling services.

For the diagnostic implementation see [W-only probe](M1_BOUNDED_W_FORWARD_PROBE_2026-11-23.md), [A/D turning](M1_PHYSICAL_AD_TURN_CALIBRATION_2026-11-23.md), [validation](VALIDATION.md) and [AI-first autonomous workflow](AUTONOMY_POLICY.md).
