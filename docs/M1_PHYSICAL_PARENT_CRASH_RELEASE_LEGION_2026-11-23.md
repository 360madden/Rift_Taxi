# M1 — Physical A-key release after real sender process crash (LEGION)

**Monday, November 23, 2026 · 1:39–1:44 PM EST · physical RIFT game client**  
**Qualification:** **One physical abrupt-parent-exit test confirmed the *independent* release child sent an OS-accepted A key-up without any parent/launcher backup.** A second controlled crash with a **100 ms pre-crash A hold** caused a native actor-matrix angle change and then stable post-release native readings. This materially advances M1 fault recovery, but **game-consumed release in all failure states and crash-proof navigation remain unqualified.**

## Why this test differs from a normal STOP

The previous supervised A/D/W actions had the parent explicitly sending key UP, then clearing the child's reservation. The release child never needed to act. Here, Taxi deliberately exited the **input sender process using `os._exit(37)`** after sending a real A DOWN. The Python `finally`, cleanup and normal key-up paths of that sender **did not run**. The independent release child, already holding an ACKed A reservation, received EOF and sent A UP through its own Win32 `SendInput`.

A **third, surviving Taxi launcher** supervised the experiment and was prepared to issue a separate backup A UP if the child failed. On both physical crash tests, this backup was **not needed**. A final outer PowerShell guard also sampled W/A/D UP and would have sent A UP if it remained held. It did not have to.

### Exact game admission

| Item | Verified value |
|---|---|
| Host | LEGION physical Windows client; no VM |
| Executable | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |
| On-disk executable SHA | `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01` |
| PID / process creation UTC .NET ticks | `424` / `639310421805307472` |
| HWND | `1968794` |
| Current native self-owner candidate | `239816685251645959` |
| Scene | Real, independently inspected current-game foreground screenshots of stationary player in open ground by healer / stone steps |
| Physical input | **A only**; **never W** or autonomous navigation |
| Other input | W/A/D all initially UP; no mouse action |
| Foreground | Exact game window temporarily foregrounded and then prior window restored |
| Source artifacts | Git-ignored local `artifacts/`, SHA-256-indexed below |

## Three deliberately distinct observations

| Evidence | Immediate sender crash | Ordinary A control | 100 ms held A, then sender crash |
|---|---:|---:|---:|
| Parent deliberately exits with `os._exit(37)` | **Yes** | No | **Yes** |
| Parent sends normal A UP | **No** | Yes | **No** |
| Actual OS A DOWN accepted | Yes | Yes | Yes |
| Extra pre-crash A hold | 0 ms | Normal 100 ms action | **100 ms** |
| A DOWN to accepted A UP | **168.027 ms** | **100.812 ms** | **108.499 ms** |
| Who sent A UP? | Separate child | Original parent | **Separate child** |
| External release STOP reason | `parent-disconnected` | `explicit-stop` | `parent-disconnected` |
| Backup release needed | No | No | **No** |
| Observed native actor-matrix delta | **0.000°** | **−17.800379°** | **−17.979023°** |
| Native XYZ displacement | 0 | 0 | 0 |
| Native heading after vs. delayed settled | Same | Normal probe lacks delayed sample | **Same** |
| W/A/D after action | All sampled UP | All sampled UP | All sampled UP |

**Interpretation:** The immediate-crash A DOWN was accepted by Windows and its high bit was independently observed, but the native actor heading **did not move**. It would be incorrect to claim this verified that the game actually acted on the key-down. The ordinary control just afterward confirmed the same game was responsive to a normal 100 ms A press (**−17.800°**). With the next independently supervised 100 ms pre-crash A hold, the game-associated native actor matrix changed **−17.979°**, and that heading stopped changing after the child issued A UP. This is **substantially stronger physical release-response evidence** than either a dry-run crash or an OS-only key-up acknowledgement.

The held-then-crashed experiment had native matrix **−21.290548° → −39.269571°**. Its player-system scalar changed **+15.197280° → +35.699087°**, confirming that the scalar and matrix can have different update magnitudes, even though their post-W relationship has looked closer in separate experiments.

## Independent child process and timing

During the **100 ms pre-crash hold**:

1. Launcher verified fresh screenshot SHA, exact foreground process/build/HWND and same-owner native candidate, with W/A/D up.
2. Input sender created a real Windows external-release worker, obtained `reserve(A)` and `renew` ACKs, verified foreground and owner again, and inserted A DOWN through `SendInput`.
3. The sender durably wrote an original A-down marker with monotonic timestamp `27998.416723`, then held A for 100 ms.
4. Sender deliberately terminated with exit code **37** and **never sent A UP**.
5. Independent release child detected `parent-disconnected` and its own native A-UP was OS-accepted at monotonic `27998.5252216` — **108.499 ms after actual A DOWN**.
6. The surviving launcher's high-bit check saw A held during the action, then W/A/D all UP afterward. **No launcher backup A UP** was attempted.
7. Native actor matrix after the crash was **−39.269571°** and matched its delayed settled reading. A subsequent **12-sample** read-only series on the exact game process found one XYZ, one matrix angle, **12/12 actor/position raw-bit matches**, and **24/24 W/A/D high-bit snapshots all UP**, with median sample spacing **130.055 ms**.

Both the first zero-hold and subsequent held-then-crashed experiments had the independent child's real `native-key-up-attempt` accepted and ended with `parent-disconnected`. These events do **not** prove the sender, release helper, Windows scheduler or RIFT will behave identically under every possible crash or focus-loss race.

## New standalone Taxi code

`rift_taxi/crash_release_probe.py` provides a **diagnostic-only** launcher and internal abrupt-exit child. Its CLI is not wired into normal Taxi navigation. It requires an explicit `--execute-physical`, a fresh (maximum 180 seconds) real JPEG/PNG source screenshot verified against its original SHA, fully pinned same-session host/PID/epoch/path/SHA/HWND and player owner, new report/audit/marker/guard paths, and all W/A/D initially up.

- The only permitted physical input is **A**. `--precrash-hold-ms` is strictly **0–140 ms**; W/A/D navigation and continuous routes are never armed.
- The input sender has no normal-release path once the deliberate `os._exit(37)` occurs. Its separate child holds a **0.55-second TTL** and attempts emergency UP on EOF/lease expiry.
- A surviving launcher monitors the crashed parent and release child for at most a bounded interval. It checks that the original child audit includes reserve/renew, a real native A UP accepted **after** an original A-down marker, a child STOP and correct process identity. A ledger-clear alone is not sufficient.
- If the child fails, the launcher attempts a distinct **backup A UP**. If the sender hangs, the launcher **kills and reaps it before** attempting backup UP, closing the obvious late-DOWN-after-rescue ordering flaw. A final sampled A-down also triggers a separate documented rescue attempt.
- Every artifact is **created new**; no old raw data is overwritten. Diagnostic success never sets `LivePose.actor_yaw_verified`, `gameConsumedReleaseVerified`, `crashProofReleaseGuaranteed` or `M1Complete`.
- A guard challenge token used to coordinate internal processes remains in Git-ignored local evidence; it is **not published** to GitHub.

### Original source receipts

All hashes below were computed from physical files on LEGION. Files stay in `C:\work\Rift_Taxi\artifacts`, not Git.

| Artifact in `artifacts/` | SHA-256 |
|---|---|
| `m1-crashA-before-20261123-1339.jpg` | `44b4444af2c57ed1e674b90ba654f9b39a6ba855b91ddf9af2578b87f0b1ebb1` |
| `m1-crashA-before-native-20261123-1339.json` | `5618619d74806788c009570493e090982664a135a64f3a3ae1f1d8210a518af9` |
| `m1-crashA-release-20261123-1340.jsonl` | `8568f7303c4a4c1c37b1d4fa0ed0bd659dfe74c850cf7902d1a21f5ef7b5f557` |
| `m1-crashA-down-20261123-1340.json` | `1c31e6eae052eb5519542839783aad859d5352fbc01dafb9b2a8bced1fcd97bc` |
| `m1-crashA-result-20261123-1340.json` | `62043a7538b3bf4ea402f01962538baf366f200f3c3b4927473371827d47a004` |
| `m1-crashA-after-20261123-1341.jpg` | `6d259938f9930ab95e90de3c8c00a9824107910ce6e4c97d7158c3a0a4091cfb` |
| `m1-crashA-post-series-20261123-1341.json` | `857be47334a0b532ca04b7666b50c3e307a5e3f3ed399d06cf993bc63ff7d9f5` |
| `m1-crashA-control-release-20261123-1341.jsonl` | `06d15b9671ac3917c52e29315717915ab5dfde68f608ed069ffbbb4d558933f6` |
| `m1-crashA-control-turn-20261123-1341.json` | `fcedd7a0fbcc5ae1ecbfd8ef1c93247bd1fb46460bb83c6adb957142856652a7` |
| `m1-crashA-hold100-before-20261123-1343.jpg` | `723537446a3fcff42b90bbce397bedadf4ec04c4199407e7d0234e06ab5e78b7` |
| `m1-crashA-hold100-release-20261123-1343.jsonl` | `27d477af2fe1b99345e81fecc15af2cd9e8a8f678986bfe7e36c1ef3f7d3c262` |
| `m1-crashA-hold100-down-20261123-1343.json` | `79e68435df1ce06649c698ad2af1db9b2b327889435733e19bb998638c58b009` |
| `m1-crashA-hold100-result-20261123-1343.json` | `38eaeeec4d3347ee6745f74a4c7d224682eeae05b0268faa1dda720b7e45d1ac` |
| `m1-crashA-hold100-after-20261123-1344.jpg` | `5bd1bdf4cb5991fce5676fe1ee1c61df71c4c20ee4799dfe0f78e6379adfc9e` |
| `m1-crashA-hold100-post-series-20261123-1344.json` | `5e9e7973c48bcd5a50d8c0cc4f54fd8701916acd9b22b78465bd41fc8ddc9b8f` |

## Remaining M1 boundaries

**Validated here:** actual OS-A input, separate-parent abrupt crash, surviving child OS-A UP **after** crash, native orientation response when A was intentionally held before exit, unchanged native pose on later samples, all W/A/D observed up after, and no automatic route driving.

**Not yet validated:** physically consumed release when game window loses focus, crash of the release child itself, queued/late DOWN after parent stalls, every crash timing, and independent authoritative character-body yaw and zone/native XYZ freshness. Native data may be refreshed by installed Telemetry addon API polling. No universal guarantee is appropriate.

**Next optimal work:** derive strict M1 acceptance from independent actor/zone/pose evidence, test the remaining specific release race with an independently guarded fault experiment, then begin a scoped physical straight-route acceptance only when those gates pass. No general GUI, world rewrite or sibling repo modification is justified yet.

See [current handoff](M1_HANDOFF_2026-11-23.md), [release supervisor design](M1_RELEASE_SUPERVISOR.md), [two-heading body-direction evidence](M1_TWO_HEADING_ALIGNMENT_LEGION_2026-11-23.md), [validation requirements](VALIDATION.md) and [AI-first policy](AUTONOMY_POLICY.md).
