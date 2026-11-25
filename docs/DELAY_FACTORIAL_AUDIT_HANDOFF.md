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
