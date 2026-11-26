# November 26, 2026 — deterministic observation timing and fault replay

Host LEGION; base commit 2f1c67d. This is synthetic inert-backend evidence for the actual Taxi control gate, not a physical navigation experiment or a closed-loop delayed-observation controller.

## Design and implementation

`rift_taxi.synthetic_observation_replay` obtains verified fixed prefixes of two synthetic routes at two speeds (2.5 and 3.5 synthetic units/s). Each 64-tick truth prefix uses a binary-exact 62.5 ms sample grid. The prefix digest binds the actual model frames separately from the geometry digest. Seven deterministic delivery schedules vary only transport, giving 28 cases. Captures preserve source time and sequence. At every tick the driver-neutral `HeldInputController` checks expiry before processing arriving packets, using a fake clock and inert accepted W/A edges. The existing 350 ms pose age and 500 ms hold lease are unchanged. No game or OS input calls, native reads, production arming or physical pose claims.

Delivery profiles: immediate; constant two-tick delay; alternating one/two-tick jitter (same-tick packets in source order); drop captures 20–22; drop captures 20–28; delay capture 20 by three ticks while adjacent captures arrive immediately; constant six-tick stale stream. Packets arriving beyond the 64-tick window are separately counted. All delivered packets, their admission/refusal, tick states, and inert edges up to the end of replay are retained. Normal final context cleanup releases the inert keys but is deliberately excluded from fault results.

The V2 report separately tracks age immediately before delivery and age/error of the accepted pose while keys remain held. Packet-delivery age alone hides a silent interval followed by a fresh packet. Missing samples are null, not fabricated zero errors.

## Fixed results

| Profile | Fault stops / 4 | Max delivery age (ms) | Max pre-delivery observation age (ms) | Max held-pose age (ms) |
| --- | ---: | ---: | ---: | ---: |
| Immediate | 0 | 0 | 62.5 | 0 |
| Steady delay | 0 | 125 | 187.5 | 125 |
| In-order jitter | 0 | 125 | 187.5 | 125 |
| Short dropout | 0 | 0 | 250 | 187.5 |
| Long dropout | 4 | 0 | 625 | 312.5 |
| Out of order | 4 | 187.5 | 125 | 62.5 |
| Stale stream | 4 | 375 | 437.5 | n/a |

All four long-dropout replays latched pose-expired at tick 25 (375 ms after the last accepted capture). All four reordered streams latched sequence rollback at tick 23. All four stale streams refused the first arrival at tick 6, before any DOWN edge. The remaining sixteen cases completed the observation window without a fault. The 12 faults left no inert held keys and refused 532 subsequent packet admissions; no automatic rearm occurred. Short dropout produced up to 0.65625 synthetic units of held-pose position error despite zero delivery delay. Long dropout reached 1.09350 units before STOP. At 125 ms steady delay, maximum delivery position error was 0.43750 units and yaw error 12.036 degrees. These are modeled reference errors, not physical measurements or evidence that 350 ms is an appropriate live threshold.

## Reproduction

From the Taxi repository root:

```powershell
python -B -m rift_taxi.synthetic_observation_replay --summary --out artifacts/NEW-observation-replay.json
python -B -m unittest discover -s tests -p test_synthetic_observation_replay.py -v
```

Nine focused tests passed. The full LEGION regression suite passed 579/579 in 85.297 seconds (exit 0). The baseline-byte-hash rejection is expected negative-test output. The first V1 report is preserved locally. Two independently executed V2 reports (`artifacts/legion-observation-replay-20261126-v2-01.json`, `-v2-02.json`) are 1,396,137 bytes each, SHA-256 `d39e5d5201ef6999f38ce8bc478f53b8d07a300d9fac73abcc13c5808ef461c5`. Source SHA-256 `9af5cabc321d17357d19550698f0c0a8348d63149911e04a69c9bc7584802fbe`. The evidence files are local ignored artifacts.

## Limits and next steps

Truth is a fixed trajectory and continues even after the inert gate stops; do not infer a stopped physical position, closed-loop arrival, steering robustness, physical release, wall-clock watchdog timing, actual telemetry age, or native-source qualification. The next offline controller study should separate sampled observation from actual plant state in the steering loop, retain source timestamps, and compare bounded uncertainty handling under irregular delivery. Preserve all existing production defaults and the live admission gate.
