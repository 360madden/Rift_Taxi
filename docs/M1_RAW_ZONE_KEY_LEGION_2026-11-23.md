# M1 — Read-only self-owner raw zone-key candidate on LEGION

**Monday, November 23, 2026 · 2:09–2:10 PM Eastern · physical RIFT client**  
**Result:** Taxi independently decoded a *raw same-owner zone key* on the exact current physical game build using only a bounded read-only memory chain already present in its native XYZ reader. A separate pinned 12-sample series returned one stable value. **This is NOT a verified public zone ID, displayed zone name, world instance, or an authoritative `LivePose.session.zone_id`.**

## Why this slice, and why not duplicate RR2

RiftReader2 has fuller local **zone/TLS registry and candidate zone-ID** research. Taxi does not need to implement those mechanisms to gain a useful first M1 location-context continuity signal.

Taxi adapted *only* the raw same-owner key path: current self unit key → exact-build entity/health selector → health owner backlink → typed self-owner vtable/getter fingerprint → 32-bit `selfOwner + 0x150` raw key. It uses Taxi's existing resolved self entity and component table, exact-build offset table, read-only process handle, anchored byte rereads and full foreground PID/start/build/HWND identity checks. It does not invoke the game's getters, initialize or refcount game objects, inspect other units, read TLS, or depend on RR2 at runtime.

**Read-only upstream RR2 files consulted (original SHA-256s on LEGION, no changes):**

| Reference file relative to `C:\work\riftreader2\` | SHA-256 |
|---|---|
| `src/RiftReader2.Live/CurrentBuildPlayerLookup.cs` | `e1ad039f1592edfe56c194ecb1f5792a30b66cc28783fe799372bdf1be992165` |
| `src/RiftReader2.Live/CurrentBuildPlayerContextCandidateReader.cs` | `dd9a5efe53cadbf79d78da1cd6b75be8b00d18be6c33e49176378c543f6be1b4` |
| `src/RiftReader2.Live/CurrentBuildZoneSeedSampleCommand.cs` | `6a809dc5bbac172bc66775251c28177b1395c9c8f9e770ab2076540df3a0ed0e` |

Source significance: on the current SHA-pinned build, the health selector is at module RVA `0x2F68850`, owner vtable RVA `0x2933218`, getter RVA `0x19D2020`; the historical supported layout uses source-specific old RVAs. These offsets are valid **only** for the two explicitly pinned game executable hashes in `native_candidate.py`. The owner type check and backlink are required; offsets are never guessed for unknown builds.

## Physical result

| Admission or measurement | Observed |
|---|---|
| Machine | LEGION, physical game process |
| RIFT executable SHA-256 | `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01` |
| PID / process start .NET UTC ticks | `424` / `639310421805307472` |
| HWND | `1968794` |
| Native owner key | `239816685251645959` |
| **Raw self-owner zone key (hex)** | **`0x487C9102`** |
| Raw self-owner zone key (unsigned decimal) | `1216123138` |
| One-shot status | `candidate-only`, current process/owner/window admission successful |
| Pinned series | **12/12** same raw zone key, same actor-owner |
| Observed median sample interval | **129.528 ms** |
| Native XYZ and actor-matrix angle | One position and one angle across series |
| Actor/position matrix raw-bit agreement | **12/12** |
| Refresh guard pair | Both known top-level guard candidates zero in all 12 samples |
| Windows W/A/D snapshots | **24/24 all up** |
| Game input injected by Taxi during these captures | **None** |
| Public zone ID / world instance qualification | **False / False** |

One-shot capture included matrix and refresh-guard evidence, again remaining candidate-only. A series now aborts the *entire report* if its raw zone key changes during an acquisition, rather than misleadingly publishing one stable zone context. A zero raw key is preserved as an unqualified raw value, **not** proof of no zone. Successful memory reads do **not** map the raw key to a displayed game-zone name, public `z...` zone ID or unique instance.

## New Taxi-owned code and checks

- `rift_taxi/native_candidate.py` adds `ZoneKeyCandidate` and opt-in `include_zone_key_candidate`, reusing resolved native self ownership and anchored pointer checks. Unrecognized exe SHA, health/owner selector mismatch, missing slot, pointer alias, changed owner backlink or wrong native type/getter abort.
- `rift_taxi/native_capture.py` adds `zoneKeyEvidence` with explicit `authoritativeZoneQualified=false`, `publicZoneIdStatus=not-derived`, `worldInstanceStatus=unavailable`.
- `rift_taxi/native_series.py` accepts the same optional raw self-key, checks its consistency across all samples and refuses changed-key series. Still cannot certify API-quiet passive XYZ freshness.
- CLI `inspect-native-candidate --include-zone-key-candidate` and `observe-native-series --include-zone-key-candidate` are **read-only and opt-in**. Both require an explicitly pinned physical RIFT session; neither uses W/A/D input, adds a dependency on RR2, or sets a qualified live player-zone binding.
- New `tests/test_zone_key.py` checks the two exact supported builds; mismatched health/owner chain; invalid selectors, vtable/getter, changed raw zone key during source anchoring, missing/invalid report, false authority promotion, zero key, stable native series and changed-key fail-closed behavior.

## Original local evidence — Git ignored

| File under `C:\work\Rift_Taxi\artifacts\` | SHA-256 |
|---|---|
| `m1-raw-self-zone-first-20261123-1409.json` | `1b5dd4f870a39b65d3e1a13c242ab64c5ddddd704a8f79ce021889933c3e4cc0` |
| `m1-raw-self-zone-series-20261123-1410.json` | `846451c6405e239a4327c7184666373d872e32c529b09db26e4065fc0de7a948` |

**Validation:** 14 new focused synthetic decoder/source/series/CLI tests passed; the full LEGION Python 3.14 suite passed **334/334**. Both original physical read-only reports were created with **new** filenames and verified on disk. No raw capture is published in Git.

## Supplemental game-screen correlation attempt (2:17–2:19 PM Eastern)

After the successful raw-key series, Taxi performed a **read-only/hover-only UI cross-check** on the same pinned physical RIFT window:

1. Captured the upper-right RIFT HUD/minimap region using Windows screen-copy, with the exact game HWND/PID foreground verified and previous application focus restored afterward. The performance/diagnostic overlay partially obscured text around the minimap; **no reliable public zone name or ID was readable**.
2. In that same short foreground observation, issued a *separate read-only native one-shot* with `--include-zone-key-candidate`. It still reported self-owner raw key **`0x487C9102`**, identical owner, process and XYZ. These observations were sequential, not an atomic cross-source snapshot.
3. Conducted a single **cursor-hover without clicking**, over the minimap. The UI tooltip read **“Quicksilver Medic” / “Healer” / “9 meters away”**. This is an independently visible NPC/scene detail, **not a zone name or public zone ID**. Cursor and previous focus were restored; no movement key or click was sent.
4. Since the minimap and hover yielded no zone identifier, **public zone/API correspondence remains unverified**. Do not infer zone from the NPC's name or game-world appearances; do not set `LivePose.session.zone_id`.

Additional original ignored receipts:

| Original local artifact | SHA-256 |
|---|---|
| `m1-zone-ui-topright-20261123-1417.jpg` | `e2d5978d6054a4dc8de2f157ae6fc266403acc8c55eba8358cf61efca116b063` |
| `m1-zone-ui-coincident-native-20261123-1417.json` | `23cfaba1ad8b7633abeb3072480101251e059d6fb00b3eda6ef19ea148bbbad0` |
| `m1-zone-ui-hover-minimap-20261123-1419.jpg` | `7065bb23612f427d4c7cb2c405fc4db407a01ec2b8d7a886d44696a5c6168d01` |

**Result:** screen-side same-session context was retained, but the requested *independent public zone ID* was **not** established. The next useful source must expose a readable/public zone identity and capture its producer/clock, rather than sampling more identical raw keys.

## What M1 still needs

The new key supports **same-owner raw zone-context stability in one source**. It does **not** prove the player is in Sanctum Watch, Silverwood or any particular game location/instance. Next verify correspondence with an independently observed in-game zone/public identifier, ideally with a source-timestamped same-session game API or UI observation, without assuming a cached `Inspect.Unit.Detail` read is API-quiet. Then qualify actor-world freshness and body yaw across a real restart/zone change, and finish the remaining late-DOWN/focus-loss release cases.

**Production navigation remains disarmed and `LivePose.session.zone_id` is not created from this raw key.** M1 is not complete.

See [M1 handoff](M1_HANDOFF_2026-11-23.md), [native read-only research](M1_NATIVE_READONLY.md), [current RR2 reuse](RR2_HANDOFF.md), [independent parent crash proof](M1_PHYSICAL_PARENT_CRASH_RELEASE_LEGION_2026-11-23.md), and [validation requirements](VALIDATION.md).
