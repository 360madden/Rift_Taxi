# M1 moving native series — LEGION, 2026-11-28

**Result:** one bounded physical W pulse overlapped 96 accepted native observations,
including two during the recorded hold. XYZ changed and then remained settled.
This advances moving-candidate acquisition evidence; M1 remains unaccepted and
production navigation remains disarmed. Execution was November 28 at 07:01 PHT
(November 27 at 23:01 UTC).

## Execution and source

Source commit: `a97bac9cf8163ee495b3b0c73db2d68360360a1c`.
[CI run 46075963311](https://github.com/360madden/Rift_Taxi/actions/runs/46075963311),
attempt 1, passed all four required jobs with remote-head checks before/after.
Reviewed job-log totals: Windows 860 passed; each Linux suite 844 passed with
16 platform skips. The checkpoint verifier establishes required-job/step success,
not independent test-count verification.

The sole physical job was `taxi_20261128_observed_forward01`,
23:01:44.662–23:01:51.302 UTC. The original observer, forward probe, sender and
external release child were retained. The ignored wrapper requested one 100 ms W
pulse and a separate 96-sample series at 50 ms spacing, with a 10 s observer limit.
Actor/position matrices, refresh guards, raw zone and W/A/D polling were enabled.
No actor stored-translation experiment or repeat input accompanied recovery.

| Historical pin | Value |
|---|---|
| Host / character | LEGION / Atank, level 45; reviewed clear grass |
| PID / start UTC ticks | 12092 / 639313885727379680 |
| HWND | 133394 |
| Executable | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |
| Executable SHA-256 | `df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01` |
| Owner candidate | 239816685251645959 |
| Raw zone candidate | 1216123138 / 0x487C9102 |

These are archived experiment identities, never reusable live authorization.
Fresh preflight derived owner/raw zone. Every accepted series row retained both.

| Executed module | SHA-256 |
|---|---|
| `rift_taxi/native_series.py` | `83a07d5d2b65df9ecd9271206c079e4744375d323e2163a52c810ede6e66dcab` |
| `rift_taxi/turn_probe.py` | `79167da710cd4f8af5273868f3c39eb338cba1fbc7224a9b89c2d20f7856fe4d` |

## Measured response

All timing below uses recorded same-host monotonic seconds. DOWN/UP timestamps
bracket parent sender calls; they are not exact game-consumption instants.

| Measurement | Observed value |
|---|---|
| Parent DOWN / UP timestamps | 67341.1117532 / 67341.2142869 s |
| Recorded hold | 102.5337 ms; requested 100 ms |
| Accepted samples | 96/96: 24 before, 2 during, 70 after recorded hold |
| Observation gap | 50.4701 ms median; 44.1807–55.5373 ms range |
| Observation window relative to DOWN | −1.1715129 to +3.6116933 s |
| Coverage after recorded UP | 3.5091596 s |
| First changed XYZ, sample 25 | +33.9042 ms after DOWN |
| Final XYZ first observed, sample 27 | +34.6202 ms after UP |
| Horizontal displacement | 0.6085430726 source units |
| Actor/position matrix raw-bit agreement | 96/96 |
| Actor matrix angle | 57.2450515878° throughout |
| Candidate travel bearing | 57.2343890821° |
| Travel minus matrix bearing | −0.0106625057° |

| Position | X | Y | Z |
|---|---:|---:|---:|
| Initial, samples 1–24 | 7149.8876953125 | 871.7828369140625 | 3057.856201171875 |
| Sample 25 | 7149.78662109375 | 871.7828369140625 | 3057.92138671875 |
| Sample 26 | 7149.498046875 | 871.7828369140625 | 3058.107177734375 |
| Final, samples 27–96 | 7149.3759765625 | 871.7828369140625 | 3058.185546875 |
| Delta | −0.51171875 | 0 | +0.329345703125 |

Travel bearing uses `atan2(-ΔX, ΔZ)`. Its close matrix agreement is candidate
kinematic evidence, not independently qualified absolute body yaw. First-change
and final-position times are sampled observation bounds, not exact response
latency or proof of post-UP inertia. The probe's after/settled captures agree.
A separate later native capture at UP +211.2023698 s matches the final XYZ,
owner, raw zone and matrix. It does not fill the intervening observation gap.

## Input and release evidence

The probe records OS-accepted W DOWN and UP, W sampled DOWN during the hold,
and W/A/D sampled UP afterward. The observer made 192 polls per key: four W-DOWN
polls and no A/D-DOWN polls. These are sparse OS snapshots, not continuous input
tracking or proof that RIFT consumed each event. The observer's
`inputInjectedByTaxi=false` describes its own read-only operation; the separate
probe correctly records `inputInjectedByTaxi=true`.

The child audit records reserve, renew, CLEAR and explicit STOP. Parent UP
preceded CLEAR; the child acknowledged an empty ledger and stopped.
Every `releaseAttempts` array is empty: **the child did not issue emergency UP**.
This run therefore adds no crash/emergency-release qualification.
Independent scene captures before and after the run each sampled all 15 checked
movement/modifier/mouse states UP; those checks are not continuous guarantees.

## Original receipts and derived recovery

Local originals remain under
`C:\work\Rift_Taxi\artifacts\m1-observed-forward-20261128-0701`.
Raw images/JSON are not published to GitHub; this document records their hashes.

| File in that directory | SHA-256 |
|---|---|
| `preflight.json` | `e1f372a1a4bdd3248adda8bfb725b7f4975a2cd1e9f6f03bd194c11381f1064f` |
| `probe.json` | `e84133b27481ef87abd4d48934d5f4cdc61bf776bcfa9a861c0b06ce16219e52` |
| `series.json` | `3e233a84ac7e2be1c0ead5cbaad3dcfebff03852ad4f536dad705247838ccd5a` |
| `release.jsonl` | `603f6460cebf85c4f2c8353bc25fd2271c32f79379c242a0a589c1f5004b7ca9` |
| `post-release-native.json` | `60a07739976a4496c9f5a2156659315ee59bff979005c44f120631ad56059dd7` |
| `runner-job-failure.json` | `d5af0666e0580093945e386423aed5e4d405642f47c87dab82440cf45e2338e1` |
| `scene-before-metadata.json` | `403bf48b761784a34826000442e9ca81c25d22e42a6decb06eaf4a261df18c62` |
| `scene-after-metadata.json` | `7346ba5a22c0633112d5ff4a9886fdf7fdae3ed22dbd2604a6321bb9620cf67b` |
| `recovery.json` | `f82b44fd5280b58744ccb07a097caf656a7718533d39ab2ddc44d213119285fc` |

Image paths are retained in the metadata. Before: 23:00:10.6244430 UTC,
SHA `5fec070454ab38f2eb934182b6d12b53d0b044f5c2e45063c9eaba673e77a651`.
After: 23:02:36.9847004 UTC,
SHA `df753ae22be881e6a9489300de2e44652481bbf097c1ceb998caec42bf13c98b`.
Both capture receipts report two identity checks, no focus change and no input.

The original wrapper exited **1** after saving `probe.json` and `series.json`:
Windows `poll()` raised `BrokenPipeError [WinError 109]` in finalization.
The original `manifest.json` is absent. Later read-only job
`taxi_20261128_forward_recovery01` produced `recovery.json` at
23:05:18.902664 UTC. It is explicitly derived, not the missing original manifest.
Readiness IPC messages, identity-inspection timestamps and observer exit code
were lost and were not reconstructed or inferred.

## Reporting repair, without repeating the action

The ignored runner was preserved byte-for-byte as
`artifacts/m1_observed_forward_20261128.executed.py`, with a sibling SHA file.
Its repair catches closure at both poll/recv, records channel termination, uses
guarded readiness polling and preserves final metadata through endpoint closure.

Their directory is
`C:\work\Rift_Taxi\artifacts\product-position-review-20261128-0008\artifacts`.

| Ignored source beneath the experiment worktree | SHA-256 |
|---|---|
| Original `m1_observed_forward_20261128.executed.py` | `687992154de6dcd35cc74587a7d6d4c325c7fb05f86b6e5e6baaef1037cfd896` |
| Repaired `m1_observed_forward_20261128.py` | `b47bd0db263bd2afbc2a15d9624b1c3d82dea14259b0f8051051a320dc5da1ff` |
| `m1_observed_forward_pipe_regression_20261128.py` | `112dd752eff9f0a1825b1c3533c07e5876849c0c1029743be767192e3b6f0201` |

Inert job `taxi_observed_forward_piperegression_run_20261128_01` passed.
A spawned fixture reproduced original error 109 after two messages; repaired
cleanup retained both and finalized in memory. Receive-side closure finalized
as incomplete. Only extracted pump/finally AST ran; no game reads or action-main
import occurred. Independent source/log review passed. Original receipts remain
unchanged; the physical action was not repeated.

CI receipt: `C:\work\Rift_Taxi\artifacts\ci-checkpoint-a97bac9-20261128.json`,
SHA `64f36b589d9996a4f8410ac93ba04d4a8611fa384ce1412077b93dd538ab8947`.

## Remaining practical gates

The existing Telemetry/API-polling setup remained active; no API-quiet producer
window was established. All refresh-guard samples were zero, making two known
conditional routes ineligible at those sampled observations. This does not
exclude API-triggered cache refresh between samples. See
[the Telemetry audit](M1_MOTION_TIMING_AND_TELEMETRY_AUDIT_2026-11-23.md).
Matrix agreement and matching owner/raw zone do not establish public zone,
world instance, passive freshness or independently authoritative body heading.

Next, address the separately identified crash/late-DOWN release gap with inert
regression and exact-head CI. Qualify a cache-independent position producer and
independent body/zone authority before further physical acceptance work.
Do not repeat this pulse merely to replace its missing wrapper manifest.
Passive freshness, body yaw, public zone, world instance, universal emergency
release and live journey qualification remain false; no M1/production promotion.
