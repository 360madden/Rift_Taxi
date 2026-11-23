# M1 driver-neutral control boundary — November 23, 2026

**Project:** Rift_Taxi on LEGION · **Status:** driver-neutral gate offline-tested. A later Taxi-owned read-only candidate reader has succeeded against live RIFT, and a separate Win32 scan-code input adapter is inert-tested. **Neither qualifies a working RIFT controller or physical game input.**

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

**The original 63/63 offline regression tests passed on November 23, 2026 (Python 3.14).** A separate Win32 identity slice added 11 tests, bringing the later suite to **74/74 passing**; see [M1 Windows identity](M1_WIN32_IDENTITY.md). The **29** control-gate tests cover forward-key continuity across turn changes, A/D reversal ordering, STOP/retry, worker-initiated release, expiry ordering, exact session binding, stale/duplicate/out-of-order source data, invalid key sets, immutable pose coordinates, and injected backend faults.

The original gate tests use an inert `RecordingBackend`: they insert no OS input. Since that historical slice, Taxi's **separate read-only native reader** has collected real candidate XYZ/yaw and matrix values on LEGION; the **new Win32 key backend is still tested only with inert SendInput fakes**. None of those later observations establishes game movement, heading semantics or an accepted physical input event.

## Explicit safety/implementation gaps

| Boundary | Present | Still required for live M1 |
|---|---|---|
| Same-client process/window/player binding | OS PID/start/path/hash/HWND read-only candidate inspector plus exact session-contract equality | Bind that candidate to independently verified RIFT actor/zone and fresh pose |
| Pose freshness/yaw | Same-clock gating + real exact-build read-only XYZ/yaw **candidates** | Prove live passive refresh and qualified body heading/actor/zone before motion |
| Held W/A/D | Driver-neutral gate + **Win32 scan-code backend** with fake-sender acceptance tests | Qualify and measure bounded physical OS/game response after verified pose |
| STOP and timeout | Latched STOP, daemon watchdog and accepted-UP accounting | Independently supervised release even if the native backend blocks; OS/game post-release readback |
| Exclusive ownership | Single in-process lock | Cross-process actuator-owner arbitration and safe crash/restart behavior |
| Verification | 29 fake-driver tests plus historical/offline suite | Read actual observed game response and fresh independently settled final pose |
| Navigation | Synthetic Pure Pursuit preview | Calibrated closed-loop trajectory controller and verified corridor |

**Critical distinction:** a Python watchdog cannot guarantee release when a foreign driver call hangs under the shared controller lock, when the process exits, or when RIFT ignores a key-up despite OS insertion. Those require a short bounded native backend and independently supervised release/physical test. `potentially_held_keys` is an uncertainty ledger, **not** a claim that RIFT is still physically holding those keys.

The `control.py` module itself has no automatic process discovery, native reads or SendInput; the separately implemented `win32_input.py` can issue SendInput **only if explicitly armed with independently qualified pose**. The physical RIFT session has not met that gate. Do not mark M1 complete from synthetic sender tests or real candidate reads alone. [Input evidence boundary](M1_WIN32_INPUT.md).

## Next most valuable development steps

1. Correlate the already-acquired Taxi-owned current-build XYZ/yaw/matrix candidates with independent actual game-state changes, verified actor/zone and same-clock timestamps; no automatic promotion from stationary data.
2. Complete **independently supervised release, exclusive actuator ownership**, and measured physical acceptance for the new bounded Win32 W/A/D backend. Distinguish OS insertion from independently observed game response.
3. Run a short **authorized physical** clear-ground probe: one qualified actor, same verified build and foreground, an actual timed W press/release, resulting XYZ/yaw and settled state. Preserve a source-hashed receipt; test lost focus/restart as negative cases.
4. Only then tune sustained straight motion (M2) and measured multi-bend smooth steering (M3).

## Source ownership

This work changes only Rift_Taxi. RiftReader2, RiftWorld and permanently read-only Telara Fly remain untouched. The interface is deliberately Python stdlib-only and does not require those projects, Workbridge, network or ChatGPT at runtime.
