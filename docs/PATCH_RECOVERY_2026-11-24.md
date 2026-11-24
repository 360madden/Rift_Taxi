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
