# M1 — Camera-only negative control: left-mouse orbit

**November 23, 2026 · LEGION**  
**Code status:** bounded diagnostic implemented; **11 focused regression tests pass**. A real physical camera-only orbit was subsequently captured with original screenshots, mouse release audit and native readings. See [physical camera negative control](M1_PHYSICAL_CAMERA_NEGATIVE_CONTROL_LEGION_2026-11-23.md) for independently examined evidence; the diagnostic output itself remains candidate-only.

## Why this experiment matters

The first real A/D pulses changed the actor-matrix angle approximately −17.91°/+18.23°, but the player-system scalar changed by different approximately opposite angles. A short real W input changed native XYZ without changing actor-matrix yaw; that still does not prove an independently correct body-heading reference.

RIFT's documented default **left-mouse drag** orbits the camera around the player, whereas **right mouse** turns/steers the player. See [RIFT control reference](https://theriftrealm.fandom.com/wiki/Controls_%26_Key_Bindings) and [official game camera settings](https://support.gamigo.com/en/support/solutions/articles/201000105440-camera-settings-in-rift). Current user keybindings and game semantics remain independent observations: controls may be remapped, and successful OS injection does **not** establish a camera-only effect.

## Separate, bounded diagnostic (never navigation)

`python -B -m rift_taxi probe-camera-orbit`:

- **Dry-run by default**; only `--execute-physical` permits OS mouse injection.
- Requires fully pinned current **LEGION/physical game** PID/start epoch/path/SHA/HWND/foreground, exact owner-key, independently inspected current real-game screenshot SHA, new release audit/output paths, and a **reviewed clear-ground cursor point** expressed as `--cursor-x-fraction` and `--cursor-y-fraction`.
- Uses **left mouse only**, 30–90 pixels horizontal movement, an 80–160 ms hold; never W/A/D or right mouse. Avoids action bars, NPCs, chat boxes, buttons and physical click-to-move surfaces by requiring a reviewed point. If the actual game configuration maps left click to movement or the scene is unsafe, refuse physical execution.
- Independent Windows release child reserves `MOUSE_LEFT` before DOWN, renews the lease, attempts UP on TTL/parent-disconnect/STOP, and retains reservation until parent UP is OS-accepted. Parent always attempts UP and restores the original cursor position in `finally`; background release is bounded, not infallible.
- Rechecks current exact foreground process and same native self-owner, ensures W/A/D are not held, checks left mouse not already down, then captures native XYZ, player-system scalar and actor/position matrix candidate before/after and ~200 ms after release.
- All output semantics are **candidate-only**. The probe explicitly marks `gameCameraOrbitIndependentlyVerified=false`, `actorHeadingQualified=false` and `passiveXYZFreshnessQualified=false`. Real before/after screen captures must be independently examined.
- The production W/A/D runtime remains **disarmed**. Mouse code is isolated to diagnostics and emergency mouse-up, not a general movement controller.

## Correct qualification sequence

1. Confirm actual current game window, on-screen gameplay and a visibly clear cursor point; preserve original screenshot/source hash and live process/actor pin. Validate that click-to-move is disabled or no left-click movement is expected.
2. Run one bounded mouse gesture with new audit/JSON paths. Verify OS mouse DOWN/move/UP acceptance and independent release ledger.
3. Capture a new actual game image and compare its orientation with the before image while checking whether the player position/character body actually changed. Native candidate scalar/matrix values are *not* sufficient by themselves.
4. If visual camera changed while player body did not, and native angle fields remained fixed/changed in a source-backed way, classify only what the synchronized receipts support. A camera negative control is not an authoritative body-yaw calibration without independent reference.
5. If input fails or the screenshot is ambiguous, keep the experiment unqualified and do not repeat physical gestures without fixing the measured cause.

## Reproduction — dry-run example only

```powershell
python -B -m rift_taxi probe-camera-orbit --pid <CURRENT_PID> --start-ticks <CURRENT_TICKS> --exe-path "C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe" --sha256 <CURRENT_SHA256> --hwnd <CURRENT_HWND> --host LEGION --owner-key <CURRENT_OWNER> --drag-px 60 --hold-ms 100 --cursor-x-fraction 0.36 --cursor-y-fraction 0.45 --audit artifacts\camera-release.jsonl --out artifacts\camera-report.json
```

Actual physical use additionally requires the reviewed fresh scene SHA and the explicit physical flag, with operator-approved scene and cursor coordinates; never copy historic PID/actor values blindly.

Related: [physical A/D](M1_PHYSICAL_AD_TURN_CALIBRATION_2026-11-23.md), [physical W](M1_PHYSICAL_W_DISPLACEMENT_LEGION_2026-11-23.md), [full M1 handoff](M1_HANDOFF_2026-11-23.md) and [autonomous execution](AUTONOMY_POLICY.md).
