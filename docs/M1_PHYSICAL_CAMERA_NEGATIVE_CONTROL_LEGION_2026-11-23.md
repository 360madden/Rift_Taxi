# M1 — Physical camera-only negative control on LEGION

**November 23, 2026 · 12:52–12:55 PM Eastern**  
**Result:** A **real, bounded left-mouse-only orbit** was injected, its own independent Windows mouse-up release child acknowledged/cleared, and the actual RIFT view changed while same-owner native XYZ, player-system scalar yaw and actor matrix angle stayed constant. This is **strong negative-control evidence against interpreting either native angle as freely orbiting camera yaw**. It is **not** authoritative proof of body-facing yaw, persistent position freshness, or game-consumed release under failure.

## Exact game and scope

- Host: **LEGION**, physical RIFT process (no VM); executable `C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe`.
- On-disk executable SHA-256: `DF954B798331E18359BE62A31CC74B49FC3F50B87385EBB080A5448256322C01`.
- PID `424`, creation epoch `639310421805307472` .NET UTC ticks, HWND `1968794`, foreground admission true.
- Exact native current self-owner candidate `239816685251645959`; same owner before/after/settled and later time series.
- Gameplay image: open ground by healer/wagon, not a menu; verified a safe clear-ground left-click target at screen fractions `X=0.36, Y=0.45`. Click-to-move settings were not independently inspected in this run; **no native position change** was observed.
- RIFT's normal left-mouse drag orbits the camera; right-mouse steering was expressly forbidden. [Game control description](https://theriftrealm.fandom.com/wiki/Controls_%26_Key_Bindings). The input mapping is a research premise, independently supported by the observed before/after world images, not a blind claim that any mouse gesture must mean camera-only.

## Physical input and native measurements

| Measurement | Actual result |
|---|---|
| Command | `probe-camera-orbit --execute-physical` (diagnostic only) |
| Left-mouse request | 60 pixels horizontal in 3 accepted move packets, 100 ms requested hold |
| Monotonic DOWN → UP | **107.3592 ms** |
| OS left DOWN / UP accepted | **Yes / Yes** |
| Independent release child | MOUSE_LEFT reserve, renew, CLEAR, STOP acknowledged |
| User cursor | Original screen position restored |
| W/A/D emitted by Taxi | None |
| Native XYZ before / after / after-delay | **Identical** `[7209.39794921875, 871.758544921875, 3024.7236328125]` |
| Native player-system scalar bearing | **−55.7086723613°** before, after and settled |
| Native actor/position matrix planar angle | **+55.7086696982°** before, after and settled |
| Same-owner native candidate delta XYZ / scalar / matrix | **0 / 0° / 0°** |
| Actual window image | **Visible world-view framing changed** while same character was still in position |
| Independently qualified body-heading field | **Not yet** |
| Physically qualified crash-recovery release | **Not yet** |

The screenshots were captured with a read-only Windows `CopyFromScreen` fallback because the desktop screenshot endpoint returned `IO_ERROR`. They are real game-window frames, not generated images. Independent visual inspection found the character near the same position while the wagon, background and nearby characters shifted relative to the viewport after the left-mouse drag.

As a reproducible *coarse image difference check*, 760-wide saved JPEG frames were sampled on a world region (screen sample X 80..700, Y 32..270, stride 8): **815 of 2,340** sample positions had RGB absolute-sum change ≥55 (**34.83%**); average absolute RGB-sum difference was **73.34**. This verifies material scene-image change, but the metric itself does **not** prove all changed pixels are due to camera motion versus animation.

The diagnostic's JSON deliberately says `gameCameraOrbitIndependentlyVerified=false` and `cameraOnlyVerified=false` because it cannot inspect saved screenshots itself. **This handoff** adds external before/after image review. No `LivePose.actor_yaw_verified` flag was promoted.

## Separate post-release readback

A separate physical, read-only `observe-native-series` captured **12** additional owner-pinned samples at median gap **130.4352 ms** after the drag:

- **One unique XYZ** across 12 samples (same as pre/post gesture).
- **One native actor-matrix angle** across all samples.
- **24 sampled W/A/D snapshots**, all UP.
- Separate Windows left-mouse, right-mouse, W/A/D read-only checks found all buttons/keys UP.
- The producer is not known to be API-quiet. Installed Telemetry addon `Inspect.Unit.Detail` polls may refresh cached native XYZ; stationary agreement is not passive freshness qualification.

## Retained source receipts (ignored `artifacts/` directory)

| Local artifact | Exact SHA-256 |
|---|---|
| `m1-camera-before-20261123-1252.jpg` | `2D78A8C187A104DDFF3962B45081A03916150BE149254DC3B300D2B3CA6F4710` |
| `m1-camera-native-before-20261123-1252.json` | `4552f903c3bb350ebc4d4cf623f8e719c248155e3b8d246fbfe7d18d8eb024e8` |
| `m1-camera-orbit-physical-20261123-1253.json` | `907ca4f0357f715658c8d037032b44215d5c31db3189a35be59a034e6651ccdd` |
| `m1-camera-orbit-release-20261123-1253.jsonl` | `0dda76c995fe893bcf8f6d824081259ad24710a49d100a2fc2b09bc619583920` |
| `m1-camera-after-20261123-1253.jpg` | `7A1634EC081FC9D4DE6B54A2037827890D32ADAD0AED0B3C2D554B4C715B35D3` |
| `m1-camera-postrelease-series-20261123-1254.json` | `b41e9718aa20cc02b4f7de12c75c77ed846a7f255900f4065cdc3d73b837c96a` |

## Interpretation and next work

**Supported:** Controlled left drag produced a different on-screen camera/world composition **without** changes in the current same-owner XYZ, scalar yaw or actor-matrix angle candidates. This helps separate those native fields from orbit-camera orientation.

**Still unqualified:** Absolute body heading, body-versus-movement-bearing semantics, actual native writer/passive freshness, exact live actor/zone, game-consumed release under parent/child crash, complete M1 motion controller, and any autonomous destination arrival. Short A/D body-turn tests still show different scalar/matrix delta magnitudes. No single field can be promoted on this experiment alone.

Next focus should be **independently qualified actual body-heading reference**, then robust physical STOP/fault proof; do not repeat camera drags solely to generate more samples. The production controller remains **disarmed**.

See [camera diagnostic source boundary](M1_CAMERA_ONLY_ORBIT_PROBE_2026-11-23.md), [physical A/D turn data](M1_PHYSICAL_AD_TURN_CALIBRATION_2026-11-23.md), [physical W displacement](M1_PHYSICAL_W_DISPLACEMENT_LEGION_2026-11-23.md) and [M1 handoff](M1_HANDOFF_2026-11-23.md).
