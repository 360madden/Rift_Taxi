# November 27, 2026 — tapered certified-corner approach

Host LEGION; base commit aa5cba3. This is a separate opt-in synthetic research candidate. The existing bounded and legacy policies remain unchanged; no actual RIFT navigation, measurement, game input or physical qualification.

## Method

The preceding bounded policy uses a fixed .08 synthetic-unit per-axis measurement-error envelope. It certifies a sharp corner only when the entire error rectangle lies within the original .15-unit radius (for the existing .30 terminal tolerance), with the original ordered arc condition. Its local requested velocity cap is 4d synthetic units/s, where d is the forecast chord to the pending corner.

The new `bounded-taper` policy preserves the certificate, capture and delivery ordering, STOP gates, actuator estimator, one-tick overshoot cap, final arrival criterion and actual FIFO drain. Only its local approach speed cap changes to

    4d + 4 max(0, d - 0.25)

This continuous monotone function keeps the previous cap for d at or below .25 units and permits more requested speed farther away. Existing nominal speed and turn-rate restrictions still apply. The fixed knee and extra slope were selected before the study, without fitting to its results. They are research parameters, not a measured stopping-distance model.

The full per-run verifier checks the declared policy and constants, independently reconstructs the delayed control pose and ordered corner target/rejoin state, and verifies the local speed cap for this new policy. It retains independent rectangle enumeration, actual captured corner truth checks, arrival and terminal drain. Prediction never substitutes for a captured witness. This is internal consistency and synthetic outcome verification, not a complete independent controller implementation or physical release proof.

## Prespecified comparison

- Historical cohort: all 192 conditions in the original bounded-corner study; the exact archived baseline is pinned at SHA-256 45f72a4f4cfbfe96291bfc351137e3e93c8f174c2e25393539514d353db946e4. Regenerate the original condition identities and require a one-to-one match, then run only the tapered candidate for each.
- Fresh cohort: 48 newly authored conditions: two consecutive-turn geometries (four-turn ladder and rotated tight switchback), two coupled speed/delay settings (2.6/3 and 3.3/8), fixed mixed gain or a hidden gain change at tick 96, moderate or impulse measurement error, and steady-delay/short-dropout/long-dropout transport. Run both bounded and tapered policies under identical plant settings.
- Total: 240 matched conditions, 480 policy outcomes, comprising 192 archived baseline results and 288 new executions. This deliberately avoids claiming that archived data was rerun.
- Each cohort must preserve all settled baseline successes, improve mean time on commonly successful usable cases, expire every deliberate long-dropout case, and preserve all corner certificate and truth-witness checks. Keep every failure and report slower individual cases as well as gains.

## Reproduction

```powershell
python -B -m rift_taxi.synthetic_corner_speed_study --prior artifacts/legion-corner-study-20261127-01.json --summary --out artifacts/NEW-corner-speed-study.json
python -B -m unittest discover -s tests -p test_synthetic_corner_speed.py -v
python -B -m unittest discover -s tests -q
```

All nine focused tests passed in 1.606 seconds. Git diff check passed. The full suite and benchmark outcomes are recorded in the completed-results section after verification. Source and original reports remain local and ignored where appropriate.

## Completed results

| Cohort | Matched usable | Bounded settled | Tapered settled | Mean bounded / tapered duration (s), common successes |
| --- | ---: | ---: | ---: | --- |
| Archived | 128 | 128 | 128 | 15.990234 / 15.921387 |
| Fresh | 32 | 32 | 32 | 21.208984 / 21.083984 |
| Total | 160 | 160 | 160 | 17.033984 / 16.953906 |

All prespecified gates passed in both cohorts: no lost settled successes; lower matched mean duration; 80/80 candidate deliberate dropout expiries; 384 valid candidate certificates, no retrospective truth-witness failures. The overall mean gain is only .080078 s (0.47%); mean duty .9140372 / .9144019. 73 journeys were faster, 78 equal, 9 slower, maximum slowdown 1.0625 s. Archived cohort 50/72/6 faster/equal/slower; fresh cohort 23/6/3. Preserve all nine slowdowns. The fresh cohort is authored independently of results, not a random sample or live route.

The separate report audit confirmed all 192 prior baseline outcomes exactly against the pinned archive, unique condition identities, 48 fresh paired conditions, all candidate corner witness and fault classifications, settled counts and paired duration means. Four selected historical bounded runs were newly reproduced byte-equivalently at the compact-result level; the corresponding four tapered results also reproduced exactly. A complete independent duplicate of the 288 newly executed runs was not performed. Report `artifacts/legion-corner-speed-20261127-01.json`: 935,805 bytes; SHA-256 `d0f8e1f3089476e307201e827f92a399a1cd4500b2775ac1adde675d03dd3206`. Study exited 0. Full suite 634/634 in 91.244 s, exit 0; the baseline-byte-hash rejection is expected negative-test output.

Source SHA-256: sampled steering `ad193f50458b3d31b3f8e3c629337573def5ad4489835f322ee0a29b2ea12782`; taper `7d2554804fd6610a94bdcaa7c3479d5b7416c61c8e8b2f09f0fe912b69a07adb`; comparison `4339723479545aeb734b6ed060f7b6e971e8e12d3b60eb474bdf1d3c34f07fc3`.

## Decision

Keep the tapered policy opt-in, with the previous policy preserved. Given the marginal mean speed improvement and nine slowdowns, do not spend successive development cycles tuning a synthetic corner coefficient without stronger evidence. Prioritize the actual M1 qualification bottlenecks: fresh physical session, source freshness, body heading, zone identity, and independently verified release. Continue targeted offline diagnostics where these prerequisites cannot yet be met. No game input or physical qualification occurred in this batch.
