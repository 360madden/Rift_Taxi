# M1 driver-neutral control boundary — November 23, 2026

**Project:** Rift_Taxi on LEGION · **Status:** implemented and offline-tested protocol/gate, **NOT** a working RIFT input driver or current-build live pose reader.

## Delivered

- `rift_taxi/control.py` introduces immutable `SessionBinding` and `LivePose` contracts, a `KeyBackend` protocol, `KeyEdge` audit events, `ControlStatus`, and `HeldInputController`.
- The session binding retains **host, PID, process-start ticks, executable SHA-256, foreground window handle, player/actor ID and zone**. A different client, process epoch, character or zone is a different identity.
- The live-pose contract requires a finite XYZ tuple, finite actor yaw, **explicit actor-yaw qualification**, foreground verification, monotonic in-process observation time, and an advancing sample sequence/timestamp. No missing yaw is silently converted to zero.
- `apply({W,A,D}, fresh_pose)` computes held-key transitions. It releases obsolete turn input **before** pressing a conflicting direction; W stays held when only the steering direction changes. A+D simultaneously is rejected.
- STOP is **latched** and cannot silently rearm the same controller. `stop()` retries any still-unaccepted releases. An input-failure, invalid request, lost foreground, missing/old pose, identity mismatch or impossible clock sequence causes a STOP and attempted release.
- A watchdog **thread independent of the steering call loop** checks pose age and finite input lease expiration. It attempts release without requiring another `apply()` call. `check_expiry()` offers a deterministic equivalent for seeded tests.
- Driver responses and input edges are recorded separately from physical game-state observation. `game_response_verified` is **always false** in this module.

## What the test results prove

Run on LEGION in PowerShell from `C:\work\Rift_Taxi`:

```powershell
python -B -m unittest discover -s tests -v
```

**63/63 offline regression tests passed on November 23, 2026 (Python 3.14).** Of these, **29** new control-gate tests cover forward-key continuity across turn changes, A/D reversal ordering, STOP/retry, worker-initiated release, expiry ordering, exact session binding, stale/duplicate/out-of-order source data, invalid key sets, immutable pose coordinates, and injected backend faults.

Tests use an inert `RecordingBackend`. No OS input is inserted; no RIFT client is opened, moved or queried; no new XYZ/yaw evidence is collected. Backend acceptance means only **test driver acceptance**, not a game-observed key transition or proof of movement.

## Explicit safety/implementation gaps

| Boundary | Present | Still required for live M1 |
|---|---|---|
| Same-client process/window/player binding | Validated values and exact equality | Discover and independently verify current RIFT build/PID/start/window/actor/zone |
| Pose freshness/yaw | Same-clock sequence, timestamp and qualification gating | Taxi-owned native Win32 read-only acquisition; establish actor-facing source and true clock alignment |
| Held W/A/D | Driver-neutral, sequential edge state and audit receipts | Taxi-owned native Windows backend, bounded calls, exact foreground ownership and physical calibration |
| STOP and timeout | Latched STOP, daemon watchdog and accepted-UP accounting | Independently supervised release even if the native backend blocks; OS/game post-release readback |
| Exclusive ownership | Single in-process lock | Cross-process actuator-owner arbitration and safe crash/restart behavior |
| Verification | 29 fake-driver tests plus historical/offline suite | Read actual observed game response and fresh independently settled final pose |
| Navigation | Synthetic Pure Pursuit preview | Calibrated closed-loop trajectory controller and verified corridor |

**Critical distinction:** a Python watchdog cannot guarantee release when a foreign driver call hangs under the shared controller lock, when the process exits, or when RIFT ignores a key-up despite OS insertion. Those require a short bounded native backend and independently supervised release/physical test. `potentially_held_keys` is an uncertainty ledger, **not** a claim that RIFT is still physically holding those keys.

This module has **no automatic process discovery, no SendInput invocation, no native memory read, and no capability to start a journey**. Do not change the README milestone to complete on the strength of these tests.

## Next most valuable development steps

1. Reinspect RR2's exact native XYZ + actor-facing reader, build-1179 evidence and post-patch offsets/identity; build a **Taxi-owned** read-only observer with current session and observed monotonic timestamps.
2. Build a bounded Windows W/A/D backend with exclusive ownership and a release path that can outlive/interrupt the normal controller loop. Distinguish OS insertion from independently observed game response.
3. Run a short **authorized physical** clear-ground probe: one qualified actor, same verified build and foreground, an actual timed W press/release, resulting XYZ/yaw and settled state. Preserve a source-hashed receipt; test lost focus/restart as negative cases.
4. Only then tune sustained straight motion (M2) and measured multi-bend smooth steering (M3).

## Source ownership

This work changes only Rift_Taxi. RiftReader2, RiftWorld and permanently read-only Telara Fly remain untouched. The interface is deliberately Python stdlib-only and does not require those projects, Workbridge, network or ChatGPT at runtime.
