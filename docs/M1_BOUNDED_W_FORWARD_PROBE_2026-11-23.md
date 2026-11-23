# M1 — Bounded W-only forward calibration: implementation and validation

**November 23, 2026 · LEGION**  
**Evidence class at this document's creation:** implementation + injected-sender regression only. **Subsequently exercised physically** on November 23; see [original 100 ms W-only physical receipts](M1_PHYSICAL_W_DISPLACEMENT_LEGION_2026-11-23.md). The present document explains the implemented safety boundary.

## Purpose

The existing physical A/D turn experiment showed scene rotation and native angle changes, but never changed player XYZ. A separate *single forward pulse* diagnostic is required to ask whether the same owner's XYZ candidates respond to controlled forward travel, and whether a later read stays settled after key-up. This is **not** autonomous navigation, a qualified body heading, proof of passive native data freshness, or proof of game-consumed STOP.

## Implemented, fail-closed boundary

- `python -B -m rift_taxi probe-w-forward` is **dry-run by default**. Only `--execute-physical` opts into actual W injection.
- The diagnostic accepts **W only**, one **60–160 ms** hold, a fully pinned host/PID/process-start/executable path/SHA/window, and the exact currently read native self-owner key. It never steers, repeats a pulse or runs a route.
- Physical mode also requires the SHA-256 of an **independently reviewed current clear-ground game screenshot**. The function verifies the receipt format and cannot inspect the picture or establish safety from that hash alone. An operator must verify scene suitability before enabling physical mode.
- Exact foreground OS identity and same-owner native candidate observations are checked before action, after release and after a further **200 ms** delay. Any owner/session change rejects the report. Native XYZ/angles remain **candidate-only**.
- The external Windows release child ACKs the W reservation **before DOWN** and the W path renews/checks that lease immediately before attempting DOWN. A 0.6-second lease, parent's unconditional UP attempt, independent STOP/expiry and all-W/A/D-UP high-bit checks bound release uncertainty. OS SendInput acceptance is not game input consumption; the child can also fail.
- Original reports and child audit logs must use **new** paths. The JSON includes immediate XYZ difference, XZ planar distance and the after-delay XYZ candidate; it explicitly marks heading, passive freshness, game motion and game-consumed release **unverified**.
- The old `probe-ad-turn` wrapper **still refuses W**. The production movement backend remains disarmed.

## Test qualification

New focused tests use fake senders, fake native snapshots, an expired release lease, injected DOWN/UP failure and a real Windows release child in **dry-run only**. No test transmits physical RIFT movement. Before first physical use, obtain an independently reviewed *fresh* scene, exact foreground game/actor/zone checks and a release plan. If those are unavailable, leave the diagnostic dry-run and keep collecting read-only evidence.

## CLI example — dry-run only

```powershell
python -B -m rift_taxi probe-w-forward --pid <CURRENT_PID> --start-ticks <CURRENT_TICKS> --exe-path "C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe" --sha256 <CURRENT_SHA256> --hwnd <CURRENT_HWND> --host LEGION --owner-key <CURRENT_OWNER_KEY> --hold-ms 100 --audit artifacts\w-probe-release.jsonl --out artifacts\w-probe.json
```

The placeholders must be filled from a single fresh verified session. No `--execute-physical` is present in this example.

## Remaining gates

1. Camera-only rotation negative control to separate scene yaw from player body yaw.
2. Repeat one physical W test with stronger independent actor/zone proof, post-release key-readback and a synchronized scene/pose timeline. An initial 100 ms live pulse and stable later key/XYZ observations are now source-hashed in the physical handoff.
3. Capture source-hashed before/action/after/release/post-settle receipts and corroborating game frames; compare against addon poll activity to avoid false passive-freshness claims.
4. Physically test crash/late-DOWN independent release, without assuming the dry-run simulation proves it.
5. Only then consider promoting an accepted live pose and an M2 straight-route experiment.

See [physical A/D calibration](M1_PHYSICAL_AD_TURN_CALIBRATION_2026-11-23.md), [validation acceptance](VALIDATION.md) and [AI-first autonomous development policy](AUTONOMY_POLICY.md).
