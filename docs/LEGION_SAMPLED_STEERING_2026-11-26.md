# November 26, 2026 — sampled closed-loop steering

Host LEGION; starting commit 778cbb1. This is a separate offline research controller, not a change to the production controller or the legacy ideal journey engine.

## Method

The new `rift_taxi.synthetic_sampled_steering` module evolves an ideal planar plant with a fixed FIFO command delay. A separate controller receives immutable sampled observations through the existing seven transport schedules. Capture and delivery ticks are distinct. Only admitted source samples earn route progress, using a displacement-derived budget and ordered sharp-corner witnesses. The controller has no direct access to current plant truth. It may forecast from its latest source sample and its own issued command history. Forecast position never qualifies route progress or arrival.

The binary-exact 62.5 ms tick, 40-second approach budget, 350 ms observation expiry, 1.5-unit lookahead, and 2-unit observed cross-track limit are fixed model settings, not physical calibrations. Startup with no observation requests zero. Expiry and sequence rollback stop the run; no automatic rearm. Terminal evaluation drains the actual modeled command FIFO and adds a stationary interval. Observed arrival alone is not settled arrival.

Three policies: held pose (new experiment's baseline); predictive application pose using known exact modeled command delay; predictive application plus linear age-based speed reduction (25% floor before expiry). The last is an experimental heuristic only. All use the same source-only admission, progress, and terminal criteria. The predictor knows the ideal actuator and exact fixed delay; uncertainty about real actuator response or actual latency is not addressed here.

Two route geometries (long S and sharp return), two speeds (2.5/3.5 units/s), two command delays (0/3 steps), and seven transport profiles produce 56 matched conditions and 168 runs. Reports retain all compact outcomes, STOP reasons, and final model error. The single-run API retains actual frames, deliveries, admissions, forecast references, sharp-corner witnesses and FIFO drain, then independently reconstructs integration, forecast, delivery schedule, admitted projection, passage witnesses, arrival and time/duty accounting. This is internal consistency, not a full independently implemented steering oracle.

## Results

| Policy | Settled, usable telemetry (32) | Mean full time, 31 common successes | Mean forward duty, 31 common successes |
| --- | ---: | ---: | ---: |
| Held pose | 31 | 11.0464 s | .92022 |
| Predictive application | 32 | 10.1351 s | .92689 |
| Predictive + age cap | 32 | 11.9556 s | .93587 |

All 72 long-dropout, out-of-order, and stale-stream runs stopped without settled arrival (24 per policy: eight of each fault class). No baseline success was lost. The sole baseline unsettled arrival was sampled-long-s, speed 3.5, steady 125 ms observation delay, three-step actual command delay. Baseline final model error was .306594 units (outside .3 tolerance); predictive application settled at .135929 units and reduced full duration from 13.5625 to 8.3125 s. Keep this negative baseline result. On this authored study, age capping produced no extra arrivals and increased common-success time relative to prediction alone; do not promote it.

## Reproduction and evidence

```powershell
python -B -m rift_taxi.synthetic_sampled_steering --summary --out artifacts/NEW-sampled-steering.json
python -B -m unittest discover -s tests -p test_synthetic_sampled_steering.py -v
```

Full LEGION suite passed 586/586 in 81.264 seconds (exit 0); the baseline-byte-hash rejection is expected negative-test output. Seven focused regressions passed, including delayed startup, source-only progress, FIFO drain, fault stops, tamper rejection and paired accounting. Two independently generated reports `artifacts/legion-sampled-steering-20261126-01.json` and `-02.json` are byte-identical (164,249 bytes), SHA-256 `3aaf293dcd2ecc2c77c54500bb3dbe117d85be6c55a544b634335fa1d4443198`. Module SHA-256 `101ade2c73aae9d04d84e11dd57274f256caaf0b3a1c0b6189bca593775e16b2`. Artifacts remain local ignored files.

## Next

Keep predictive application as the candidate, not a promoted default. Prespecify a combined delayed-observation and inaccurate-command-model comparison, including adverse geometry and actuator uncertainty, before evaluating it. Live M1 still requires fresh eligible session and independently qualified native observations. No OS/game input, game memory, physical arrival or collision qualification was performed.
