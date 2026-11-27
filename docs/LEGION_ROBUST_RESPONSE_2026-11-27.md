# November 27, 2026 — robust response estimation and noisy corner admission

Host LEGION; base commit e0efb79. Research-only synthetic comparison. The original estimator and production defaults are unchanged. No physical RIFT observations, live input, or M1 qualification.

## Implementation

The experimental V2 estimator uses signed displacement projected along midpoint heading to avoid unsigned stationary-distance bias, overlapping four-tick windows that never bridge missing captures, a median-seeded robust scalar fit, and separate residual scales for speed and yaw. It searches the same bounded whole-step latency range. A fit requires sufficient excitation, a bounded residual and separation from competing delay hypotheses. Two disjoint inconsistent innovation blocks invalidate a current fit; recent inconsistent observations seed a new window, while the controller falls back to the fixed nominal model. Fit lifetime is 64 ticks (4 seconds), versus 96 in V1. Confidence here means support within a synthetic model, not measured pose freshness.

The optional deterministic sensor fixture perturbs X/Z and wrapped yaw only. Mild and moderate profiles use bounded per-axis errors of .005/.015 synthetic units and .25/.75 degrees; impulse adds an occasional .08-unit/3-degree error. Actual capture ticks, transport order and plant motion remain separate. Neither controller receives the noise profile, plant truth, or response-change schedule. For noisy runs the report checker reconstructs the measured captures, and the final scoring also requires actual sharp-corner witness positions inside the original radius. A noisy observation is not proof of a traversed corner. The prior no-noise adaptive report is byte-identical.

## Fixed benchmark and results

Two authored geometries, two coupled speed/latency settings, two response profiles (constant cross-gain or hidden switch at tick 64), four sensor profiles, and three transport schedules: 96 matched conditions, 288 runs. The fixed nominal predictor, V1 adaptive predictor, and V2 robust adaptive predictor all see the same deterministic noise law and transport pattern. There are 64 usable and 32 prolonged-dropout conditions per policy. This is an authored development design, not statistical or physical validation.

| Metric | Fixed nominal | V1 adaptive | V2 robust |
| --- | ---: | ---: | ---: |
| Settled usable journeys | 49/64 | 63/64 | 62/64 |
| Prolonged dropouts expired | 32/32 | 32/32 | 32/32 |
| Truth-witness failures, usable | 5 | 1 | 2 |
| Qualified estimate coverage | n/a | 88.51% | 92.85% |
| Conditional accuracy | n/a | 91.17% | 95.62% |
| First accurate model, mean seconds | n/a | 1.60156 | .88086 |
| Post-change reacquisition, mean seconds | n/a | 2.94531 | .984375 |
| Cases acquiring a model | n/a | 64/64 | 64/64 |
| Post-change accurate runs | n/a | 32/32 | 32/32 |

Accuracy means actual delay and both response gains within the fixed .05 tolerance, among qualified frames. V2 performed 36 invalidations across the usable cohort; this is not an independently measured physical false-alarm rate. V2 reduced mean reacquisition time 66.58%. Among 61 common successes, mean full duration was 14.65779 s (V1) versus 14.33197 s (V2); mean forward duty .93100 versus .92716. V2 has one gain and two losses relative to V1 and therefore **fails the prespecified no-settled-losses research screen**. Do not promote V2.

| Sensor profile | V1 settled | V2 settled | V2 gains / losses vs V1 |
| --- | ---: | ---: | ---: |
| None | 16/16 | 16/16 | 0 / 0 |
| Mild | 16/16 | 16/16 | 0 / 0 |
| Moderate | 15/16 | 15/16 | 1 / 1 |
| Impulse | 16/16 | 15/16 | 0 / 1 |

## Retained adverse cases

All three changed settled outcomes were on sharp-offset, scenario SHA-256 ee4910e91f4a9e98c3f87170081e7b0d8d3730a41febdf7ec79b992dc64a146f. The two losses had speed 2.5, actual delay one tick, fixed-cross gains (.9,1.2). Moderate noise with jitter: V2 truth witness error .15954074, terminal error .19052803. Impulse noise with steady delivery: V2 truth witness error .15007340, terminal error .19258619. Both terminal errors are within .3 tolerance, but neither corner witness meets the .15 radius. V1 truth witness errors were .07048982 and .13970977. The recovered moderate/jitter case had speed 3.4, seven-tick latency and a slow-to-fast switch; V1 corner error .15837307 and V2 .11939523. Do not relabel these as successes by widening the retrospective radius. Next investigate an opt-in uncertainty-aware sharp-corner admission rule on a separate frozen design, retaining all three cases.

## Reproduction and provenance

```powershell
python -B -m rift_taxi.synthetic_robust_study --summary --out artifacts/NEW-robust-study.json
python -B -m unittest discover -s tests -p test_synthetic_robust_estimator.py -v
python -B -m unittest discover -s tests -q
```

Focused tests 10/10; complete LEGION suite 616/616 in 80.287 seconds, exit 0. The baseline-byte-hash rejection is expected negative-test output. Git diff check passed. The original adaptive report regenerated with SHA-256 598384cca32c2af877f159d61f4c72beff77d26df9c974dae37577bf5529e9c9 (824,621 bytes). First robust report `artifacts/legion-robust-study-20261127-01.json`, SHA-256 619c246b130a309d13a721429b3a26f66d7b2c0752015f9e296310d7cd3a5f1d (375,701 bytes). The independent repeat `artifacts/legion-robust-study-20261127-02.json` has identical size and SHA-256; both runs exited 0. Original artifacts stay local and ignored.

Source SHA-256: sampled steering 2b214f76a9caecff1d62a709b9acf8b7c05e22d7fe99851f121d96a453863a65; estimator V2 7d1839663469ce772aa9121136420a1e44bfd77508e008210bd71434828a4f47; sensor noise 9bcf8de9099726d7ac69666263ea6190c9420fe30fcd28c8bc50348551f53d0f; study 0bc1623ea6b841e43f881870fd6097c843e25bd6dec2b77877a68b5913a0f080.

## Limits

Noise is deterministic, gains piecewise constant, actual delay fixed, and plant planar/ideal; no inertia, variable delay, terrain, collision or real actuator calibration. A qualified estimate does not authorize live navigation. Existing live M1 evidence gates remain binding. Production input remains disarmed.
