# Independent factorial archive audit — November 24, 2026

Base: `2e0a8cf65ea6345bf1b82c8b76ecf367260f7b94`. This is a proposed offline evidence-integrity improvement, not a new controller or a new physical experiment.

## Verification performed

The standalone auditor and analytic fixture passed all three focused unittest methods (including nine corruption subcases) on the isolated Linux Python 3.13 environment. The two GitHub file blob hashes were independently matched to the locally tested source:

- `rift_taxi/delay_factorial_audit.py`: `372abc14adca7e1c70f9719fb8d779bc4d0672c3`
- `tests/test_delay_factorial_audit.py`: `17dd5b32ac161590661f5b333101b04ea4af3619`

No full checkout was available to the isolated environment because direct GitHub DNS resolution failed. The original ignored LEGION archive was not available. Do not report a new integrated regression baseline or a successful original archive audit yet.

## Acceptance on the repository checkout

Run from the root in PowerShell after fetching the review branch:

```powershell
python -B -m unittest discover -s tests -p test_delay_factorial_audit.py -v
python -B -m rift_taxi.delay_factorial_audit artifacts/m2-m3-delay-factorial-20261124-1326.json --sha256 83c749b68236c62a8a3e85c94f9349016298eb3e53e2b9cd6971b18cc81cb65f
python -B -m unittest discover -s tests -v
```

The trusted archive hash is from M2_M3_DELAY_FACTORIAL_2026-11-24.md. A digest match authenticates identity relative to that recorded receipt; internal consistency checks do not independently reconstruct every trajectory, geometry or source trace. Retain the original evidence unchanged.

Before merging, review schema coverage and verify the original 864-case archive and integrated tests. The next steering study remains separate. Production navigation and all physical qualification flags remain unchanged.

## Online environment follow-up

Added .github/workflows/offline-regression.yml: GitHub-hosted Windows and Ubuntu, Python 3.14, read-only repository permissions and no game dependency. Workflow execution is not yet confirmed; do not count it as passing.

The auditor now rejects duplicate JSON keys, nonfinite numbers (including overflowing exponents), and booleans used as numeric case IDs, factors, duty or terminal measurements. Five isolated Python 3.13.5 tests passed, including sixteen corruption subcases, and the updated remote blobs match the locally tested files exactly:

- Auditor: `57ddf5e19c2fbbb043845b5dedec08898457ae02`
- Tests: `99a8e30111f2b75ce1b9363f86fa66f5bb0e4a46`

Full integrated acceptance and the original archived report remain pending. Main and frozen synthetic policies are unchanged. Direct Git DNS remains unavailable in the Linux execution environment; use the GitHub connector and hosted CI where supported.

## Hosted regression and diagnostic evidence

GitHub Actions run 45540802854, head d16632b: Windows 503/503 (46.282 s), Ubuntu 487 passed and 16 skipped (21.526 s). Run 45541077013, head 576dcb2, base 2e0a8cf: Windows 507/507 (34.987 s); Ubuntu 489 passed, 2 failed, 16 skipped (21.650 s). Windows checkout log confirms synthetic PR merge b0ce121 with the expected head and base. Both platforms generated and audited the complete 864-case study and reconciled these route-level counts.

| Route | Approach losses at 330 ms | Arrived but unsettled | Total settling losses |
|---|---:|---:|---:|
| double-crossing | 13 | 6 | 19 |
| narrow-return | 12 | 5 | 17 |
| mixed-angle-fan | 0 | 10 | 10 |
| short-leg-staircase | 0 | 7 | 7 |
| translated-curve | 0 | 7 | 7 |
| short-terminal-leg | 0 | 3 | 3 |
| Total | 25 | 38 | 63 |

Zero and 110 ms: all 288 approach and settling outcomes successful. At 330 ms: 263 arrivals, 225 settled, 32 arrival-plus-duty successes. These counts match the historical study, but small platform-specific floating-point differences occur in terminal error values; do not claim cross-platform byte identity. For duty success, zero delay has 104, 110 ms has 89 (15 gains, 30 losses), 330 ms has 32 (16 gains, 88 losses), all compared to zero delay. All observed geometric losses concentrate in two route shapes. Original ignored LEGION archive still unavailable; generated report SHA validation is not a substitute for historical archive verification.

## Cross-platform test defect

The two failing Ubuntu tests in run 45541077013 are existing mocked crash-release tests. Their synthetic marker is at 100.03 monotonic seconds, but the fixture uses the real host monotonic clock to judge whether that marker is in the past. A newly started host can violate that assumption. Commit aa2d037 pins the mocked clock to a deterministic advancing epoch beginning at 500 seconds, independent of uptime; production behavior is unchanged. This is a proposed fixture correction pending hosted rerun, not confirmation of a physical release event. Keep PR draft pending acceptance.

Evidence: https://github.com/360madden/Rift_Taxi/actions/runs/45541077013

## Model contract and bounded archive follow-up

Source review: simulation.py, simulation_settling.py and simulation_delay_factorial.py. The ideal plant observes current synthetic pose, delays only command application in a stationary-initialized FIFO of 0–10 whole steps, and uses midpoint planar integration. No sensor lag or physical actuator is represented. The matched dt=55/110 ms and delay=0/110/330 ms correspond to integer queues 0/2/6 and 0/1/3 respectively. Geometric arrival requires endpoint distance and remaining arc both within tolerance plus all ordered sharp gates passed; cross-track rejection precedes arrival. Terminal settling is separate passive FIFO drain and one stationary interval, not active correction. Forward duty is modeled positive applied velocity time divided by elapsed approach time, with a 40 s factorial approach budget; it excludes the post-arrival drain and is not key duty.

Comparison contract: pair by geometryCase, speed, maxYawRate, dt, and delay; record geometricArrival, settledWithinTolerance, arrivalAndDutyTarget, terminal status and final/settled error separately. Gains and losses must both be retained; never discard failed approaches or assign them terminal observations. Preserve all original report and policy identities. No live input, collision, safe traversal or physical qualification claim follows from these simulations.

Commits 94653fc, fb876ec and 170cbc5 add a shared digest-verified strict parser, an 8 MiB bounded read (original report 667,969 bytes), top-level object and nesting rejection, and CLI/error-path tests. This is an engineering limit chosen for current report size, not a simulator constraint. Three new test methods bring the prospective discovery count to 510; hosted confirmation remains pending. The original archive is still unavailable.

## Cross-platform reproducibility follow-up

Run 45546590286 (aa2d037) completed successfully: Windows 507/507 in 50.375 s; Ubuntu 491 passed, 16 skipped in 35.214 s. Independently parsed the diagnostic JSON from both job logs: all discrete outcomes across 12 route/delay groups match exactly. The maximum absolute difference in the 12 maximum-settled-error measurements is 5.717648576819556e-15 synthetic units. This is aggregate diagnostic equivalence, not a per-case trajectory comparison or byte-identical archive reproduction.

Run 45546766551 (ed17b2c): Ubuntu 494 passed, 16 skipped, 21.150 s; Windows pending at observation. The archive size, non-object/deep JSON, and both CLI error/success tests therefore have verified Linux execution. Four additional test methods are committed at c48bec2 and 2e8e7a8: deterministic diagnostic case ordering, all-failure report, matched gains/losses that cancel in marginal counts, and unknown schema with correct digest. Prospective discovery count is 514; no pass claim until hosted execution.

## Route-factor stratification checkpoint

Hosted run 45546919255 at head 3828af4: Windows 514/514 (39.941 s); Ubuntu 498 passed, 16 skipped (19.729 s). Both succeeded. This validates the preceding four new tests and bounded archive changes. Source blobs for simulation.py (5294c221193e18f067856857428549ebbcac5050), simulation_settling.py (52a5f2082fd07502a77bbb6a876486e2566dc894), simulation_delay_factorial.py (b26999c0de6671d7029abb30cf394675ba1b90ea), and simulation_holdout_v3.py (60871fc94ab3c17d0cc8d3154e65d46d3939882e) independently match base 2e0a8cf.

Commits ca637e6, 0739369 and 92e8603 introduce a separate descriptive stratification command: route-specific matched effects for speed, yaw cap and timestep; binary outcome histories across three delays; and min/median/max terminal errors with failed-approach denominators. The four new tests (three analytic, one actual-grid reconciliation) are committed but not yet verified by hosted CI. Prospective discovery count: 518. Keep the historical archive and controller unchanged. The analysis is descriptive, not an independent holdout or a physical performance claim.

Usage (from repo root):
```powershell
python -B -m rift_taxi.delay_factorial_stratification artifacts/m2-m3-delay-factorial-20261124-1326.json --sha256 83c749b68236c62a8a3e85c94f9349016298eb3e53e2b9cd6971b18cc81cb65f
```
The original file remains unavailable; above is a future verification command, not an execution receipt.

## Route-stratification results and next research priority

Hosted run 45547058953 at head 92e8603: Ubuntu discovered 518 tests, 502 passed and 16 skipped in 35.612 s. Windows was still running at initial review. All six route strata reconcile to the original 864-case study. Matched changes at 330 ms (low to high factor value, gains/losses):

| Route | Speed arrival | Speed settled | Yaw arrival | Yaw settled | dt arrival | dt settled |
|---|---:|---:|---:|---:|---:|---:|
| double-crossing | 0/11 | 5/10 | 0/13 | 4/13 | 0/1 | 0/5 |
| narrow-return | 0/12 | 0/13 | 0/12 | 0/11 | 0/0 | 0/3 |
| mixed-angle-fan | 0/0 | 5/5 | 0/0 | 5/5 | 0/0 | 0/8 |
| short-leg-staircase | 0/0 | 2/5 | 0/0 | 0/5 | 0/0 | 3/4 |
| short-terminal-leg | 0/0 | 3/0 | 0/0 | 0/3 | 0/0 | 1/2 |
| translated-curve | 0/0 | 0/7 | 0/0 | 0/5 | 0/0 | 0/7 |

Terminal distributions at 330 ms, conditional on geometric arrival:

| Route | Arrivals / 48 | Min | Median | Max | Outside tolerance |
|---|---:|---:|---:|---:|---:|
| double-crossing | 35 | .059563 | .198077 | .406516 | 6 |
| narrow-return | 36 | .049080 | .218367 | .372131 | 5 |
| mixed-angle-fan | 48 | .095572 | .182495 | .444542 | 10 |
| short-leg-staircase | 48 | .080966 | .210559 | .474761 | 7 |
| short-terminal-leg | 48 | .040119 | .165944 | .332633 | 3 |
| translated-curve | 48 | .049575 | .184857 | .412727 | 7 |

The three-delay geometric and settled histories are exclusively 110 and 111. The combined arrival/duty outcome is not monotone: eleven short-terminal-leg cases have 010 (succeed only at 110 ms), four have 011, five have 001, and seven narrow-return cases have 001. All double-crossing cases have 000 for the combined objective even at zero delay. These observations argue against treating delay as the only cause or choosing a universal faster/slower profile from marginal counts. Prioritize separate approach and terminal studies, retain all failed starts, and evaluate independent geometry before making any generalization. This is descriptive analysis of observed synthetic cases, not a new steering policy, physical calibration, or live qualification.

## V4 prespecified holdout design

Windows run 45547058953 subsequently completed 518/518 in 28.343 s. Both platforms are green for the stratification checkpoint.

Commit d31c7ae fixes six new authored synthetic geometries, two perpendicular initial offsets, three heading offsets, and two new coupled speed/yaw/dt profiles. Three matched nominal delay levels (0, 120 and 360 ms) give 216 intended runs across 72 scenario identities. Commit d693df4 adds two design-only regression tests; prospective discovery count 520, hosted confirmation pending. The generator returns scenario specifications, not outcomes. No V4 simulations have been run by these additions. Freeze a candidate and its matched comparison protocol before evaluating this set; once inspected, treat the set as observed and preserve it unchanged. New authored geometry is separate from V1–V3 but not an independent external physical dataset. Existing simulation code and prior reports are unchanged.

Future results must distinguish geometric arrival, terminal settling and forward duty, preserve failed starts, and report matched gains/losses rather than relying on marginal success. The historical LEGION archive remains unavailable. No production qualification or merge claim.
