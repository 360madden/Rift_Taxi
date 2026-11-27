# November 26, 2026 — LEGION recovery and journey benchmark

## Current installation and recovery
- Machine: LEGION; repository C:\work\Rift_Taxi; recovery tested at 7323d03c6d5b400cac13e43b3552ee2c1cb8d46d.
- Update Helper's existing November 26 two-pass capture, prefix `riftworld-20261126-01`, was independently checked using `verify_cycle.py` with the pre-patch manifest SHA-256 pin. All 266 files (26,754,214,661 bytes) were unchanged. Current on-disk executable hash also matched independently.
- Before manifest: `6612cab5ad31162cc0eab21266ed3839c4a2ef1e12e3a2aa82536d5b195c983e`.
- After A/B: `a4331e85bc7a4a84c421368daf09bfbf4208ee7ffb793b5816a48fbcd7b2742c`, `cdb069503995eae000b5f8c69e0d4073b26f5956220e6c5a4fb00521d27f4c84`.
- Executable SHA-256: `df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01`; no build profile revision justified by this inventory.
- Taxi postcheck receipt: `artifacts/patch-check-post-20261126-shared-cycle-01/receipt.json`, SHA-256 `a82b6d70cc97ac14a8fb718a7f011ef578b63e862bb81dda6a7e52a660e924b7`. Doctor and 559 tests passed; independent stored-receipt verifier validated 29 files. These are local original evidence files, not Git-tracked artifacts.
- Fresh read-only Windows identity inspection found PID 15076, start ticks 639312735157524276, HWND 1443934, valid pinned build and non-foreground window. Historical identifiers only; re-discover the active session before any new observation. No game memory acquisition, focus change, game input, restart, or live compatibility promotion.

## Repeatable standalone journey comparison

Run from the Taxi repository root (Python 3.11+):

```powershell
python -B -m rift_taxi.synthetic_journey_batch --summary --out artifacts/NEW-journey-batch.json
python -B -m unittest discover -s tests -p test_synthetic_journey_batch.py -v
```

The CLI reconstructs the documented November 24 fixed smoke design (four routes, two initial headings, two coupled model profiles, three command-delay levels). It runs all 48 cases, with baseline and only eligible experimental modes, for 128 complete synthetic journeys. It retains individual compact outcomes, distinct case hashes covering scenario and model parameters, explicit modeled bounds, matched settled gains/losses, and common-success means for total time and forward duty. The compact console summary does not remove case rows from the saved report. Output creation is exclusive. It uses existing Taxi-owned synthetic code and no external runtime dependencies.

| Mode | Matched cases | Baseline settled | Candidate settled | Gains/losses | Common-success mean total time (baseline/candidate) | Common-success forward duty (baseline/candidate) |
| --- | ---: | ---: | ---: | --- | --- | --- |
| Zero-delay rejoin | 16 | 12 | 16 | +4 / 0 | 4.4833 / 4.4833 s | .95577 / .95577 |
| Near-goal prediction | 32 | 30 | 32 | +2 / 0 | 6.7640 / 6.3413 s | .88366 / .88714 |
| Near-stall prediction | 32 | 30 | 32 | +2 / 0 | 6.7640 / 5.7680 s | .88366 / .91924 |

Reproduction: original fixed-smoke archive SHA-256 `7f25b693911db7c824f48a8996eda8de2e7e4727e4f5450062f54fe85d6bc90e` and November 25 complete-journey archive SHA-256 `dd75e75be12a1fc04c8a797379d98bc04b666f5090dc1bee4836533ab6a9d9ec` independently match their documented pins. All 48 original scenario/profile/delay identities and all 128 historical compact journey outcomes were compared and matched exactly. Two CLI runs produced byte-identical files `artifacts/legion-journey-batch-20261126-01.json` and `artifacts/legion-journey-batch-20261126-02.json` (167,613 bytes; SHA-256 `df6e33ad5a4dc65f808991b6ec6aadd0024f47f8bb5eb5ac7e5ae0423f6491c1`). All five focused tests passed. The complete LEGION regression suite subsequently passed all 564 tests in 81.771 seconds (exit 0).

This is repeatable evidence on already-observed geometry, not an unseen holdout, a new live route, or a reason to promote the experimental controller. Production navigation remains disarmed. The next offline study should prespecify mismatched observation/command timing and independent geometry before evaluating a candidate. Resume live qualification only from a freshly verified, eligible physical session.
