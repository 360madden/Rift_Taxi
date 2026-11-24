# RIFT Taxi — patch recovery runbook

**Prepared:** November 23–24, 2026 (EST).  
**Canonical host:** LEGION · `C:\work\Rift_Taxi`.  
**Planning window:** Tuesday, November 24, 2026; no publisher announcement or new build is asserted.

## 1. Immutable pre-update evidence

The existing Update Helper at `C:\work\Update Helper` owns installation capture. Taxi does not need another scanner or a sibling runtime dependency. Its verified **before** manifest is:

- Path: `C:\work\Update Helper\before-20261124-legion.json`
- Manifest SHA-256: `6612cab5ad31162cc0eab21266ed3839c4a2ef1e12e3a2aa82536d5b195c983e`
- RIFT x64 executable SHA-256: `df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01`
- Scope: 266 files, 26,754,214,661 bytes; Update Helper verification exit 0. The executable SHA also matches the recorded November 23 M1 physical evidence in `M1_LIVE_NATIVE_LEGION_2026-11-23.md`; this is historical build corroboration, not fresh process qualification.
- Taxi baseline commit: `dbfff0f01126fdc6b2776579ac1643c8f6c14de2`. Fresh baseline: 442/442 Python tests passed, 59.103 seconds, Python 3.14.10.
- Doctor: offline-replay-ready, stdlib runtime, candidate reader available; qualified native reader, public zone/world-instance, movement qualification and game input all FALSE.

The two files introduced for this patch window (`rift_taxi/patch_readiness.py` and `tests/test_patch_readiness.py`) only consume saved manifests and have eight focused passing tests. The actual pinned before-manifest test also passed. The integrated suite passed **450/450 tests in 54.843 seconds** (exit 0); the expected wrong-pin rejection printed by its negative CLI test is not a failure. `git diff --check` also passed. No after capture exists in this receipt and no game update, live process, new-build compatibility or movement was verified.

**November 24 pre-patch bug hunt:** Windows path aliases, reserved names, invalid characters, file/directory conflicts, duplicate or replaced evidence files, inconsistent hash lengths and empty executables are now rejected. All 15 focused tests passed; the original 266-file manifest passed with its unchanged SHA-256 pin. The full suite passed **457/457 tests in 65.305 seconds** (exit 0). Both PowerShell blocks parsed successfully without execution; `git diff --check` passed before this documentation-only update. No game or updater operation was executed.

Preserve the original baseline, all November 23 physical receipts, and frozen synthetic V1/V2/V3 evidence. Local ignored artifacts are **not** included in Git backups. Do not reuse the archived PID, HWND, process start, actor, zone, map transforms or timing as current observations. Do not change the game, installed addons, RR2, RiftWorld or Telara Fly from Taxi work.

## 2. Repeatable offline preflight (before the update)

Taxi now has a development-only evidence and diagnostics runner. It requires the actual execution host, a clean committed checkout, the original manifest pin and an explicit minimum regression count. It saves complete original manifest copies, separate command logs and their SHA-256 hashes, the Git HEAD, the doctor verdict and the test result to a new ignored directory. It never modifies the game or its sibling repositories.

```powershell
Set-Location -LiteralPath 'C:\work\Rift_Taxi'
python -B -m rift_taxi.patch_check --run-id pre-20261124-01 --expected-host LEGION --before '../Update Helper/before-20261124-legion.json' --expected-before-sha 6612cab5ad31162cc0eab21266ed3839c4a2ef1e12e3a2aa82536d5b195c983e --minimum-tests 466
if ($LASTEXITCODE -ne 0) { throw 'Taxi offline preflight blocked; inspect receipt' }
```

The final receipt is `artifacts/patch-check-pre-20261124-01/receipt.json`. Use a unique run ID for every attempt. A blocked or interrupted run must never be treated as successful. The recorded source HEAD and manifest bytes are checked again after the tests. This detects observable drift, not an atomic repository snapshot. A preflight is not a new game-file scan.

**Verified operational rehearsal (November 24, 00:16–00:17 EST):** LEGION at committed HEAD `ab65e4b77636bb813de86d502c7991b328a26b36` completed the real offline preflight (exit 0) with the original pinned 266-file manifest, doctor and **466/466 tests passing in 56.937 seconds**. The nine new workflow tests passed, all three runbook PowerShell blocks parsed, and the source/evidence rechecks passed. Local receipt: `artifacts/patch-check-pre-20261124-verified-01/receipt.json`, SHA-256 `2651bcf64c8a376814fc498c09b13a5393d056a817de24901ae297bedd7cf3a8`. Independently rehashed Update Helper's preserved 60,574,536-byte pre-patch executable: it matches the pinned executable SHA above. No post-patch capture or live compatibility claim is made. Local receipts and the preserved executable are not included in Git.

## 3. Recovery order after the updater completes

### P0 — establish stable file evidence

Verify the connected machine is LEGION, and confirm the updater is actually finished before capturing. No client restart, input or modification is part of the offline workflow. Run in PowerShell:

```powershell
Set-Location -LiteralPath 'C:\work\Update Helper'
python -B -m unittest -v test_update_helper test_post_patch test_verify_cycle
if ($LASTEXITCODE -ne 0) { throw 'Update Helper regression failed' }
python -B update_helper.py verify before-20261124-legion.json --expected-sha256 6612cab5ad31162cc0eab21266ed3839c4a2ef1e12e3a2aa82536d5b195c983e
if ($LASTEXITCODE -ne 0) { throw 'Baseline verification failed' }
python -B post_patch.py --expected-host LEGION --before before-20261124-legion.json --expected-before-sha256 6612cab5ad31162cc0eab21266ed3839c4a2ef1e12e3a2aa82536d5b195c983e --prefix patch-20261124-attempt-01
if ($LASTEXITCODE -ne 0) { throw 'Capture or comparison failed' }
python -B verify_cycle.py --before before-20261124-legion.json --prefix patch-20261124-attempt-01 --expected-evidence-host LEGION --expected-before-sha256 6612cab5ad31162cc0eab21266ed3839c4a2ef1e12e3a2aa82536d5b195c983e
if ($LASTEXITCODE -ne 0) { throw 'Independent bundle verification failed' }
```

Use the current Update Helper one-command capture cycle and its independent saved-bundle verifier, rather than maintaining a duplicate scanner or manual capture sequence in Taxi. Both after captures must agree before the final change report exists. If any step fails, preserve the failed attempt, use a new prefix and investigate before retrying. Never overwrite the baseline or substitute another host. The helper does not guarantee an atomic file-system snapshot. The manual fallback remains documented in the Update Helper README.

### P1 — Taxi-specific evidence admission and offline checks

```powershell
Set-Location -LiteralPath 'C:\work\Rift_Taxi'
python -B -m rift_taxi.patch_check --run-id post-20261124-01 --expected-host LEGION --before '../Update Helper/before-20261124-legion.json' --expected-before-sha 6612cab5ad31162cc0eab21266ed3839c4a2ef1e12e3a2aa82536d5b195c983e --minimum-tests 466 --after-a '../Update Helper/patch-20261124-attempt-01-after-a.json' --after-b '../Update Helper/patch-20261124-attempt-01-after-b.json'
if ($LASTEXITCODE -ne 0) { throw 'Taxi offline postcheck blocked; inspect receipt' }
```

The runner saves the gate result, original manifest copies, Git/doctor/test logs and final receipt in `artifacts/patch-check-post-20261124-01/`. Use the same explicit cycle prefix as P0, and a new Taxi run ID for retries. Compare the manifest hashes in the Taxi receipt with the independently verified P0 bundle. Omit both after arguments only for a pre-patch check. Exit 2 means validation blocked; exit 0 means **offline checks passed only**. A missing receipt, pending file, or blocked status is not success. It never authorizes live game input. The gate checks declared capture intervals, distinct file identities, stable reads, canonical local Windows paths and inventory consistency; it does not cryptographically authenticate the producer or prove the scanner actually ran twice. Run the capture steps independently and retain the original bytes. The commands above are fail-fast; do not ignore exceptions or continue to P1 after an unstable comparison.

| Gate output | Recovery decision |
|---|---|
| `baseline-only` | No post-patch evidence yet. Preserve baseline. |
| `executable-changed` | Treat prior exact-build client evidence as historical; keep production disarmed. Record compatibility as unqualified. |
| `other-files-changed` | Preserve changed-file inventory; require independent map/route and interface compatibility review as applicable. |
| `no-content-change` | No content changes observed in the captured scope; still require fresh process/session evidence. Not proof that no server-side update occurred. |
| Exit 2 | Invalid, unstable, duplicated, or mismatched evidence. Do not proceed. |

If changed files affect map assets, retain the source manifest and consult the independently maintained RiftWorld packages rather than copying or rewriting their pipeline. Report addon compatibility separately; the game-install capture does not prove installed addon behavior.

### P2 — release decision

Keep the current M1 qualification boundary. Only fresh, separately authorized evidence may establish current client/actor/zone, observation freshness, heading, release and map qualification. A passing test suite or unchanged executable does not qualify these. Never auto-arm after a patch, restart, crash or stale observation. Continue offline geometry, simulation, integrity and packaging work even when the live compatibility gate is blocked.

## 4. Handoff requirements

Record machine, Git HEAD, patch timestamps, original manifest hashes, changes by class, offline test exit/count, outstanding qualification blockers and whether any live observation actually occurred. Preserve the distinction between pre-patch evidence, post-patch evidence, synthetic fixtures and actual verified behavior. Mark M1 incomplete until its existing acceptance requirements are met. No sibling writes or automatic game updates from this workflow.

## 5. November 24 current-install recovery receipt (12:30–12:38 EST)

**Disposition: offline recovery passed; no game installation content change; live M1 remains unqualified.** The publisher's actual patch/maintenance status was not independently established. This is a current-install comparison against the original before manifest, not evidence that a new build was delivered.

- Host: LEGION. Taxi tested HEAD: `792e62a3b6055c81ef8513dd766af0e39e0a775a` (clean committed checkout throughout the check); Python 3.14.10.
- Update Helper: 35/35 tests passed (1.210 s); original baseline pin verified by the capture cycle and independent bundle verifier.
- Fresh two-pass capture: `taxi-20261124-current-01`, 12:30:26–12:33:11 EST. Both captures agreed; 266 unchanged, 0 added, 0 removed, 0 modified. Executable SHA unchanged. Independent `verify_cycle.py` completed exit 0.
- Taxi `patch_check`: `post-20261124-current-01`, 12:33:29–12:34:44 EST; `offline-postcheck-passed`, `no-content-change`, doctor exit 0 and **466/466 tests passed in 73.946 s**. The wrong-pin message in stderr is expected from a negative test; unittest reported OK.
- No movement, focus change, restart, installation/addon change, or live native pose acquisition was performed. Production input and live compatibility remain explicitly false.

| Original evidence (local ignored files; not included in Git) | SHA-256 |
|---|---|
| Update Helper `before-20261124-legion.json` | `6612cab5ad31162cc0eab21266ed3839c4a2ef1e12e3a2aa82536d5b195c983e` |
| Update Helper `taxi-20261124-current-01-after-a.json` | `16d1d64d611192a90ebc5fddcb22093af646024c8b3a731dd1b63eafae6e237f` |
| Update Helper `taxi-20261124-current-01-after-b.json` | `110524bcbc3a4526ac324f709e4dd39585278794e013901be4e0b2aaf0a67961` |
| Update Helper `taxi-20261124-current-01-consistency.json` | `fba57e97eab4b337fd4b398937f64e16f06318f396563283988712f5e1a9fbc0` |
| Update Helper `taxi-20261124-current-01-changes.json` | `a80f1992a40d50ff6a542eb47d8e7b6dabdea755464299780977aecdfb270c1f` |
| Taxi `artifacts/patch-check-post-20261124-current-01/receipt.json` | `14211fb8c29258d798f9b782554ff987b0ec67772ead66a81c124b6a0f60d6b6` |
| Taxi same folder `evidence.json` | `d7d66c258fc2d2c59eca64c6953f90a2984004b6944029884b0ea0c9ca1397e3` |
| Taxi same folder `tests.stderr.txt` | `3c5acb232ea0df8721f52c9e90e275b76f0142826198d648c150ccdd9adfcc79` |

### P2 read-only OS identity follow-up (12:38 EST)

The current RIFT process was present and responding, with the same Windows session (2) as the diagnostic. Initial Taxi OS identity inspection refused unpinned window selection; a second attempt with the independently observed main HWND refused the pinned window. Independent Win32 metadata established that HWND 395576 belonged to PID 33052, was valid and visible, unowned, and **minimized** (`IsIconic=true`); Taxi correctly returned no eligible window. These PID/HWND values are historical observations only. Both identity attempts exited 2 as intended; the independent metadata diagnostic exited 0. Do not relax the non-minimized window contract or infer a build failure from this result.

| Local original diagnostic | SHA-256 |
|---|---|
| `artifacts/patch-os-identity-20261124-current-01.json` | `2af965c0222ef1d2fba0cb4abe271894b9adcca618f5fe9e05168524f361c4fa` |
| `artifacts/patch-os-identity-20261124-current-02.json` | `f56f957116d71a46306d8ecd6337705ab34242b1ef0f7b7cdffd2db4b55060bf` |
| `artifacts/patch-window-diagnostic-20261124-current-01.json` | `4283bc674b8c53b819de23af3b248a7c892d58f122583a14f1cd3ff123cfa8f8` |

**Resume:** If actual installation content changes later, create a new capture prefix and Taxi run ID, preserving these originals. Otherwise continue M1 offline work or obtain fresh non-minimized process/window identity when the game is available for observation. Keep actor/zone, heading, freshness and movement gates unqualified; no automatic re-arm.
