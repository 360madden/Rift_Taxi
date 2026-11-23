# M1 live native candidate acquisition — physical LEGION, November 23, 2026

**Session:** 2026-11-23 ~07:04–07:06 EST · **Machine:** LEGION · **Project:** `C:\work\Rift_Taxi` · **Game:** RIFT physical client, not VM.

## Result

**New Taxi-owned read-only native acquisition succeeded against a running real RIFT process.** This establishes exact-build, owner-checked *candidate* bytes from a physical RIFT process, **not** qualified passive player-position freshness, independently proven actor-facing yaw, movement, or a completed route.

| Pinned target | Observed value |
|---|---|
| Image | `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe` |
| On-disk SHA-256 | `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01` |
| Process ID | `31684` |
| Process start .NET UTC ticks | `639310312490361378` |
| Process start (local) | `2026-11-23 06:47:29.0361378 -05:00` |
| Top-level window HWND | `22022232` (`RIFT`) |
| Selected native self owner key | `239816685251645959` |
| XYZ component candidate | X `7208.7431640625`, Y `871.6995849609375`, Z `3020.64208984375` |
| Player-system `+0x304` yaw candidate | -0.4043150246143341 radians / **-23.165544504129343°** |
| Actor matrix `+0x398` planar candidate | **+23.16615466558538°** |
| Position secondary matrix `+0x94` planar candidate | **+23.16615466558538°** |
| Raw actor vs position matrix | **9/9 identical float32 bit patterns** in each tested sample |
| Native one-shot capture bracket | 0.27248 s for XYZ/yaw; 0.14827 s for matrix-enabled capture |
| Separate burst | **4/4** candidate observations in 1.66548 s |
| Burst observations | No change in XYZ, player-system yaw or either matrix; all four matrix pairs bitwise equal |

The close **negative-sign relationship** between the player-system yaw and matrix-derived angle is an observed candidate correlation at **one stationary orientation**, not a proven body-heading mapping. It must be tested after actual A/D turns, camera-only changes, and W travel on the **same process** with independent game-state evidence before navigation use.

## What happened

1. A fresh OS check identified an already running `rift_x64.exe` on LEGION and independently hashed the on-disk 60,574,536-byte executable. Its SHA exactly matched Taxi's current source-pinned `build-1179` layout.
2. The exact pinned window was **visible but minimized** (`IsIconic=true`). The first, ordinary `inspect-native-candidate` invocation correctly refused it as `pinned window missing`; this was a real failure-to-admit, **not** a memory failure.
3. Using temporary OS foreground/window restoration (no keyboard/mouse game events), a later ordinary Taxi CLI invocation acquired a fresh, complete one-shot candidate. It passed the app's pre/post PID/start/path/hash/HWND/foreground checks.
4. A second, opt-in matrix acquisition on the same process read both source-pinned matrix paths. A **separate 4-sample matrix-enabled burst** re-resolved and checked the owner across each captured sample.
5. In every temporary test, the RIFT window was returned to its original **minimized** state and the previous foreground HWND was restored (reported prior and final HWND `328472`). **No keys were sent; no game memory writes, UI reloads or game restarts occurred.**

The process was not launched by Taxi. These were tests of the existing read-only code and temporary OS window management outside the production Taxi application. The production CLI retains exact foreground requirements and does not auto-restore windows.

## Original evidence, stored locally (ignored artifacts)

The raw reports remain **untracked** under `C:\work\Rift_Taxi\artifacts` and are **not copied into Git**. File names and source SHA-256s:

| Relative path | Original file SHA-256 |
|---|---|
| `artifacts/native-candidate-20261123-0705-p31684.json` | `6dd7fec08a755851faa078b0a30e58d5db1f42fd77c15c2f6eec4c743ec62e84` |
| `artifacts/native-matrix-20261123-0706-p31684.json` | `ceaf3fdde5511f3c1633ee6b6dd002e27f79dfe2892323fdb03974412597a44f` |
| `artifacts/native-matrix-burst-20261123-0706-p31684.json` | `759c6718bd0e1cee0583352d29ca63baf364511fc3b9c556b4ba01080683a1df` |

Verify before interpreting by running `Get-FileHash` in PowerShell against each ignored artifact. The hashes establish file integrity, not authenticity of body-heading semantics. If evidence is later moved or cleaned up, retain its original hash and mark the raw receipt **unavailable**; do not reconstruct plausible raw bytes from the summary table.

## What this does and does not prove

- **Confirmed:** Taxi-owned Python Win32 `ReadProcessMemory` path, process-epoch checks, exact on-disk executable hash pinning, self-entity resolution, current-build component type/backlink checks, field rechecks, and same-player key throughout four burst observations.
- **Confirmed:** Position-secondary and actor 3×3 matrix **raw float32 bytes agreed** for this stationary native observation, reproducing a relationship RR2 had separately observed. This is independent *Taxi code* acquiring the native bytes, **not** an independent game-behavior reference.
- **Not confirmed:** Whether the cached XYZ is passively refreshed as RIFT runs; whether the candidate scalar/matrix is controllable body yaw rather than an internal representation or cached/renderer orientation; whether observations map to a particular zone/floor/character's displayed name; whether any movement command was consumed by the game.
- **Not confirmed:** Loaded in-memory executable module byte hash, atomicity of sequential field reads, full-restart recovery, high-rate tracking, any game-response timing, steering or independent W/A/D key release.

**M1 remains incomplete.** No `LivePose(actor_yaw_verified=True)` can be fabricated from this receipt. Game-response verification is false in every stored original report.

## Next experiments

1. **Independent in-game correlation:** Collect an addon/UI position observation of the same actor while the client is running; compare only after clock and owner binding. Examine camera-only versus A/D turn and measured forward travel. Never infer change from stationary data.
2. **Backend in isolation:** Implement the Taxi-owned standard Windows scan-code W/A/D insertion/release adapter behind the existing session and STOP gate; test with an injected fake OS API. Do not start movement while actor heading/source freshness or independent release supervision is still missing.
3. **Production live acceptance:** After separate qualification, collect a short bounded input + independently newer pose + release + settle receipt; do not describe this candidate-only study as physical M1 acceptance.

## Source boundaries

RiftReader2 and RiftWorld were consulted only as **read-only** source references; permanently read-only Telara Fly was untouched. No dependency on their running services was added to Taxi.
