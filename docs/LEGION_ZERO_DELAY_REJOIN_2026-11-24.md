# Zero-delay terminal progress recovery and journey integration — November 24, 2026 PST

PR #6 merged at db161f0 after successful hosted run 45562821038. LEGION main synchronized; this work is separate from the frozen V2/V3 prediction experiments.

## Root cause and opt-in policy

All four short-final-z zero-delay failures from the prior 48-case smoke were independently reproduced: final XZ error below 1e-9 units, progress approximately 11.018–11.029 on an 11.35-unit route, below the required 11.05. The baseline brakes toward the coincident endpoint before earning sufficient observed progress. Separate zero-delay recovery applies a local admitted-arc rejoin only when ordered sharp gates are already satisfied, the target is the endpoint, progress is short and actual endpoint error is at most one tenth of tolerance. This uses the existing displacement and arrival gates without forecast, progress assignment or tolerance relaxation.

The frozen controller defaults and comparison modes are unchanged. Direct recovery is explicit, zero-delay and ordered-policy only. The standalone synthetic journey supports baseline, predict-near-goal, predict-near-stall and zero-delay-rejoin; prediction modes require nonzero delay and zero-delay recovery refuses nonzero delay. Approach failure cannot be converted to terminal success. No physical input or qualification.

## Evidence

- Original 16 zero-delay cases from the 48-case smoke: 12/16 settled before vs 16/16 after, 9 high-duty arrivals in each. All four previously failed cases recover; observed approach durations 9.36 -> 6.32 seconds (dt .08), 7.56 -> 5.04 seconds (dt .12). Exploratory report `artifacts/legion-zero-delay-rejoin-trial-20261124.json` SHA-256 `8e51ed14d0e0ae6581d8ee6a36604a4576f6c8dd33d4fcdd966e23102a384713`. Four direct journey regression subcases reproduce the failure and verify correction.
- Observed V3 zero-delay 72/72 and factorial zero-delay 288/288 settled, high-duty 26/72 and 104/288 respectively, unchanged; zero rejoin activations. Observed groups overlap. Report `artifacts/legion-zero-delay-observed-comparison-20261124.json` SHA-256 `d667e956bf3acbb8fb0db55c8b602a0f702d69456b2702ecab08354cdcebfc09`.
- All four actual source-checkout journey CLI invocations with synthetic_continuous.json returned model-settled. Baseline (two-step delay) total 6.6 s, prediction modes (two-step delay) 6.9 s, zero-delay rejoin 5.8 s (different delay, not a fair speed comparison). Final XZ errors .1982/.1585/.1585/.2846 synthetic units. Reports are retained separately in ignored artifacts.
- Four new regression methods, 14 journey-focused tests passed. Hosted wheel workflow now explicitly exercises all three experimental modes from the installed package outside the source tree; acceptance awaits CI.

Reproduce using new output paths:

```powershell
python -B -m rift_taxi.synthetic_journey_demo samples/synthetic_continuous.json --approach-mode predict-near-stall --delay-steps 2 --out artifacts/NEW.json
python -B -m rift_taxi.synthetic_journey_demo samples/synthetic_continuous.json --approach-mode zero-delay-rejoin --out artifacts/NEW_ZERO.json
python -B -m unittest discover -s tests -p "test_synthetic_journey*.py" -v
```

Next: preserve these negative controls, compare new geometries with delay mismatch and jitter in a separate ideal-model study, and improve standalone reporting. Default navigation remains disarmed; live RIFT qualification still pending.

Full LEGION regression: 556/556 passed in 69.725 s, exit 0.
