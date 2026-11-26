# November 27, 2026 — independent API motion-field inventory

LEGION, 03:20–03:23 PHT. Base Taxi commit b11a20e, with the previous uncommitted 02:14 PHT API-zone evidence preserved. This cycle is offline analysis of retained originals plus read-only installed-addon source inspection, not a new live capture or movement experiment.

## Why this slice matters

The preceding [native/API zone bracket](M1_API_ZONE_CORROBORATION_LEGION_2026-11-27.md) proved same-epoch candidate zone agreement and publisher progression. Reuse those original frames to answer a separate question: which motion fields actually exist, and did their values change as source sequences advanced?

The installed Telemetry 0.5.0 publisher source `telemetry.lua`, SHA-256 `a08062a2299a5f723a19bab759a4eb819c9c725939ef4e1d5cb22cb072ee41a2`, is unchanged from the prior audit. Its lines 100–112 list the fixed unit-field allowlist, including coordX/coordY/coordZ and zone, but no heading/facing/yaw/orientation field. Lines 114–133 project only listed scalar fields from `Inspect.Unit.Detail`. The publisher calls this API at line 514 and uses `Inspect.Time.Frame` at lines 585–595 with the configured .1-second period. Frame time is a producer clock, not a separately timestamped coordinate update event or host monotonic time. A missing field in this projection is not proof that the game API has no such capability.

## Retained evidence

Original directory: `artifacts/m1-20261127-0214-api-zone/`. The existing original bracket summary and separate upstream zone-replay receipt are pinned inputs. The new Taxi offline audit reopens all accepted wire files, verifies original wire SHA-256s, checks schema/player/zone/generation and indexed source timestamps, rejects conflicting repeated sequences, and deduplicates before assessing motion fields.

| Observation | Result |
| --- | ---: |
| Accepted original wire occurrences | 73 (34 + 39) |
| Unique source sequences | 39 |
| Newly advancing second-pass sequences | 5 |
| Sequence range | 83863–84003 |
| Source-clock span | 15.25390625 s |
| Retained source-clock gaps, min/median/max | .1005859375 / .3115234375 / 2.4580078125 s |
| Frames with complete XYZ | 39/39 |
| Unique XYZ candidates | 1 |
| Adjacent comparable pairs | 38 |
| Consecutive publisher-sequence pairs | 8 |
| Changed adjacent XYZ pairs | 0 |
| Maximum adjacent XZ difference | 0 |
| Heading-like fields in player projection | none |

Every accepted unique frame has the same API XYZ candidate (7213.65966796875, 871.949951171875, 3026.800048828125). Source sequence/timestamp advance is therefore distinct from observed coordinate change. In the earlier same-process Taxi native series at 16:58 UTC, the single XYZ candidate was (7213.65771484375, 871.9497680664062, 3026.804443359375). The new API bracket was captured at 18:13 UTC, approximately 75 minutes later; these are not synchronized or contemporaneous positions and cannot establish a physical error or latency calibration. Do not infer movement or stationary duration between these captures.

The retained frame span exceeds the 4.613-second host capture bracket because already-retained frames are present. Only eight of 38 adjacent retained-frame pairs represent consecutive publisher sequences. The 311.5 ms median retained source gap is **not** the live publisher interval or reader latency.

## Reproduction

`rift_taxi.telemetry_motion_audit` is a narrow downstream offline field audit. It accepts an already independently replayed original RR2 zone bracket and separate replay receipt, both caller SHA-pinned. It verifies each accepted wire and derived motion inventory, but does not replace the upstream native endpoint/zone replay or independently certify the source's authenticity. Skipped/excluded frames stay in the upstream archive. Missing/partial XYZ remains unavailable; no pair bridges a missing coordinate sample. Differences across nonconsecutive retained samples are labeled explicitly. Output retains source sequence, clock, wire SHA, XYZ candidates and pair differences, not unrelated player or target data.

```powershell
python -B -m rift_taxi.telemetry_motion_audit --summary artifacts/m1-20261127-0214-api-zone/summary.json --summary-sha 5d86c28cf8d84ffdf3cc36da292d9b8b321a828037c7b0c1faf1b364e37b8bc0 --replay artifacts/m1-20261127-0214-api-zone/zone-replay.json --replay-sha 02dbef2e6e144c860299a9ac3268ff6e8ff6fba41e08d3d698dcd51def400b48 --out artifacts/m1-20261127-0214-api-zone/NEW-motion-audit.json
python -B -m unittest discover -s tests -p test_telemetry_motion_audit.py -v
```

Both real-original audit executions passed. Reports `motion-audit-01.json` and `motion-audit-02.json`, each 22,597 bytes, byte-identical SHA-256 `37bd785a3652297df753c79da1c059d60b47e12b8df731ec68b6df0283342b62`. Nine focused regressions passed, covering missing/invalid coordinates, changes across retained gaps, generation/identity/count/hash/index corruption, conflicting repeated samples, and exclusive output. Code SHA-256 `cad423a1fe27315c2b098d0af6add5d4185a116d997e6be266bab5939535a094`. Reports and wire originals remain Git ignored. The full regression job subsequently completed successfully: 651/651 tests in 162.942 seconds, exit 0. The baseline-byte-hash rejection is expected negative-test output.

## Decision

Retain the API stream as a useful independent implementation of player position and zone observation, not a qualified body-heading source. Its Unit.Detail calls can themselves refresh native data, so native/API coordinate agreement alone cannot establish passive native freshness. No clock alignment, causal movement, game-consumed release, unique world instance, or current-session authority is established by this offline replay. No new game input, native read, addon edit, sibling write, focus change, process restart or production promotion occurred.

Next high-value evidence is a genuinely independent current-session changed-state motion/body-heading reference with explicit capture timing and scene/action provenance. Avoid further static samples as a substitute for changed-state qualification, avoid duplicating RR2 capture tools, and keep all production gates disarmed.
