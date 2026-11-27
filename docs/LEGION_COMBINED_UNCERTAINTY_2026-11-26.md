# November 26, 2026 — combined observation and actuator uncertainty

Host LEGION; starting commit d4ab88d. This work extends the separate synthetic sampled-steering experiment, not the production controller or its live qualification.

## Implementation

The simulated actuator now has independently declared actual command-delay steps and constant velocity/yaw-response multipliers. The predictive controller receives only its assumed delay and response multipliers, its own past requests, and delivered immutable observations. Actual plant movement and terminal queue drain apply the actual multipliers. Neither estimated position nor privileged plant truth earns source-observed route progress. The independent consistency verifier reconstructs actual FIFO integration and estimated-model forecasts separately; it rejects altered declarations, out-of-range parameters and inconsistent motion. Legacy unit-gain matched-delay reports remain unchanged.

The new `rift_taxi.synthetic_combined_uncertainty` study fixes two authored geometries, two speeds, three actual command delays (1/3/5 steps at 62.5 ms), three response profiles (unit, .85 velocity/.75 yaw, 1.15 velocity/1.25 yaw), and four observation schedules (steady delay, in-order jitter, short dropout, long dropout). This yields 144 matched conditions and 432 total runs. The nominal predictor always assumes three command steps and unit gains, irrespective of actual conditions. The exact-model reference receives actual parameters only as an information-advantaged comparator. The held-pose baseline has no predictor. All three share route admission, STOP, and terminal criteria.

## Results

| Policy | Settled with usable telemetry (108) | Mean duration, 92 common successes | Mean forward duty, 92 common successes |
| --- | ---: | ---: | ---: |
| Held pose | 92 | 11.5713 s | .91017 |
| Nominal prediction | 108 | 10.4823 s | .93258 |
| Exact-model reference | 108 | 9.4823 s | .92393 |

Both predictive variants recovered all 16 baseline failures without losing an existing success. The failures were eleven observed arrivals that did not settle inside tolerance and five approach timeouts. All 108 long-dropout runs (36 per policy) terminated with observation expiry and no settled-arrival claim. All gains occurred at five-step actual delay: unit response 6/12 baseline versus 12/12 both predictors, slow response 9/12 versus 12/12, fast response 5/12 versus 12/12.

On the 108 usable cases, nominal prediction averaged 10.7431 s versus 9.6175 s for the exact-model reference. Nominal prediction was slower than the held-pose baseline on 43 of 92 common successes. Worst nominal-vs-exact duration gap: reversal-exit, speed 2.5, steady delay, five actual command steps, fast-response gains. Baseline timed out after a total 40.375 s; nominal settled in 15.4375 s, exact in 11.25 s. Retain these adverse efficiency outcomes rather than tuning on them and calling them unseen validation.

## Reproduction and evidence

```powershell
python -B -m rift_taxi.synthetic_combined_uncertainty --summary --out artifacts/NEW-combined-study.json
python -B -m unittest discover -s tests -p test_synthetic_combined_uncertainty.py -v
```

Full LEGION regression suite passed 592/592 in 102.265 seconds (exit 0). The baseline-byte-hash rejection is expected negative-test output. Six focused tests passed. The two independently produced combined reports (`artifacts/legion-combined-uncertainty-20261126-01.json` and `-02.json`) are byte-identical (480,947 bytes each), SHA-256 `753b70c6ee1fa0bd21a15af1cedb79196d8237b4da874ac021783e5259a2fe6e`. The prior 56-condition sampled benchmark was reproduced byte-for-byte: `artifacts/legion-sampled-steering-after-combined-20261126.json`, SHA-256 `3aaf293dcd2ecc2c77c54500bb3dbe117d85be6c55a544b634335fa1d4443198`.

Source SHA-256: sampled steering `248372f4c861cd237351132711a62a240aaac78c9d13c645b95084be50ba64f6`; new combined study `044da7e635c36487745e66f87802375fa1c62100c689b5b6a1dd4c699e0c2c6e`. Original reports remain local ignored files.

## Limits and next

These are deterministic flat-plane ideal actuator experiments. Gains and delays are fixed, not measured RIFT values; noise, inertia, geometry clearance and varying actuator dynamics are not simulated. The exact-model reference is privileged, not a deployable estimator. The nominal predictor is promising but should not be promoted from this authored study. Next consider a bounded offline estimator using only timestamped admitted pose increments and issued command history; separately prespecify independent geometry and varying actuator response before evaluating improvement. No real game input, current native pose qualification, physical stopping or live route completion is claimed.
