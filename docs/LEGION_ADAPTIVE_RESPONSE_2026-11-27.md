# November 26–27, 2026 — adaptive synthetic response estimation

Host LEGION; base commit b3fe17c. Offline research only. No production policy promotion, physical RIFT observation, game process interaction, or game input.

## Implementation and evidence boundaries

The new `synthetic_response_estimator.py` fits a whole-step command delay (0–10) and independent velocity/yaw gains (.5–1.5) using a rolling window of up to 48 consecutive-pose increments. It excludes multi-step observation gaps, uses immutable capture and delivery epochs, and uses only commands already issued by delivery time. Both channels require excitation. The candidate delay must be distinguishable from competing hypotheses, with bounded normalized residual and a minimum separation. The model is refit every four accepted increments, and an old qualified fit expires after 96 model ticks (6 seconds) to the nominal 3-step/unit-gain fallback. A qualified fit is an estimator classification, not verified physical pose or future response.

The existing sampled closed loop now has an opt-in adaptive predictor that starts nominally, accepts only the same controller-admitted samples, and uses the learned parameters solely for forecast. Actual model state, observed route progress, sharp passage witnesses, stale-pose expiry and terminal settled-arrival gates remain separate. The report checker reconstructs the estimator feed from delivered source poses and the prior command history, verifies per-frame estimates and forecasts, and checks the actual FIFO and zero-command witness. The separate plant supports one hidden response-gain change at a specified application tick (including pending commands at terminal drain). The command delay remains fixed per run.

## Frozen comparison

The prior 144-condition combined uncertainty design is explicitly a development replay. The new authored 192-condition design crosses two longer geometries, two speeds, three command delays (0/4/8 steps of 62.5 ms), four gain profiles (unit, cross-gain, slow-to-fast, fast-to-slow), and four delivery schedules. Changing gain profiles switch at tick 64 (4 seconds), without warning the controller. A total of 336 matched conditions / 672 runs compares the nominal predictor with the adaptive predictor. The nominal predictor is fixed at three steps and unit gains. The prespecified research screen requires no settled losses, every scheduled long-dropout case to expire, and lower mean matched duration. No thresholds were adjusted after observing this study.

| Cohort | Usable cases | Nominal settled | Adaptive settled | Common-success time, nominal / adaptive | Adaptive dropout expiries |
| --- | ---: | ---: | ---: | --- | ---: |
| Prior development | 108 | 108 | 108 | 10.7431 / 9.6435 s | 36/36 |
| New fixed/changing | 144 | 123 | 144 | 18.9502 / 15.2165 s | 48/48 |

All 21 gains occurred at eight-step actual delay (27/48 nominal vs 48/48 adaptive); all 48 cases at each of zero and four steps settled under both policies. New gain-profile nominal/adaptive arrivals: unit 30/36 vs 36/36, cross-gain 31/36 vs 36/36, slow-to-fast 26/36 vs 36/36, fast-to-slow 36/36 vs 36/36. Both cohorts passed the research screen. New matched mean duration fell by 19.70%, while mean forward duty was .95365 nominal vs .94876 adaptive. Five new common successes were slower under adaptive prediction; the largest slowdown was .25 s. Preserve these tradeoffs.

## Estimator accuracy and limitations

All 108 prior usable runs and all 144 new usable runs obtained an accurate fit at some point. In the new cohort, 33,889/35,633 approach frames carried a qualified estimate (95.11% coverage). Of those, 30,425/33,889 matched actual delay and both gains within .05 (89.78% conditional accuracy); estimated delay alone matched in 99.988% of qualified frames. There were 3,464 inaccurate qualified frames. Mean time to the first accurate estimate was .75694 s. All 72 usable cases reaching the hidden gain change eventually reacquired an accurate model, in 2.5–3.125 s (median 3.0625, mean 3.00694). The old fit can remain qualified during a change; do not equate model confidence with current truth. The prior fixed cohort had 15,068/15,068 accurate qualified frames.

This is a deterministic, ideal planar model, not a real-game latency calibration. No noise, inertia, collision, variable command delay, physical release or native-pose freshness was modeled. Authored new geometry is not a statistical validation population. Next investigate measurement noise, change detection and a shorter bounded stale-fit policy on a separately fixed design, then prioritize actual M1 qualification before a controller promotion.

## Reproduction and hashes

```powershell
python -B -m rift_taxi.synthetic_adaptive_study --summary --out artifacts/NEW-adaptive-study.json
python -B -m unittest discover -s tests -p test_synthetic_response_estimator.py -v
python -B -m unittest discover -s tests -p test_synthetic_adaptive_study.py -v
```

The two completed study reports (`artifacts/legion-adaptive-study-20261126-01.json` and `-02.json`) match byte-for-byte, 824,621 bytes, SHA-256 `598384cca32c2af877f159d61f4c72beff77d26df9c974dae37577bf5529e9c9`. The prior combined report regenerated identically (`artifacts/legion-combined-after-adaptive-20261126.json`, SHA-256 `753b70c6ee1fa0bd21a15af1cedb79196d8237b4da874ac021783e5259a2fe6e`). A separate comparison of the old report verified all 144 prior nominal outcomes, STOP records and admission counts exactly. Full LEGION regression suite passed 606/606 in 96.495 seconds (exit 0); the baseline-byte-hash rejection is expected negative-test output. Fourteen focused tests passed; an initial failing coverage test used the wrong tuple indices, corrected in the test only, and reran successfully.

Source SHA-256: estimator `d3456553e8256dcc45cfbe6fbb45e1fe7ddbcfa4c28769745432477e9c372cb6`; sampled controller `4ddd011b3e026fe7ebdf92310ac449cad8da932a381323a371ff4bb3dfafb051`; study `1d9b9d188bf7e71a42dcf0926ce77e29493f773f5709c1c6852d4eb52417bcf2`. Reports remain local ignored artifacts.
