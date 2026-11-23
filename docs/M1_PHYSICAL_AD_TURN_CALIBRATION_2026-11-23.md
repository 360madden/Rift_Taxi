# M1 — First bounded physical A/D turn calibration on LEGION

**November 23, 2026 · 11:21–11:26 AM Eastern · physical RIFT client**

**Status:** **Two real short A/D turns sent and released by Taxi-owned code**, with separate-process release leases, exact Windows process/actor binding, original native before/after evidence and independently inspected game screenshots. This is a real physical **calibration**, not a running Taxi journey or a fully qualified body-heading source.

## Target and safety boundary

| Item | Exact qualified value |
|---|---|
| Machine / executable | LEGION · `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |
| SHA-256 on disk | `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01` |
| Process PID / start UTC .NET ticks | `424` / `639310421805307472` |
| HWND | `1968794` |
| Same owner-key candidate before/after each pulse | `239816685251645959` |
| Scene | Character stationary in open ground near the visible healer Tira Marlas |
| Input policy | **Only A or D**, one `60–160 ms` pulse; `W` is explicitly refused |
| Release | Separate real Windows child process, **reserve ACK before DOWN**, key-up in `finally`, child CLEAR/STOP and bounded watchdog lease |
| Production navigation backend | **Remained disarmed**; no fabricated qualified `LivePose` and no autonomous path execution |

A native Python/PowerShell workflow inspected the actual game scene and recorded a fresh screenshot receipt before attempting physical input. Taxi's `probe-ad-turn` command defaults to **dry-run**. Physical insertion requires explicit `--execute-physical` plus the reviewed screenshot SHA, exact PIN/PID/start/SHA/HWND, expected owner key and new separate audit and report paths. Neither the screenshot inspection nor the process restore changes installed addons or sibling repositories.

## Verified physical A/D results

| Measurement | One A pulse | Opposite D pulse |
|---|---:|---:|
| Requested hold | **100 ms** | **100 ms** |
| Actual DOWN-to-UP monotonic interval | **104.3 ms** | **101.1 ms** |
| Native current actor XYZ before/after | Unchanged | Unchanged |
| Actor/position matrix yaw candidate Δ | **−17.90656°** | **+18.23284°** |
| Player-system scalar yaw candidate Δ | **+11.65491°** | **−12.14681°** |
| OS SendInput DOWN/UP accepted | Yes / Yes | Yes / Yes |
| Windows key-down bit sampled during held key | A=true | D=true |
| W/A/D all UP after key release | Yes | Yes |
| Child key reservation cleared/STOP | Yes | Yes |
| Current actor-key/epoch/window changed | No | No |
| Game input independent visual corroboration | Scene rotated after A, roughly returned after D | Same corroboration; **not** a verified standalone body yaw |
| Autonomous navigation / destination arrival | Not tested | Not tested |

**Exact observed angles:**
- Before A: player-system scalar **−19.2728199131°**, actor-matrix **+21.8530823843°**.
- After A and on settled follow-up: scalar **−7.6179123257°**, actor-matrix **+3.9465193508°**.
- After D: scalar **−19.7647215994°**, actor-matrix **+22.1793609484°**.
- Across A then D, matrix final versus initial ≈ **+0.32628°**; scalar ≈ **−0.49190°**. Small differences are plausible timing/float32/visual effects; they must not be silently collapsed to exact reversal.

The two candidate angles change in **roughly opposite signs** but **different magnitudes**; it would be wrong to assume either already equals body-facing orientation. The reviewed screenshots show a visible rotation of the world/camera around the player with A, followed by a visual return after D. A **camera-only negative control** and ideally an independently qualified body-heading reference are still required before promoting a heading into the runtime `LivePose`.

There was **no X/Y/Z change** during either short turn, consistent with a character rotating in place. This is stronger evidence for native orientation responsiveness than the prior purely stationary captures. It does **not** prove XYZ freshness during forward travel, because W was never sent.

The external child was real and `dryRun=false`. Both parent key-ups succeeded, so the release child received CLEAR/STOP and did not need to issue an emergency key-up. Its ability to recover after physical parent crash/late SendInput remains **not physically proven**. The child's clearance only establishes a software release ledger state; independent game-consumed key-up and settled in-game release require additional evidence.

## Original source SHA-256 receipts

The following files remain under Git-ignored `C:\work\Rift_Taxi\artifacts`. Hashes are of actual retained bytes; do not manufacture missing screenshots or game frames.

| Original local receipt | SHA-256 |
|---|---|
| `m1-turn-before-20261123-1121.jpg` | `D688C9F936C16C14E53D764BF9A4A19EE7844223E90459E5AEB10195061FB741` |
| `m1-turn-A-20261123-1122.json` | `c501981cf5c324fdfe477b07294505f4fbc5f36880fbd44cbe54126f34990603` |
| `m1-turn-A-release-20261123-1122.jsonl` | `81cd3a6b3f80480aba9b91dcf45a677887ed11c7f7bc878aad946a319c1010a7` |
| `m1-turn-afterA-20261123-1123.jpg` | `9E63B9AA786A6C934CD77CBBF192B8E709475A2F5940A8BDFE0FAA0B68143868` |
| `m1-turn-afterA-settled-20261123-1124.json` | `6ad170c6be3989991d80b4cfafa6646f200db2f6e9f0b5cc00f6284d9975b3cc` |
| `m1-turn-D-20261123-1125.json` | `f2bceedf601211514584c6a7b2fee9b94c98d6d6d4c1fc674c3e88d360cc32d2` |
| `m1-turn-D-release-20261123-1125.jsonl` | `6280d7a6f93c1253fe7f11ec01146b4969ebc3918469b9730bfa13437e6951` |
| `m1-turn-afterD-20261123-1126.jpg` | `4B1A1BE4AE98F7A979B5DF3960B866B7499A0C74D6A3AB5B312788ABB98833CE` |

The original frames are full game-window downscaled JPEG images at 760×415 pixels. They corroborate *visible scene orientation change* but cannot alone establish precise body-facing degrees. The screenshots may be taken slightly later than their associated native samples, so do not invent exact frame/action synchronization.

## Taxi-owned implementation

- `rift_taxi/release_supervisor.py`: a special **turn-probe-only release child** can start from a fully specified OS release pin **without pretending native yaw is already qualified**, unlike the production `LivePose`-gated controller. For physical use, it independently checks expected foreground PID, start epoch, HWND and executable SHA; the ordinary production `ExternalReleaseSupervisor.start` still requires an actual qualified `LivePose`.
- `rift_taxi/turn_probe.py`: one bounded A or D pulse, pre/post native matrix/XYZ/yaw candidate reads, read-only key observations, exact source/owner checks and unconditional UP attempt in a `finally`. The short probe refuses W, nonboolean flags, existing W/A/D down state, invalid source and uncertain release. It publishes no completed report if any essential step fails.
- `rift_taxi/cli.py`: `probe-ad-turn` is default dry-run, requires explicit physical opt-in, expected owner key, newly created release-audit and output paths and a reviewed scene image hash. **No production navigation or waypoint command is armed by this diagnostic**.
- `tests/test_turn_probe.py`: 10 focused regression tests, including actual separate Windows child **dry-run** validation, invalid key/hold refusal, simulated UP/DOWN failures, source owner mismatch and CLI intent forwarding. The full repository suite then passed **271/271 tests** on Python 3.14.10 LEGION.

## Remaining M1 qualification and optimal sequence

1. **Camera-only negative control**: record native scalar/matrix and visual scene during camera-only rotation, separate from A/D body-turning. Do not assume a heading is body-facing until this distinction is supported by observed screen evidence.
2. **Bounded W-only calibration**: add a separately supervised **short forward pulse** with exact owner/scene/readback to prove source XYZ changes during a physical action; then verify fresh post-release state. Keep this distinct from autonomous route execution.
3. **Independent release robustness**: measure delayed input and unexpected process death against actual OS/game keys; verify the game does not remain moving/turning after STOP.
4. **Actor/zone/source clock binding**: match readable current actor and zone plus addon API poll activity. Explicitly note that `Inspect.Unit.Detail` may refresh cached XYZ.
5. Only promote an actual qualifying `LivePose` and start an initial controlled straight route if those gates pass. Never declare M1 complete on the basis of these two short turning pulses alone.

**User-directed operating policy:** [AI-first automation](AUTONOMY_POLICY.md): perform machine/game interaction and tests autonomously with minimal manual intervention, within exact-session and release qualification. No RR2, RiftWorld, Telara Fly or installed addon files were modified.
