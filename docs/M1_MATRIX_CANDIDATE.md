# M1 — Opt-in actor / position matrix comparison

**Status:** Implemented as a **read-only, candidate-only diagnostic** on LEGION, November 23, 2026. **No new live RIFT capture, player-heading qualification, or movement input.**

## Why this matters

RIFT Taxi must learn which numerical heading can drive a character smoothly. The existing `player-system +0x304` scalar is a **yaw candidate**, not independently verified avatar facing. RR2's read-only work discovered a second relationship: the position component's secondary 3×3 matrix (offset `+0x94`) and the actor component's matrix (offset `+0x398`) matched in **9/9 raw float32 elements** in a stationary build-1179 capture. This indicates a plausible internal copy/alias relationship, **not** which matrix corresponds to player body heading.

Taxi now optionally samples both **from the same freshly resolved player entity**. This reduces the next experiment's unknowns without requiring a running RR2 service.

## How it works

The optional diagnostic is inside `rift_taxi/native_candidate.py` and is enabled only by `--include-matrix-candidate` on **`inspect-native-candidate`**. The default XYZ/yaw capture remains unchanged and does not read the actor matrix.

For a caller-supplied, exact SHA/PID/start-ticks/HWND/host and live foreground game window, the new branch:

1. Reuses Taxi's existing anchored self-entity, player key, exact-build component table and validated XYZ/yaw candidate.
2. Resolves **the actor component selector**, at `module+0x2F58490` (older source-pinned build) or `module+0x2F69490` (updated build-1179), without scanning unknown memory.
3. Reads nine little-endian float32 values from the **already captured** position-component bytes at `+0x94` and nine from actor-component `+0x398`.
4. Compares their **original uint32 bits**, not rounded angles. Reports `exactRawBitsMatch` and separate candidate structural Y-planar angles.
5. Rechecks every consumed memory region and the owner chain. Changing bytes, missing selectors, invalid pointers and aliasing components fail the optional capture rather than publishing unqualified data as proven.

For structural matrices, the angle diagnostic follows the source-backed row-major convention `atan2(m[6], m[0])` in degrees, only after the 3×3 orthogonality, determinant and Y-planarity checks pass. Nonfinite or nonplanar matrices retain raw bits but **do not** generate a synthetic angle or qualify heading.

Even a perfect raw match leaves `actorHeadingQualified=false`; there is no `LivePose` conversion, game-input call, or implicit approval for navigation.

## Exact source provenance (RR2, examined read-only)

| RR2 source file under `C:\work\riftreader2` | SHA-256 observed |
|---|---|
| `src/RiftReader2.Live/CurrentBuildPlayerLookup.cs` | `e1ad039f1592edfe56c194ecb1f5792a30b66cc28783fe799372bdf1be992165` |
| `src/RiftReader2.Live/CurrentBuildActorPoseCandidateReader.cs` | `57fe4b4cf4f50fa2f82a4868a0d1e58460d450f646a14181558da0b72417f073` |
| `src/RiftReader2.Live/CurrentBuildOrientationCandidateReader.cs` | `8faed1488890b00eb1c28ca959d3d290150553baa7afb7bb9ea9213565e2fe50` |

Independent source research: `riftreader2/docs/validation/physical-orientation-actor-bitcopy-1179-2026-11-21.md`, SHA-256 `d9732f5b176f6c24d260d5e82851eb890a4dcd4f77ac252f3236cad145a252e7`. The previous report used a physical AMD-DESKTOP process and separately sampled matrices about 9.91 seconds apart; its `actorHeadingQualified` flag remained false.

## Usage

In **PowerShell** after independently selecting a running RIFT executable and obtaining the exact PID, .NET UTC process-start ticks, SHA-256 and main-window HWND described in [M1 native read-only instructions](M1_NATIVE_READONLY.md#explicit-pinned-candidate-capture-cli-m1-diagnostic-only):

```powershell
cd C:\work\Rift_Taxi
python -B -m rift_taxi inspect-native-candidate `
    --pid $rift.Id --start-ticks $startTicks `
    --exe-path $exe --sha256 $exeHash `
    --hwnd $hwnd --host $computer `
    --include-matrix-candidate `
    --out .\artifacts\native-matrices-unique.json
```

Reports use the existing `taxi.native-candidate/1` record and an optional `matrixEvidence` member: both 9-word raw arrays, bitwise match flag, separately calculated planar candidate angles (or null), per-matrix status and an explicitly **false** body-heading-qualification flag. The legacy one-shot command without the option does not require matrix values to be readable. `inspect-native-burst` now also offers an explicit `--include-matrix-candidate` flag; ordinary bursts **do not** contain matrix evidence. See [M1 facing signature](M1_FACING_SIGNATURE.md) for matrix-enabled burst and five-phase offline analysis.

**Output files must be new paths**: existing evidence is never overwritten. A successful return only certifies that the expected pinned candidate structure was read without observed inconsistencies in the capture bracket. The on-disk executable SHA does not prove in-memory module bytes, and sequentially acquired values are not atomic.

## Verification and remaining barrier

On LEGION, **132/132 regression tests passed** under Python 3.14.10, including 6 new decoder matrix tests and 3 capture/CLI tests. Fixtures cover both known SHA layouts, exact raw-byte matching, nonplanar and nonfinite matrices, invalid/missing actor selectors, aliasing, concurrent mutations and CLI opt-in behavior. **No RIFT process was running; all matrix values in these tests are synthetic.** The later multi-sample facing-comparison cycle passed **154/154 tests**; it remains candidate-only.

**Next meaningful physical experiment:** record position, player-system yaw and both matrices at one stationary settled posture; compare after a controlled A/D turn with an independently observed visual response, a camera-only negative control, and readback after settling. Repeat on a second heading and after a full process restart before concluding any native number is actionable body heading.
