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
- **98/98 total regression tests passed**, Python 3.14, without reading or moving RIFT.

## Not yet proved or implemented

- No fresh **RIFT-native** position/actor-yaw sample from this Taxi code, no current game PID/actor binding, no source-clock qualification, and no demonstrated fresh passive XYZ.
- No reliable camera-vs-body yaw determination, no verified native game response, no Windows movement input and no independent key-release.
- No GUI, startup scanner, automatic process discovery, journey execution or release-ready distribution.
- No consumer contract from `PositionFacingCandidate` to `HeldInputController.LivePose`. This remains intentionally blocked until native field semantics and freshness are independently demonstrated.

**Next M1 experiment:** on a physical, explicitly identified current-build client, confirm the exact on-disk SHA, PID/process epoch/HWND, current actor and zone; run a **read-only** bounded candidate capture with no W/A/D input; correlate XYZ/yaw with independent game-state evidence and the same actor before authorizing any motion.
