# M1 native XYZ cache-refresh guard study — physical LEGION, November 23, 2026

**Live result:** Taxi-owned exact-build, read-only position-component guard bytes were successfully captured on the running RIFT client on LEGION. **Both known conditional cache-refresh entry guards were zero** in one one-shot capture and **four separate burst observations**. This establishes current *candidate branch inputs*, **not** actual writer execution, absence of other writers, stale XYZ, body yaw, or passive refresh qualification.

## Verified exact process and source

| Field | Value |
|---|---|
| Machine | LEGION |
| Executable | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |
| SHA-256 of executable on disk | `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01` |
| PID / process start .NET UTC ticks | `31684` / `639310312490361378` |
| HWND | `22022232` |
| Same native current-player owner key | `239816685251645959` |
| XYZ component cache candidate | `(7208.7431640625, 871.6995849609375, 3020.64208984375)` |
| Position component QWORD `+0x100` | **0** in every sample |
| Position component BYTE `+0x108` | **0** in every sample |
| Known handle / alternate-flag top-level routes | **Guard-ineligible** under these captured branch inputs |
| Position-secondary vs. actor orientation | **9/9 raw float32 values match** in each observation |
| Burst | **4/4 completed**, 1.6761502 s; no native XYZ/yaw/matrix/guard changes |
| Game input, memory writes and reload | **None** |

The window was initially minimized. A temporary Windows restore/foreground action enabled **read-only** acquisition; afterward, the existing minimized state and previous foreground HWND `328472` were restored. The session and its working directory remain otherwise unchanged.

## Source provenance

Taxi uses the **existing owner-checked 0x110-byte position component read**, from which it already obtains XYZ, vtable and owner backlink. There are **no additional native memory reads** for the new guard fields. The original full component payload is compared again during capture.

Source interpretation was independently reviewed against these **read-only RR2 references**; none were modified:

| RR2 source relative to `C:\work\riftreader2` | Observed source SHA-256 |
|---|---|
| `src/RiftReader2.Live/CurrentBuildPositionSampleCommand.cs` | `6a2d0d8240f922b519b8cfff669f5f3086e1bfd7d7b69cd0018fb9064311d895` |
| `src/RiftReader2.Live/CurrentBuildOrientationCandidateReader.cs` | `8faed1488890b00eb1c28ca959d3d290150553baa7afb7bb9ea9213565e2fe50` |
| `docs/reference/current-native-xyz-writer-evidence.md` | `b29c08a611c74a452270274c0fcfdaa85b8bf389da894720771ad075beb968d8` |
| `docs/reference/current-native-xyz-tracking.md` | `c07428dbbdf7c9ab34ff6c057c2b5cf4598a8e1e7294c984af4f24f228417a40` |

RR2's earlier code tracing isolated two **conditional** primary cache writers in the previous layout: a handle-present path when QWORD `+0x100 != 0`, and an alternate-provider path when handle is zero and BYTE `+0x108 != 0`. These guards are also co-sampled by its current-build position reader. A zero/zero pair means **neither of these previously isolated top-level branches can be admitted under the sampled conditions**. It does not establish that *all* game position writers are accounted for, that these are the only update routes on the installed build, or that `Inspect.Unit.Detail` definitely did or did not execute. The original code-sourced behavior must be separately validated for current-build writer execution.

Important: The game addon API `Inspect.Unit.Detail` can itself invoke a cached XYZ refresh route. This makes API-before/native-after agreement a possible **circular reference**, not independent passive freshness proof. Ordinary addon polling may prevent an API-quiet interval even if Taxi does not explicitly call it. Any future cross-source qualification must capture exact producer/API order and source timing before promoting XYZ.

## Original evidence (locally retained, ignored by Git)

| Native report under `C:\work\Rift_Taxi` | Original SHA-256 |
|---|---|
| `artifacts/native-refresh-guard-20261123-0747-p31684.json` | `d857055b68d99b9230c9c064513af95e01c289ac583d9ffb1cd4c70d8c57191c` |
| `artifacts/native-refresh-guard-burst-20261123-0749-p31684.json` | `259c857079867c5b44f8759d4c057c143567817345d6573790066d5aa73b6e1e` |

Raw reports are **not committed**. Validate hashes before interpreting. Both reports say `status=candidate-only`, `knownWriterExecuted=false`, `passiveXyzFreshnessQualified=false`, and `inputSent=false`. The four-observation burst summary says `allKnownTopLevelRoutesIneligible=true`, `anyRefreshHandleChanged=false` and `anyRefreshFlagChanged=false`. This is one physical **stationary** epoch, not a changed-state experiment.

## New Taxi features and test evidence

- `rift_taxi.native_candidate` exposes a new optional immutable `RefreshGuardCandidate`, co-sampled from the full owner-checked position-component payload.
- `inspect-native-candidate` supports `--include-refresh-guard-candidate` and records decimal/hex handle, raw flag and source-defined top-level guard status.
- `inspect-native-burst` accepts the same opt-in flag, validates per-sample guard consistency and summarizes guard changes and all-ineligible status. Legacy normal and matrix-only captures are preserved.
- The parser rejects wrong hex/decimal equivalence, fabricated branch statuses, bad flag ranges, requested-but-absent evidence, unsolicited refresh-guard evidence, and any false assertion of cache freshness or writer execution.
- The final LEGION regression suite passed **200/200 tests** on Python 3.14.10. **No native writer invocation, gameplay input or field edits** took place.

## Next discriminating experiment

1. Verify the same physical RIFT session, player unit key and current zone, and record fresh **native-before** XYZ/matrix/guard samples with exact process-build pinning.
2. Establish whether an in-game addon is polling `Inspect.Unit.Detail`. **Do not label an interval API-quiet without producer-side evidence.** An API call can refresh the cache.
3. With a separately qualified, bounded movement input/release window (or independently observed manual movement), capture **changed-state native-after** values and independent visual/API coordinates. Record all source clocks or calibrated envelopes, event ordering, actual input releases and any producer API calls.
4. Run a camera-only negative control versus a body A/D turn. Check source semantics at two orientations, movement XYZ response, full game restart and rebind. Until then `LivePose.actor_yaw_verified` and passive XYZ freshness must remain **false**.
5. If guard-zero values persist despite independently proven movement and new XYZ values, prioritize the other native cache writers rather than assuming these two conditional routes are complete.

**M1 remains incomplete.** This is a new live negative diagnostic, not a passed autonomous navigation test. RR2/RiftWorld were used as read-only references; Telara Fly was untouched.
