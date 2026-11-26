# M1 — same-epoch independent Telemetry zone corroboration

**November 27, 2026 · 02:13–02:15 PHT · LEGION · development-only, read-only**

## Result and scope

Reused the existing RR2 Telemetry capture and offline replay as development tools, not as a Taxi runtime dependency. The current RIFT process was independently enumerated and its path, epoch, window and on-disk executable hash checked before collection. The prior Taxi 24-sample native receipt was independently audited again. The new acquisition uses RR2's native endpoints and the installed Telemetry 0.5.0 Lua API publisher.

| Evidence | Result |
| --- | --- |
| Host | LEGION |
| PID / start UTC ticks / HWND | 24992 / 639313044653553067 / 4198144 |
| RIFT on-disk executable SHA-256 | df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01 |
| Native owner / API player ID | 239816685251645959 / u035400012FA2D207 |
| Taxi raw zone key (earlier same-epoch series) | 0x487C9102 |
| RR2 native and independent Lua API zone candidate | z487C9102D2EA79BE |
| API display-name candidate | Sanctum |
| Frame occurrences, two passes | 34 + 39 |
| Unique source sequences | 39 |
| Newly advancing second-pass frames | 5 |
| Source sequence range / publisher epoch | 83863–84003 / 8 |
| Maximum zone-field source age | 4.9404296875 source-clock seconds |
| Ordered host acquisition span | 4.613 seconds |

The capture exited 0. A separately executed upstream offline replay re-opened the original SHA-pinned sources and exited 0 with matching-candidates. A separate Taxi-side Python check reopened the earlier native-series original, audited it using Taxi's existing verifier and compared exact stored host/PID/start/path/build/window, owner-to-API player ID conversion, and raw-zone prefix with the pinned new capture/replay. It independently rehashed both native endpoint originals. This check exited 0.

The earlier Taxi capture (16:58 UTC) and this capture (18:13 UTC) are **not contemporaneous**, and no cross-clock calibration is asserted. The new native-before/Lua/native-after bracket is the basis of bounded API-zone corroboration, not the earlier stationary series.

## Source provenance

Installed Telemetry startup source is unchanged from the November 23 audit (read-only hashes):

- main.lua: 854734c431e1404849ce44044a4788ec55183adc5f74e03154d6733afc2e9f0a
- telemetry.lua: a08062a2299a5f723a19bab759a4eb819c9c725939ef4e1d5cb22cb072ee41a2

The publisher calls the game API and retains advancing in-process schema-4 frames. The installed SavedVariables declaration contains settings, not a durable live-frame stream. The standalone Telemetry repository is absent from LEGION's C:\work. Rather than write another memory scanner or modify an addon, reused the existing bounded RR2 capture with explicit host/PID, explicit prebuilt reader and new Taxi-owned output directory. Its map-aware scope locator reached its configured 512 MiB byte budget and selected a validated candidate scope; this is not a complete memory search or evidence of portable heap addresses.

Capture/replay script SHA-256 values were unchanged across the execution:

- RR2 scripts/capture_physical_telemetry_zone.py: 019c4d93aba4d7c2a04c8a7f3d32b6ea363fb2cff051f4aebba275783414a24b
- RR2 scripts/replay_physical_telemetry_zone.py: 3845ca9b36c631dd94a06fa1e4ad6b6ccab04329f194e7f1a402a14dc693f7b1
- Explicit prebuilt RiftReader2.Live.exe: 07663b73536bd128da315dae1908df9a22e696fc555aa403fdf7ce20cc272fd0

Observed RR2 HEAD edeb6a85ea4087ecbafdfc114936a68b88d4da68. These hashes do not establish source-to-binary reproducibility or pin every transitive dependency. RR2 was clean at the initial check; its final status showed a modified CurrentBuildExperienceSeedTests.cs, apparently separate concurrent development. This task made no RR2 tracked-file edits, builds, commits or pushes; leave that unrelated modification untouched.

## Retained original evidence

All new capture outputs are under Taxi's ignored artifacts/m1-20261127-0214-api-zone/ directory.

| File | SHA-256 |
| --- | --- |
| summary.json | 5d86c28cf8d84ffdf3cc36da292d9b8b321a828037c7b0c1faf1b364e37b8bc0 |
| zone-replay.json | 02dbef2e6e144c860299a9ac3268ff6e8ff6fba41e08d3d698dcd51def400b48 |
| native-before.json | 0cb5a18fcbb2acf518a02ca50c7e032582dd22353d6d073c1dcca5f083136af6 |
| native-after.json | 702c952c91f313cd31f04f730e5c773ff64646fb67138e8e804f52db2d0c8cc2 |

The original Lua wire frames remain in pass-01 and pass-02 with source digests in the summary. Native endpoint brackets: 2026-11-26T18:13:41.8474585–18:13:41.9271185Z and 18:13:46.5401115–18:13:46.6475593Z. Earlier original Taxi series SHA-256 3fea0fef655be1b434d2b3039c35aade37f397bd1ad33524a976c1d0fc9546f7, retained in artifacts/m1-20261127-current-session-series-01.json.

Replay the retained RR2 sources from Taxi root using a NEW output path (development only):

```powershell
python -B C:\work\riftreader2\scripts\replay_physical_telemetry_zone.py --summary artifacts\m1-20261127-0214-api-zone\summary.json --output artifacts\m1-20261127-0214-api-zone\NEW-replay.json
```

Do not reuse the recorded PID, HWND or heap scope as a live pin. Any subsequent live acquisition requires a new exact session check.

## M1 decision

Independent, advancing public API zone-ID and name corroboration now exists for this bounded process/owner observation. This reduces the missing API-reference blocker; it does **not** prove unique world-instance identity, synchronized Lua/host clocks, atomic reads, uninterrupted zone continuity, passive native XYZ freshness, body heading, scene clearance, game-consumed release or route traversability. The Telemetry producer's Unit.Detail calls may themselves influence the native position cache, so API/native agreement cannot establish passive freshness. The earlier desktop enumeration refusal remains unresolved. No new movement or game-memory write was performed. Production remains disarmed.

Next prioritize independent movement-source timing and body-heading evidence, then the remaining physical release qualifications, rather than duplicate the zone scanner or repeat static zone acquisitions without a concrete reason. No runtime code changed; the preceding 642-test regression checkpoint remains the code baseline. This evidence-only checkpoint reuses the existing verified capture/replay tools and records their limitations.
