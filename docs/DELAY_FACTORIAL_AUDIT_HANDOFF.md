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
