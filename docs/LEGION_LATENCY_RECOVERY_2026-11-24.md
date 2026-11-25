# LEGION recovery and synthetic latency experiment — November 24, 2026 PST

Branch: `research/legion-latency-reconcile`. RIFT unavailable; all work offline. Production navigation remains disarmed.

## Recovery

Preserved original interrupted work at local commit `499755c5d0fdcb692a822975f7248e0894a8570e` on `recovery/legion-latency-original-20261124`. Fast-forwarded main by 82 commits to `134b7c716f5788c111d19aaf8013ee0c574e9bee`; cherry-picked original experiment without conflict at `cd9d5927e7b5cce5013f595b1ee7a7d968dc6b60`. Existing 545 tests passed on that checkpoint. PR #4 hosted run 45556467198 verified the installed journey CLI and 545 Windows tests.

Both historical factorial reports `artifacts/m2-m3-delay-factorial-20261124-1326.json` and `artifacts/m2-m3-delay-factorial-20261124-1327-recheck.json` match the previously documented 667969-byte SHA-256 `83c749b68236c62a8a3e85c94f9349016298eb3e53e2b9cd6971b18cc81cb65f`. The standalone archive auditor passed both (864 cases, 24 profiles, 9 matched effects); originals remain ignored and unchanged. Sister checkouts inspected read-only: RR2 229fb5ba, RiftWorld 233e1bb4 (two local commits ahead of tracked remote), Telara Fly 41aacc04; all clean. Only Telara Fly identity independently matched the historical Taxi reference. Do not claim historical unchanged identity for other repos.

## Experimental results

Original V1 report: `artifacts/legion-latency-reconcile-20261124.json`, 2136814 bytes, SHA-256 `8ff223b8f06dedd746c24b37afe8d0127f8c476ee35c8c800e38e422ed89eb05`. V1 exact prediction of queued synthetic motion produced a near-endpoint progress deadlock on short-terminal-leg case 32 (dt 0.11 s, speed 3.4, yaw cap 65, one step delay). Position error 1.19e-9, final progress 14.39556 versus required 14.4, status lookahead-degenerate. No evidence of failure in a physical client.

V2 adds a local projected-arc rejoin when the observed and predicted positions are near the final goal but the admitted arc remains outside tolerance. All sharp gates must be passed; actual displacement alone earns progress. Chord-bound velocity is used during rejoin instead of braking to the already-near endpoint. It remains opt-in, and zero-delay results remain unchanged.

V2 report: `artifacts/legion-latency-terminal-rejoin-v2-20261124.json`, 2136777 bytes, SHA-256 `ac2a205c12a75c18ab1caca7d77f5a38bdb8d48c15b76896bbbee8fd887993da`. All baseline outcomes equal original report's baseline.

| Observed set | Baseline settled | V1 settled | V2 settled | Baseline / V1 / V2 arrival + >=95% duty |
|---|---:|---:|---:|---:|
| V3 (216) | 191 | 216 | 216 | 60 / 63 / 60 |
| Factorial (864) | 801 | 863 | 864 | 225 / 259 / 252 |

V2 restores the one lost factorial arrival but loses seven V1 duty successes; versus original baseline, factorial high-duty gains 54 and losses 27. V3 and factorial overlap; do not sum counts as independent evidence. Five focused regressions passed. Do not change the default controller.

## New geometry smoke (not blinded)

New hand-authored geometry smoke, 24 matched pairs, generated after V2: `artifacts/legion-latency-new-geometry-smoke-20261124.json`, SHA-256 `cb52fcdfbad2324900a5bc84d4504cd195ffd4d685fa9c8723824cac6a319165`. For reproduction: all Y=0, initial XYZ (0,0,-0.4), initial yaw +/-35 deg, dt .11, speed 3.4, yaw cap 65, budget 40 s, delay steps 0/1/3, ordered policy, generator taxi-legion-novel-smoke-20261124. XZ routes:

- oblique-stair: (0,0), (3,1), (4,4), (7,6), (9,6)
- wide-s: (0,0), (3,2), (6,2), (9,-1), (12,-1)
- narrow-return: (0,0), (6,0), (6,1.4), (1,1.4), (1,4)
- short-offset-finish: (0,0), (4,0), (7,3), (7,3.5), (7.6,3.5)

Both controllers arrived in 24/24, baseline settled 21/24 vs candidate 24/24, zero lost baseline settled arrivals. High-duty counts 19 vs 15. Every trajectory and ordered drain was checked. These are small new model-only smoke cases, not statistical validation. Preserve all negative outcomes. Next: narrow unnecessary terminal rejoin or improve duty without loosening progress or arrival rules, and run a separate fixed-design holdout.

Reproduce from Taxi root (new output file required):
```powershell
python -B -m rift_taxi compare-latency-prediction --out artifacts\NEW.json
python -B -m unittest discover -s tests -p test_simulation_latency_prediction.py -v
python -B -m unittest discover -s tests -q
```

Full LEGION regression: 550/550 passed in 57.448 s, exit 0. Git diff --check passed.
