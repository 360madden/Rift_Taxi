# M1 — Two-heading physical forward-to-matrix alignment (LEGION)

**Monday, November 23, 2026 · 12:36–1:23 PM Eastern**  
**Evidence class:** Two original short **physical RIFT W-only** input/readback experiments at distinct headings, one intervening documented physical A turn, independent source-hashed release logs, real game screenshots and later settled read-only series. **Not a full trajectory, live `LivePose` qualification or autonomous Taxi journey.**

## Most important result

Two W-only physical pulses were admitted against the **same exact game host/PID/process epoch/build/HWND/native owner**. In both, the measured native XZ displacement bearing nearly matched the **actor-matrix planar-angle candidate**.

RIFT source coordinates have **Y up**, so forward motion is assessed in the **X/Z plane**. The source-pinned actor matrix reports an angle from `atan2(m[6],m[0])`; the candidate direction is `(-sin(angle), +cos(angle))` in X/Z. To compare the actual delta, compute `atan2(-deltaX, deltaZ)` in degrees, normalized across ±180°. Using a different axis convention silently reverses signs and invalidates the conclusion.

| Measurement | Physical W #1 | Physical W #2 |
|---|---:|---:|
| Current-build actor-matrix angle **before W** | **+55.708670°** | **−3.490169°** |
| X/Z travel bearing from native candidate delta | **+55.703265°** | **−3.550998°** |
| Travel minus actor matrix | **−0.005404°** | **−0.060829°** |
| Observed native ΔX | −0.528320 | +0.040527 |
| Observed native ΔZ | +0.360352 | +0.653076 |
| XZ displacement (source units) | **0.639512** | **0.654332** |
| OS DOWN→UP | **100.7066 ms** | **101.1698 ms** |
| W down high-bit during hold | Yes | Yes |
| W/A/D sampled UP after release | Yes | Yes |
| External lease reserve/renew/CLEAR/STOP | Yes | Yes |
| Delayed native settled XYZ | Equal to immediately after W | Equal to immediately after W |
| Separate 12-sample post-release readback | One XYZ; 24 W/A/D checks UP | One XYZ; 24 W/A/D checks UP |

**Travel-heading separation: 59.254263°. Matrix-heading separation: 59.198839°. Worst single-pulse residual: 0.060829°.** These values are recomputed and released from the original source receipts by `compare-two-forward-bearings`, not estimated from screenshots.

### Why the player-system scalar is not yet interchangeable

| Phase | W #1 | W #2 |
|---|---:|---:|
| Player-system scalar **before W** | −56.280079° | −0.651579° |
| Scalar **after W** | −55.708672° | +3.490169° |
| Travel residual using **negative scalar before W** | −0.576814° | −4.202577° |
| Travel residual using **negative scalar after W** | −0.005407° | −0.060829° |

In both cases, the scalar **after** W was the negative of the actor-matrix candidate to within tiny numerical tolerance, while the scalar **before** W differed materially. The earlier bounded A/D turns also showed scalar-vs-matrix delta disagreement. This suggests a field-update/interpolation distinction worth researching, **not a proven temporal-lag cause**. Do not select the scalar as an authoritative current body yaw on these receipts.

## Intervening separately admitted A turn

Before the second W pulse, the game was observed on open ground in a **new scene**. A separate Taxi-owned single **A** turn (100 ms requested, **100.7158 ms** observed OS DOWN→UP) recorded:

- Actor-matrix angle **+15.043361° → −3.490169°** (−18.533530°).
- Player-system scalar **−11.604720° → −0.651579°** (+10.953141°).
- Current native XYZ stayed unchanged across the A turn at `[7211.53515625, 871.7744140625, 3026.5029296875]`.
- The later W-only diagnostic's **before** sample matched that XYZ and actor-matrix angle; its settled sample changed to `[7211.57568359375, 871.7744140625, 3027.156005859375]`.
- Exact process/window/owner and external release child were independently qualified on each action. Pre-turn and post-turn screenshots were retained.
- **An unknown interval separates W #1 and this A turn**, and the character's location/orientation changed during that interval. Do not describe all three actions as one uninterrupted closed-loop route or infer exactly what happened in between.

The active non-RIFT foreground window was temporarily replaced only during the bounded observations/actions; the previous foreground was restored using the Windows API afterward. Both interventions returned a successful restore response. No game settings or installed addon files were changed.

## Source-hashed offline comparison and fail-closed regression

New Taxi-owned `rift_taxi/forward_bearing.py` and CLI commands:

- `analyze-forward-bearing`: require a physically executed **W-only** report SHA and separately original child-release audit SHA, check exact game/session/actor, action clock bounds, W-held/key-up states, data arithmetic, release lease ordering and output **candidate-only** travel/matrix/scalar angular differences.
- `compare-two-forward-bearings`: independently validate both input pairs; require distinct sources, exact same process/build/actor/window, correct timestamp order, then report angle diversity and matrix residuals. It uses a **15° diversity / 1° residual** exploratory classification, **not a live control-arming gate**. Failed or insufficient alignment is reported honestly; changed process/owner/chronology or tampered hashes are refused.
- Invalid key, dry-run masquerading as physical, missing SHA, false OS UP, mismatched audit PID, forged yaw/distance, duplicate sources, reversed time, nonfinite values and false live-heading promotion are covered by tests.
- Original source reports, release logs and saved screenshots remain under Git-ignored `artifacts/`. Tracked documentation provides original exact SHA identities; no raw RIFT game data is published to GitHub.

### Exact original locally retained artifacts

| File in `artifacts/` | SHA-256 |
|---|---|
| `m1-W-physical-20261123-1238.json` (W #1) | `fef24dd4ca8d8e0008ec1689b931ef5912d7ca21dfd920aa10028b6d9513a934` |
| `m1-W-physical-release-20261123-1238.jsonl` | `f2418aa87e619a6eb94ff3fa370d50cfeedab7e1e9c5f37505c43f0caf304e7d` |
| `m1-heading-second-pre-scene-20261123-1315.jpg` | `a124f04108c9c8ba552ccf6102a50e208228fa4cf60ce5798f3fb44e8cd7faf8` |
| `m1-second-heading-A-20261123-1316.json` | `51154e181c014c38fddf69787fc4e5be0561cf09a07d1adfd6fa7c36ee418b56` |
| `m1-second-heading-A-release-20261123-1316.jsonl` | `1d286c6416f0aa1b9693900f7ff7dd1a655f6b193ca553b32a12d38d8d38db3a` |
| `m1-second-heading-after-A-20261123-1316.jpg` | `9381d8af2a2fdf7fd78447dc5556c2dfb132ecd3cf15de51c3a5359c7172afac` |
| `m1-second-heading-W-20261123-1318.json` (W #2) | `cfb7044c0ae4b54eddcf796524d5bb07c0e219bf7ca2d0bcc7a58b3724e48707` |
| `m1-second-heading-W-release-20261123-1318.jsonl` | `8a672927559470f23f0087ce963076b506b439d24dcf3dd8c7b7b94ef8fb9599` |
| `m1-second-heading-after-W-20261123-1318.jpg` | `33a4f46a46eb68afaa9124926062e926280d7d801d0f4d79ba51ff940b4c336d` |
| `m1-second-heading-W-post-series-20261123-1320.json` | `88840a6d444d3a928b77469913a0fc8d0bd3bab2ad5d18858851003ca6151478` |
| `m1-second-heading-alignment-20261123-1319.json` (derived) | `74333d8ecfb8945d63747a8a17a17b3fd7b7145989bc48c771b4211fdb926903` |
| `m1-two-heading-comparison-20261123-1321.json` (derived) | `3fd1748ff0682558e74e050a95b79079ab2335de9eaa23528bf2776c29ace6df` |

The first W experiment's original physical-game screenshot and prior independent 12-sample release check are separately documented in [M1_PHYSICAL_W_DISPLACEMENT_LEGION_2026-11-23.md](M1_PHYSICAL_W_DISPLACEMENT_LEGION_2026-11-23.md). The second post-W native series (12 owner-stable samples; median **129.9386 ms** gap) showed **one unique XYZ, one matrix angle, 12/12 position/actor raw-bit matrix matches and 24 W/A/D high-bit snapshots all UP**.

## What this qualifies and what remains open

**Now supported:** Candidate native actor matrix is consistent with physical forward motion **in two materially distinct orientations on one current-build game epoch**, with normal Windows key release and source-hashed child lease evidence. Camera-only orbit previously left that matrix unchanged while visibly changing the on-screen view. This is a substantial body-heading research advancement.

**Still not proven:** native matrix as an authoritative *body yaw* independently of same-process cached XYZ; exact actor/zone (beyond the native owner and reviewed scene); producer-quiet passive position freshness; crash/late-DOWN **game-consumed** input release; sustained W steering, 95% duty, safe corridor adherence or final arrival. Native before/after readings were separated from the OS down/up edges by hundreds of milliseconds, so dividing displacement by hold time is **not a calibrated speed**.

**Production `LivePose.actor_yaw_verified` must remain false and navigation disarmed.** The next shortest M1 path is independent body/yaw and zone semantics, then physical fault-release verification under a separately designed bounded test. Do not expand mapping/UI before M1 closure.

See [the Monday handoff](M1_HANDOFF_2026-11-23.md), [physical camera negative control](M1_PHYSICAL_CAMERA_NEGATIVE_CONTROL_LEGION_2026-11-23.md), [validation gates](VALIDATION.md), and [autonomous execution policy](AUTONOMY_POLICY.md).
