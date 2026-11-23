# M1 — Taxi-owned Win32 W/A/D scan-code backend

**November 23, 2026 · LEGION · Python 3.14.10**

## Delivered — adapter implementation, not physical input acceptance

`rift_taxi/win32_input.py` implements the existing `KeyBackend.write_key(key, is_down)` protocol using a standard-library Windows `SendInput` scan-code packet. It can be called by the existing `HeldInputController` after **explicit, same-session arming**. It is not exposed as a Taxi CLI command, does not launch RIFT, and **did not send any movement keys during this development cycle**.

This module closes an M1 *code implementation* gap for OS insertion. The later [separate-process release-supervisor prototype](M1_RELEASE_SUPERVISOR.md) adds lease/EOF/mutex tests, **not** physical game-release or crash-proof guarantees. Actor/zone qualification and game-observed input still remain open.

### Input ABI and supported keys

| Key | Set 1 scan code | Key-down flags | Key-up flags |
|---|---:|---|---|
| W | `0x11` | `KEYEVENTF_SCANCODE (0x0008)` | `SCANCODE | KEYUP (0x000A)` |
| A | `0x1E` | same | same + KEYUP |
| D | `0x20` | same | same + KEYUP |

The Win32 `INPUT` / `KEYBDINPUT` sizes are checked against the expected 64-bit Windows ABI (40 and 24 bytes). Invalid keys, lowercase names, unknown key types and nonboolean edges are refused. No mouse, targeting, teleport or game-memory-write functionality is included.

### Admission and release model

- **Disarmed by default.** Constructing `WindowsScanKeyBackend` and `Win32ScanSender` does not insert input.
- **Explicit `arm(LivePose)`:** requires independently verified actor yaw, same host/process epoch/executable SHA/HWND/actor/zone session binding, foreground status and a current same-clock pose. The constructor cannot arm itself, and the raw `PositionFacingCandidate` captured on LEGION is **not** an authorized `LivePose`.
- **Full initial identity admission** uses Taxi's read-only `inspect_desktop` (including the on-disk executable SHA). A subsequent quick OS identity/foreground check prevents ordinary W/A/D **DOWN** if the process changed or focus was lost. The per-edge path does not rehash the 60 MB executable on every key event.
- **Uncertainty before insertion:** a key is marked potentially held before calling native SendInput, so rejected/exceptional key-downs require a later best-effort key-up rather than being silently forgotten.
- **Key-up after foreground loss:** releasing an uncertain key is allowed even if the game is no longer foreground. Unsuccessful key-up is retained as uncertainty for retry. `release_all()` and `disarm()` are available separately from the steering gate.
- **No direct repeated DOWN:** duplicate presses of an unresolved held key disarm further DOWN attempts.
- **Controller integration:** `HeldInputController` still owns desired W/A/D transitions, key release ordering, watchdog, and latched STOP. Input-source stale or identity failures force STOP. The game's response is not inferred from a SendInput insertion return value.

The normal Windows `SendInput` call is a best-effort **OS insertion**; it cannot guarantee RIFT consumed an event, that the foreground did not change between last check and input, or that a background key-up reached game logic. This implementation intentionally does not claim otherwise.

### Testing evidence

**15 scan-code backend regression tests passed on LEGION on November 23** (169/169 at that slice); the later external-supervisor cycle brought the suite to **187/187**. The tests inject fake process/window probes and a fake sender; they cover scan-code packet/ABI layout, disarmed refusal, qualified-pose admission, focus loss, PID epoch/path/host/window mismatch, stopped/failed insertion uncertainty, key-up retries, disarm, duplicate press rejection, and integration with the actual driver-neutral `HeldInputController`. The sender object was constructed using Win32 without invoking `SendInput`.

Run from **PowerShell** in `C:\work\Rift_Taxi`:

```powershell
python -B -m unittest discover -s tests -p test_win32_input.py -v
python -B -m unittest discover -s tests -v
```

The separate [real native capture handoff](M1_LIVE_NATIVE_LEGION_2026-11-23.md) documents a successful read-only physical RIFT capture; it is **not** evidence of this input backend inserting or releasing a physical game key.

## Missing before M1 physical acceptance

1. Qualify same-actor/zone **fresh** native XYZ and independent body facing on the physical build. The live current-build candidate capture exists, but its `actorHeadingQualified` and `passivePositionFreshnessQualified` flags are still **false**. The backend must remain disarmed until that prerequisite is met.
2. Validate the new **separate-process release-only prototype** against actual game key consumption, focus-loss and blocked/late native SendInput behaviors. A synthetic parent-crash and delayed-DOWN compensation test now pass, but physical outcomes remain unknown. It is independent of the steering thread, but **cannot yet guarantee actual game release**.
3. Verify the new **cooperative same-game-epoch Windows mutex** under packaged deployment and prevent competing external applications from taking ownership where practicable.
4. Execute an approved, short physical clear-ground calibration on one pinned, freshly verified game process. Preserve exact input down/up timing, foreground/identity readback, independent game visual/XYZ/yaw response, and post-release settled pose. An inserted-key return value alone does not pass.

## Source boundary

Windows scan-code layout and release caution were reviewed against RR2's `src/RiftReader2.Live/Control/WindowsControlDesktop.cs` (source SHA-256 `7152c6db5222fe1bdc6ca2c8a7f817a043ccdea0f534f6f6dc2617ba4bbdd83e`). Taxi's implementation is separate Python code; RR2, RiftWorld and permanently read-only Telara Fly were not modified or linked as runtime dependencies.
