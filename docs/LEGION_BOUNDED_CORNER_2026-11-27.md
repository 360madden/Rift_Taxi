# November 27, 2026 — bounded synthetic corner admission

Host LEGION; base commit 598f354. This is an opt-in synthetic research policy, not measured RIFT calibration, live navigation, or M1 acceptance.

## Geometric certificate

The previous robust estimator lost two settled journeys because measured sharp-corner positions were inside the original 0.15-unit radius while retrospective plant truth was outside. See [the V2 report](LEGION_ROBUST_RESPONSE_2026-11-27.md); the adverse cases remain preserved.

For a measured X/Z point (mx,mz), target (cx,cz), and declared per-axis error bound e, the maximum possible distance from the target is hypot(abs(mx-cx)+e, abs(mz-cz)+e). This is the exact maximum over the axis-aligned error rectangle. The candidate uses the same fixed e=0.08 for every noise profile, including no noise: the hidden sensor profile is not made available to the controller. A witness requires this upper distance to be at most the original corner radius and the original arc-progress condition to hold. The approach locally caps forward speed at four times the remaining chord per second when targeting the pending sharp corner. A coincident forecast waits for actual admissible evidence within the existing time budget; it does not admit a corner or extend the budget. Default policy remains legacy.

The receipt verifier independently enumerates the four possible rectangle corners, reconstructs captured/delivered observations, and compares certified witness records; retrospective actual corner truth must remain within the original radius. The certificate establishes position containment at the capture epoch under the declared synthetic bound, not clearance, path topology, current position after transport latency, physical stopping, or native sensor accuracy. A radius smaller than the minimum possible rectangle radius cannot yield a certificate; the existing finite time and observation-expiry limits remain in force.

## Targeted regressions

All three previously changed cases are on sharp-offset. All three settled with the bounded policy, without changing the original corner radius or terminal tolerance.

| Case | Previous V2 truth corner error | Bounded truth corner error | Bounded duration (s) |
| --- | ---: | ---: | ---: |
| Speed 2.5, delay 1, fixed-cross, moderate/jitter | .15954074 | .03961826 | 18.6875 |
| Speed 2.5, delay 1, fixed-cross, impulse/steady | .15007340 | .04600164 | 18.5 |
| Speed 3.4, delay 7, slow-to-fast, moderate/jitter | .11939523 | .03583019 | 19.1875 |

## Frozen comparison design

The previous 96-condition robust-estimator design is a development replay, not fresh validation. The additional 96-condition design uses two newly authored geometries, two coupled speed/latency settings (2.7/2 and 3.2/6), fixed cross-gain or a hidden fast-to-slow gain change at tick 80, four deterministic noise profiles, and jitter-in-order, short-dropout, or long-dropout transport. Each cohort has 64 usable cases and 32 deliberate long-dropout cases. Compare V1 legacy-adaptive, V2 robust-adaptive, and V2 with bounded corner admission, on identical matched plant settings and noise laws. The prespecified screen requires no settled losses against either comparator, all candidate long-dropout cases expiring, and no false truth-witness/certificate admissions. Elapsed time and forward duty are measured on paired common successes. This is authored simulation evidence, not statistical validation.

## Reproduction

```powershell
python -B -m rift_taxi.synthetic_corner_study --summary --out artifacts/NEW-corner-study.json
python -B -m unittest discover -s tests -p test_synthetic_corner_certificate.py -v
python -B -m unittest discover -s tests -q
```

Focused tests passed 9/9 in 3.607 seconds; full LEGION suite passed 625/625 in 87.317 seconds, exit 0. The baseline-byte-hash rejection is expected negative-test output. Git diff check passed. Original evidence files stay ignored/local.

## Completed benchmark

| Metric | V1 adaptive | V2 robust | V2 bounded corners |
| --- | ---: | ---: | ---: |
| Prior development, settled | 63/64 | 62/64 | 64/64 |
| Newly specified cohort, settled | 59/64 | 63/64 | 64/64 |
| Total settled usable | 122/128 | 125/128 | 128/128 |
| Truth-witness failures | 6 | 3 | 0 |
| Prolonged observation-dropout expiries | 64/64 | 64/64 | 64/64 |

Both cohorts and the overall study passed all five prespecified research-screen conditions. Bounded policy gained six settled cases versus V1 and three versus V2, with zero losses against either. All 256 bounded corner certificates (64 prior, 192 new) remained within the original .15-unit radius, and retrospective actual corner truth passed. All 192 deliberately prolonged-dropout policy runs stopped on observation expiry (64 per policy).

On 125 common successes, V2/bounded mean full duration was 15.0745/15.9405 s and forward duty .912787/.922455. This is a .866-second (5.74%) mean duration increase versus V2. In the new cohort alone, V2/bounded mean duration was 15.72222/17.17956 s on 63 common successes. The certificate and local braking trade some speed for stronger corner evidence; keep this cost visible.

### Independent evidence check

The report `artifacts/legion-corner-study-20261127-01.json` contains 192 unique matched conditions and 576 policy executions, 889,130 bytes, SHA-256 `45f72a4f4cfbfe96291bfc351137e3e93c8f174c2e25393539514d353db946e4`. The separate audit checked the pinned original V2 report SHA-256, all 192 prior comparator policy outcomes (96 V1 and 96 V2) exactly, cohort counts, settled gains/losses, each certificate radius, actual truth-witness scores, and all candidate fault expiries. A separate repeat of the three historical adverse conditions reproduced all nine policy outcomes exactly. Full 576-run report duplication was not performed in this batch.

Source hashes: sampled steering `fc613af842ec9cc9bb60b1bb07f8287f08b26515664f01c82d954b2eac68febd`; certificate `92eed7830f52fb827ed5115aabe6b5de9491e33b6a840288835b427903b88182`; frozen study `4a8b2c6bf5f3ce2123b4449c3100e2ad2815d150dd1d4f416d865e5846c90fac`.

## Decision and next priority

Retain the bounded-corner policy as an opt-in synthetic research candidate; do not promote production defaults or claim real RIFT sensor bounds. The new cohort was authored before evaluation but is not a random population or a physical validation. Next prioritize speed recovery within the unchanged certificate, broader sharp geometry and delayed observations, and independent live M1 evidence when eligible. No game input, live measurement, collision clearance or physical qualification occurred.
