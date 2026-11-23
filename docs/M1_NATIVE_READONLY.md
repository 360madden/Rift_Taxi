# M1 native read-only memory and candidate decoding — November 23, 2026

**Repository:** `C:\work\Rift_Taxi` on LEGION · **Status:** implemented + tested, not yet a qualified RIFT actor pose or any live movement.

## What this adds

Two **Taxi-owned** Python standard-library modules:

- `rift_taxi/native_memory.py` provides a pinned, bounded, **read-only** 64-bit Win32 process-memory session. It requires an explicit PID, process-start timestamp, exact executable path and SHA-256. On open, it checks identity, on-disk executable bytes and the main module path/base/size. Each 1–4096-byte read checks the pinned epoch/path before and after and refuses partial reads. There is no write/input/process discovery API.
- `rift_taxi/native_candidate.py` interprets source-verified native player table → entity → position component → XYZ and player-system yaw as **candidates only**. It re-resolves owner pointers for every acquisition, compares anchored bytes after capture, rejects inconsistent owner/table/component fields, and uses exact-build selector and component-vtable checks. It does not create `LivePose` or set actor-yaw/freshness qualification.

The first module was physically smoke-tested against a **known byte buffer in the test runner's own Python process on LEGION**. No RIFT client was launched, read or moved.

## Source provenance: RR2 audited read-only

The Taxi implementation follows narrow, reviewed RR2 research. Files were read from `C:\work\riftreader2`, without modifying that repository:

| RR2 reference file | SHA-256 of surveyed source |
|---|---|
| `src/RiftReader2.Live/CurrentBuildPlayerLookup.cs` | `e1ad039f1592edfe56c194ecb1f5792a30b66cc28783fe799372bdf1be992165` |
| `src/RiftReader2.Live/CurrentBuildPositionSampleCommand.cs` | `6a2d0d8240f922b519b8cfff669f5f3086e1bfd7d7b69cd0018fb9064311d895` |
| `src/RiftReader2.Live/CurrentBuildFacingCandidateReader.cs` | `9016b7ff3395efbd06c597779b52bce84589a2680b9677114034bb6466766b05` |
| `src/RiftReader2.Live/WindowsNativeMemorySession.cs` | `d1dce81644909c901f8c5b8da52968788ef77de3144119537246250ddb47796d` |

Supported **exact historical executable SHA-256 values**, as listed by those RR2 sources:
- `1935A05C9DB6D468E34E0055014A4A99C1B5AFCEB1695884E24600F5C20A4BE8`
- `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01`

The presence of a supported hash in the code **does not mean** the currently installed RIFT executable matches it. Any other build is refused before native field reads; there is no offset fallback, signature guess or automatic patch adaptation.

## Candidate interpretation

The source-pinned native chain resolves, on each invocation:

1. Main-module-relative player-system pointer and nonzero player key.
2. Exact-build manager/table/bucket for the same player key, using the signed 32-bit table hash.
3. Owner-anchored entity and indexed position component, with required vtable and entity backlink.
4. Position component `+0x48` cached XYZ and player-system `+0x304` yaw **candidate**, with a player-system entity backlink.
5. Reread and compare captured pointers, owner bytes, component bytes and yaw; any disagreement aborts the candidate.

Returns `PositionFacingCandidate` with `actor_heading_qualified=False` and `passive_position_freshness_qualified=False`. These are **not automatically promoted** even if multiple samples appear stable. The yaw may be player-system orientation rather than independently established body heading, and cached XYZ may not be passively refreshed by the game. Sequential reads cannot exclude ABA, and checking bytes on disk cannot verify the loaded game module's bytes.

The Win32 process session does not yet require a live window/character/focus binding; the separate `win32_identity.py` inspector provides OS desktop qualification. The future live observer must correlate both to a current RIFT actor and a game build.

## Tests and evidence

Run from PowerShell in `C:\work\Rift_Taxi`:

```powershell
python -B -m unittest discover -s tests -p test_native_memory.py -v
python -B -m unittest discover -s tests -p test_native_candidate.py -v
python -B -m unittest discover -s tests -v
```

**November 23, 2026 on LEGION:**
- 11 native-memory tests, including actual Windows read-only self-process buffer access.
- 13 candidate-decoder tests using deliberately constructed, bounded **synthetic memory fixtures**: two recognized source hashes, owner/backlink/vtable validation, chain cycles, signed table hashing, nonfinite data, changing payloads, wrong build and malformed module.
- **98/98 regression tests passed** at this initial decoder slice; subsequently **110/110** after the opt-in capture CLI, Python 3.14, without reading or moving RIFT.

## Not yet proved or implemented

- No fresh **RIFT-native** position/actor-yaw sample from this Taxi code, no current game PID/actor binding, no source-clock qualification, and no demonstrated fresh passive XYZ.
- No reliable camera-vs-body yaw determination, no verified native game response, no Windows movement input and no independent key-release.
- No GUI, startup scanner, automatic process discovery, journey execution or release-ready distribution.
- No consumer contract from `PositionFacingCandidate` to `HeldInputController.LivePose`. This remains intentionally blocked until native field semantics and freshness are independently demonstrated.

**Next M1 experiment:** on a physical, explicitly identified current-build client, confirm the exact on-disk SHA, PID/process epoch/HWND, current actor and zone; run a **read-only** bounded candidate capture with no W/A/D input; correlate XYZ/yaw with independent game-state evidence and the same actor before authorizing any motion.

## Explicit pinned candidate capture CLI (M1 diagnostic only)

`rift_taxi/native_capture.py` and the `inspect-native-candidate` command add a **single opt-in, read-only observation**. It requires all of the following caller-supplied values: PID, .NET UTC process-start ticks, absolute executable path, trusted on-disk SHA-256, HWND, and machine name. There is **no automatic process selection** and no key injection. A fresh `win32_identity.inspect_desktop` check occurs **before and after** the native read; if identity, foreground, source timestamps, or capture duration disagree, the report is refused.

On an explicitly verified physical Windows RIFT session, use **PowerShell in the Taxi repository**:

```powershell
cd C:\work\Rift_Taxi

# Review candidates only. Select an exact intended PID yourself.
Get-Process | Where-Object { $_.ProcessName -match 'rift' } |
    Select-Object Id, ProcessName, Path, StartTime, MainWindowHandle

# Enter the verified RIFT game PID at the prompt; do not use stale values.
$rift = Get-Process -Id (Read-Host 'Verified RIFT game PID')
$exe = $rift.Path
$exeHash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
$startTicks = $rift.StartTime.ToUniversalTime().Ticks
$hwnd = $rift.MainWindowHandle
$computer = $env:COMPUTERNAME

# Only after independently verifying the exact process/build/window:
python -B -m rift_taxi inspect-native-candidate `
    --pid $rift.Id --start-ticks $startTicks `
    --exe-path $exe --sha256 $exeHash `
    --hwnd $hwnd --host $computer `
    --start-delay-seconds 5 `
    --out .\artifacts\native-candidate-unique.json
```

Use a **new report filename each time**: the command refuses overwriting existing evidence **before** beginning native capture. The optional `--start-delay-seconds` (0–15) gives time to return the RIFT window to the foreground after launching from PowerShell; it does not activate/focus RIFT automatically, and foreground verification still occurs before and after native reads. If no RIFT process exists, if focus/window identity changes, if the executable does not match one of the two pinned historical builds, or if native bytes are inconsistent, the command fails without producing a completed report. Successful capture still means **candidate only**; there is no qualified body heading, proven passive XYZ freshness, or physical game-response proof.

On November 23, the `test_native_capture.py` suite added **12 synthetic bracketing/CLI tests** (pre/post owner continuity, foreground, process epoch, timing, new output, and failure paths); **110/110 tests passed** at that stage. The CLI was **not executed against RIFT** because no matching client process was running on LEGION at that check.

## Repeated read-only candidate burst

`rift_taxi/native_burst.py` adds the opt-in `inspect-native-burst` command. This takes **2–8 independent full pinned read-only captures**, each of which checks the exact game PID/start epoch/executable hash/HWND before and after its native memory read. Any single failed capture, changed player-key candidate, invalid/nonadvancing timestamp, changed process or foreground, or total-duration overrun aborts the burst **without publishing a completed report**.

It compares the X/Z/3D XYZ candidate displacements, candidate player-system yaw (with degree wraparound), and whether any **intermediate** sample differs. None of those comparisons establishes actual RIFT character movement, passive XYZ freshness, or actor body heading; the report explicitly sets those verification flags to false.

**PowerShell example**, after obtaining the explicit process pins in the preceding section:

```powershell
cd C:\work\Rift_Taxi
python -B -m rift_taxi inspect-native-burst `
    --pid $rift.Id --start-ticks $startTicks `
    --exe-path $exe --sha256 $exeHash `
    --hwnd $hwnd --host $computer `
    --samples 4 --interval-ms 250 `
    --start-delay-seconds 5 `
    --out .\artifacts\native-burst-unique.json
```

Use a new output path. The requested interval is a **minimum delay after each capture**, not a promised sampling rate; executable hashing and identity checks take additional time. The default total budget is 30 seconds. The command **does not start, focus, or move the game**.

**Validation:** 13 new deterministic burst tests passed; the full regression suite passed **123/123 tests** on LEGION, November 23, 2026. All burst data in these tests are injected synthetic candidate reports. Actual RIFT passive freshness and body-yaw qualification remain unresolved.

## Installed game build reference (LEGION; read-only check)

On November 23, 2026, the installed `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` was found on LEGION. It is **60,574,536 bytes**, last modified **November 20, 2026, 12:34:40 UTC**, and its **on-disk SHA-256** was:

`DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01`

That hash exactly matches the **updated historical executable layout** in the source-pinned decoder, but this does **not** establish that the client is currently running, that loaded module bytes are identical, that the memory offsets are still behaving as expected in-game, or that the candidate values have independently qualified gameplay semantics. Rehash the executable and rebind the exact session before each actual live experiment.

During the **earlier** pre-launch check, no RIFT process matched and no game memory was read. A **later live LEGION process was found** and successfully captured using Taxi's native read-only code. See [physical native evidence, exact process identity and source-hashed receipts](M1_LIVE_NATIVE_LEGION_2026-11-23.md). No game input or process-memory writes occurred.

## Optional same-owner actor/position matrix diagnostic

The one-shot `inspect-native-candidate` command now accepts `--include-matrix-candidate`. It reads source-pinned position-secondary and actor matrices from the same owner, compares their 9 original float32 bit patterns, and reports separate structural planar-angle candidates without qualifying body yaw. The default one-shot and multi-sample XYZ/yaw captures still omit matrix evidence, but bursts can explicitly opt in with the same flag. Details, source file hashes and initial 132-test evidence: [M1 matrix candidate comparison](M1_MATRIX_CANDIDATE.md). Matrix-enabled bursts and five-phase analysis passed 154/154 tests: [M1 facing signature](M1_FACING_SIGNATURE.md).

## Optional position-cache refresh-guard diagnostics

The one-shot and burst commands additionally accept `--include-refresh-guard-candidate`. Taxi co-samples QWORD(position component `+0x100`) and BYTE(`+0x108`) from the **same already captured 0x110 bytes** as XYZ; no native getter or extra process read is introduced. The raw bytes indicate whether the two source-pinned *conditional* update routes would be guard-eligible, not whether any writer ran or the source is passively fresh. On a physical LEGION current-build RIFT process, both fields were zero in one capture and four samples over 1.68 seconds. The original evidence hashes and scope are in [M1 live XYZ refresh guard study](M1_LIVE_XYZ_REFRESH_GUARDS_LEGION_2026-11-23.md). The full suite then passed 200/200 tests. `Inspect.Unit.Detail` may itself refresh the cache, so future addon/native comparisons must retain exact acquisition order and cannot be called passive proof by agreement alone.

## Optional actor-world translation and offline pair comparison

`inspect-native-candidate` also accepts `--include-actor-translation-candidate`, a bounded same-owner actor model/world translation diagnostic. It uses the documented relation `actor+0x3BC = position secondary XYZ + actor+0x4F8 + actor+0x770`, records source residuals and conditionally reads the normal renderer translation **only** on the source-pinned normal branch. It never follows the unqualified alternate renderer reference. The independent `compare-native-candidates` CLI checks two original source-hashed same-process/owner reports for numerical XYZ/yaw/matrix/guard changes, never for proven game actions or position freshness. The live LEGION follow-up found a ~0.0000024-unit actor reconstruction residual and changed native values over 24 minutes under the same process epoch, with both sampled refresh guards still zero. See [M1 actor-world changed-state study](M1_ACTOR_TRANSLATION_CHANGED_STATE_LEGION_2026-11-23.md). The later full suite passed **221/221 tests**.
