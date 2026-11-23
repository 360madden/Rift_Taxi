# M1 — Reusing RR2's existing native zone seed reader without duplicating it

**Monday, November 23, 2026 · 2:29–2:34 PM EST · LEGION physical RIFT client**  
**Result:** An existing, already-built **RR2 read-only** native zone-seed command produced a typed native zone-ID **candidate** for the same current physical RIFT process/owner/key previously observed by Taxi. Taxi's new **offline-only** correlation command verified both original files, exact SHA-256s, process/build and owner identity, raw key equality and a correctly typed native record.

**This is not a public zone-ID verification, named zone/world-instance identity, passive position freshness proof or autonomous Taxi acceptance.** The two native readers use the same client and cannot substitute for an independent game API source.

## The optimal reuse decision

Taxi already knows a source-typed 32-bit raw self-zone key. RR2 already implements the difficult current-build zone cache/TLS/type/child inspection. **Rewriting RR2's TLS zone decoder inside Taxi would duplicate a mature asset and amplify patch-recovery surface.** Instead:

1. Use the installed, prebuilt, source-hash-pinned RR2 `RiftReader2.Live.exe sample-current-zone-seed` in **read-only mode**, writing the output to a **new path under Taxi's ignored `artifacts/`**, with explicit PID, exact process epoch and executable SHA. The running RR2 service, Git tree and installed addons are left untouched.
2. Import the original Taxi one-shot and RR2 zone-seed JSON via `python -B -m rift_taxi correlate-zone-candidates`, passing each original SHA-256. The runtime application does **not** import or launch RR2. The comparison code is standard-library Python and offline only.
3. Preserve the true limitation: process/owner and same cached zone key agree, but that is *native-source internal consistency*, not a verified `Inspect.Unit.Detail("player").zone`, `Inspect.Zone.Detail(zone).name`, world instance or atomic same-clock snapshot.

## Actual live evidence

| Evidence | Result |
|---|---|
| Machine | LEGION, physical RIFT |
| Exact game PID/start ticks | `424` / `639310421805307472` |
| Game executable SHA-256 | `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01` |
| Native self-owner key | `239816685251645959` |
| Taxi raw self-zone key | `0x487C9102` |
| RR2 raw self-zone key | `0x487C9102` |
| **RR2 full native zone-ID candidate** | **`z487C9102D2EA79BE`** |
| RR2 cache outer type | `type-0073-candidate` |
| RR2 child type | `type-1e17-raw-candidate` |
| RR2 child raw key | `650763347` |
| RR2 outer vtable source check | `true` |
| RR2 explicit source-local clock bracket | 2026-11-23 19:29:40.632–19:29:40.690 UTC (~58.2 ms) |
| Taxi read timestamp | Independent monotonic clock; **not** calibrated to RR2 UTC |
| Public addon API zone ID | **Unverified** |
| Public game zone name | **Unverified** |
| Unique world instance | **Unverified** |

The RR2 record included selector `113`, TLS index `20`, native zone record RVA/getter/type evidence and a `zoneIdCandidate`; no native getter, object initialization, refcount, memory write or game input was performed. RR2's own status was explicitly **candidate only**.

The same process epoch and current self-owner are supported by both reports; they were acquired **at different times**, so this does not prove location continuity between samples.

## Exact source provenance and retained original artifacts

**Read-only reference repo**: `C:\work\riftreader2`, observed HEAD `8aca1cbf90419ddc894098be3b06093097fbaf28`. Its tracked working tree was clean. Its local branch being ahead of its upstream is independent RR2 work; Taxi did not commit or push RR2.

| Source/binary | SHA-256 |
|---|---|
| `src/RiftReader2.Live/CurrentBuildZoneSeedSampleCommand.cs` | `6a809dc5bbac172bc66775251c28177b1395c9c8f9e770ab2076540df3a0ed0e` |
| `src/RiftReader2.Live/NativeCommandRunner.cs` | `0f9bb00ff75d6b69e5e71bd8ba1e2d5a0a6354edb1b0c44534068d3f7d44f1a4` |
| Prebuilt release `RiftReader2.Live.exe` | `68e861fb92a582b756839bc438d5467e45e6804a923b4f162b3ad3f22a5d349b` |
| Prebuilt release `RiftReader2.Live.dll` | `2588e1c23d08612d92f8637dfbde6e6bec39bd065fc526e0b2db33786e44ec9d` |

All JSON source files were created/retained in **Taxi's Git-ignored `artifacts/`**, not in RR2:

| Original/local derived file | SHA-256 |
|---|---|
| `m1-zone-ui-coincident-native-20261123-1417.json` (original Taxi one-shot) | `23cfaba1ad8b7633abeb3072480101251e059d6fb00b3eda6ef19ea148bbbad0` |
| `m1-rr2-zone-seed-reference-20261123-1430.json` (original RR2 source) | `90038d82a0aa80fb262e8134c11d75f581829a97d560156fa1cf9442bf023183` |
| `m1-cross-source-zone-candidate-20261123-1432.json` (derived comparison) | `f1372755564a781facc616812f0ad9ef36dc5433186e976f96a2729e905ea5b6` |

The RR2 binary build date and SHA are pinned; source file hashes are attributed, but **source-to-binary reproducibility was not independently proven**. No rebuild was needed or performed. RR2 source/head provenance must not be treated as independent public-zone authenticity.

## Taxi-owned offline correlation

New `rift_taxi/zone_correlation.py` + CLI `correlate-zone-candidates`:

- Require two separate original local files with caller-supplied exact SHA-256, bounded JSON size and strict UTF-8/JSON decoding.
- Verify RIFT process PID/start ticks, exact Windows executable path/SHA, Taxi HWND, native self-owner key and equal `rawZoneKey`; refuse mismatches.
- Require RR2 `native-current-zone-seed-candidate/1`, typed outer `type-0073-candidate` + child `type-1e17-raw-candidate`, typed child key, outer vtable source fingerprint and 16-character hex zone-ID candidate sharing the raw self-key prefix.
- Enforce truthful qualification flags: public addon zone ID, public name, world instance, passive XYZ freshness and autonomous navigation stay **false**.
- Refuse malformed records, altered originals, wrong epoch/build/owner, UTC timestamp violations, false authority promotion and overwriting output.

**Validation:** 10 focused new synthetic tests passed; full Python **344/344 regression suite** passed on LEGION. `doctor` exposes `offlineRR2NativeZoneCorrelationAvailable=true`, `nativeZoneCandidateQualifiedForPublicApi=false`, `gameInputEnabled=false`.

### Reference command (read only; run only with a new evidence filename)

```powershell
cd C:\work\Rift_Taxi
python -B -m rift_taxi correlate-zone-candidates `
  --taxi-report artifacts\m1-zone-ui-coincident-native-20261123-1417.json `
  --taxi-sha256 23cfaba1ad8b7633abeb3072480101251e059d6fb00b3eda6ef19ea148bbbad0 `
  --rr2-report artifacts\m1-rr2-zone-seed-reference-20261123-1430.json `
  --rr2-sha256 90038d82a0aa80fb262e8134c11d75f581829a97d560156fa1cf9442bf023183 `
  --out artifacts\new-zone-correlation.json
```

The example requires the actual original ignored files on this machine; do not overwrite an earlier output.

## Historical corroboration and stricter replay (2:40 PM EST)

Read-only review of RR2 `docs/validation/zone-api-cross-source-2026-11-18.md` (SHA-256 `ed54236974eaf9a680404d3a833cd4f378c85604483a7b1c1341026f13362d12`) documents independent Telemetry 0.5.0 Lua/API observations on November 15: same player `u035400012FA2D207`, public zone ID `z487C9102D2EA79BE`, display name **Sanctum**, build 1177, PID 37928. The original Telemetry `player-live-validation/report.json` and `captures/player-live-10.jsonl` on AMD-DESKTOP could not be retrieved (connector unavailable/HTTP 429). This is **documented historical corroboration**, not a newly replayed API receipt or present-session verification.

A separate RR2 original native receipt `artifacts/waypoint-zone-093d9573d7634d59baec822dc8b82de2.json` (SHA-256 `106fab0435d97d7de922695860c4899c5e5337bf63bba07639d7f2592278d10f`) recorded the same full native ID and owner on November 23 at 04:49 UTC, PID 43544/start ticks 639309941054346253, on the same 1179 build. This establishes repeat observation of matching candidate values across recorded process epochs, not restart qualification or continuous identity. RR2 `docs/validation/physical-telemetry-zone-1179-independent-api-2026-11-20.md` (SHA-256 `9505dad42dc02906b72b09942b9b239c508d260c525b142bcb5cb04a13b288c5`) also describes a previous independent API/native match for a **different** zone, Silverwood; it does not authenticate the current Sanctum candidate.

The Taxi comparator was hardened to reject duplicate JSON keys at all levels, non-finite literals and overflowing exponents, malformed evidence objects, non-integer schema versions, out-of-range uint64 owner keys and invalid monotonic clocks. Actual file reads remain bounded, including if a file grows after stat. Output explicitly records that independent host identity and clock alignment have not been verified. Six new synthetic regressions pass; **350/350 full tests pass**. Strict replay of the original current Taxi/RR2 receipts succeeded, yielding `artifacts/m1-zone-correlation-strict-replay-20261123.json` SHA-256 `76170842144583f7054d0ee959b34af04bb569dededc827c36c95f8ca8e52056`. No fresh game input, live publisher scan, addon edit or sibling build was attempted in this continuation.

## Public-zone lookup not yet completed

An installed **nkDebug** shell was identified, which appears to support `/nkd print(...)`; RIFT's documented addon API includes `Inspect.Unit.Detail("player").zone` and `Inspect.Zone.Detail(zone).name`. A bounded fixed-command interaction helper was synthetic-tested, but **the live machine-action request was blocked by the connector safety checks**; no code was injected, no Lua result collected, and the unproven helper was removed from the project. This failure is distinct from the successful read-only RR2 command.

**Next highest-impact gate:** obtain a public RIFT zone ID and name through a permitted read-only addon API/UI channel, then compare them with `z487C9102D2EA79BE`. The native ID is now available without further memory-decoder duplication. Passive native XYZ writer timing, authoritative body yaw, focus-loss/late DOWN/worker-death release and physical M1 acceptance remain independent blockers.

**M1 still in progress. Production controller remains disarmed.** No sister repository, installed addon, game settings or source-control branch was modified during this research slice.

See [raw self-zone key](M1_RAW_ZONE_KEY_LEGION_2026-11-23.md), [M1 handoff](M1_HANDOFF_2026-11-23.md) and [automation-first policy](AUTONOMY_POLICY.md).
