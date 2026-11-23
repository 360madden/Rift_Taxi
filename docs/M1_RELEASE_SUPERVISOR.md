# M1 — External W/A/D release supervisor (separate-process prototype)

**November 23, 2026 · LEGION · Python 3.14.10 · 187/187 regressions**

**Status:** Windows child-process lease and STOP/release prototype **implemented and test-verified using fake OS-input senders and dry-run child releases**. No W/A/D movement event was sent to RIFT during this cycle. **Not yet a crash-proof or physically verified game release path.** The running RIFT client is a separate, unmodified process. See [the earlier read-only live candidate capture](M1_LIVE_NATIVE_LEGION_2026-11-23.md) for native read-only evidence.

## What exists

| Module | Responsibility |
|---|---|
| `rift_taxi/release_supervisor.py` | Separate non-daemon Python process, short lease, parent-pipe protocol, bounded release retries and per-process-epoch Windows named mutex |
| `rift_taxi/supervised_input.py` | Composite driver requiring child **RESERVE ACK before DOWN**, normal Windows key-up before **CLEAR**, and external heartbeat renewal |
| `rift_taxi/control.py` | Existing `HeldInputController` now calls an optional `renew_guard()` after each valid fresh pose, including repeated held-W updates with **no new key edge** |
| `rift_taxi/win32_input.py` | Existing explicitly armed native sender; exposes native-vs-fake sender identity so a **dry-run child cannot guard a real SendInput sender** |

Neither module is a game motion CLI or packaged controller. `ExternalReleaseSupervisor.start` takes a **qualified `LivePose`**, an absolute executable path and an explicit `dry_run` switch (default **true**). In real-release mode, startup additionally checks the fresh process/build/HWND/window foreground before the child capable of an OS key-up is constructed. Current `PositionFacingCandidate` outputs **cannot** arm the backend: actor yaw/freshness and zone binding remain unqualified.

## Lease and release sequence

```text
Taxi steering / fresh qualified pose      External release child
    |                                            |
    | start exact pinned process ----------------> Acquire named mutex
    | <-------------------- ready ACK            |
    | renew lease -------------------------------> Advance monotonic deadline
    | before any key DOWN: reserve(W) -----------> Remember W as uncertain
    | <-------------------- reserve ACK          |
    | SendInput W down (separate OS backend)     |
    | fresh pose (even W already down) ---------> Renew
    | normal SendInput W UP accepted            |
    | clear(W) ---------------------------------> Forget W
    | STOP -------------------------------------> Attempt remaining UP
    |                                            |
    | parent blocks, pipe EOF, or TTL expires ->| Attempt all reserved UP
```

Lease duration is configurable **0.10–2.0 seconds**, default 0.50s. The child checks its own monotonic deadline independently of the steering thread and attempts key-up for every still-reserved key (A, D, W in fixed order). It can attempt best-effort releases when the main process's pipe disappears. A bounded final retry is made for uncertain keys if an initial release was not accepted.

The child's **cooperative named Windows mutex** is scoped to the exact game PID and process-start ticks: `Local\RiftTaxi-PID-StartTicks`. A second Taxi helper attempting the same game epoch is refused while the first holds it. This does **not** exclude RR2 or unrelated software that does not cooperate with Taxi's mutex.

### Admission vs. release

- **DOWN:** Only after full initial OS process/HWND/executable-hash admission, a same-session qualified fresh `LivePose`, an armed `WindowsScanKeyBackend`, a running real child process, and the child's **reserve ACK**. The backend still checks current OS foreground before the actual SendInput call.
- **UP:** The controller attempts a normal OS key-up then tells the child `CLEAR` only after OS insertion acceptance. If the child stops receiving updates or observes EOF, it may issue release-only OS key-up events even after foreground loss, but **first checks exact PID/start/executable path/HWND ownership**.
- **Uncertainty:** A successful OS key-up packet is not proof that RIFT consumed it. Child reports distinguish `releaseHandlerAccepted` from `gameResponseVerified=false`. In dry-run mode the sink logs `simulated-key-up` with `acceptedByOS=false` even when the *test handler* accepted it.
- **Failure:** A failed lease renewal latches `HeldInputController` STOP. After a key-down returns, the parent **rechecks and renews the external lease**; if the child already expired, it attempts a compensating key-up and refuses to continue. No automatic rearming. Duplicate reserve, malformed messages, failed/expired lease, changed process identity or lost release channel fail closed.

### What is not solved yet

This is a **prototype**, not an unconditional guarantee. OS job termination, blocked kernel calls, unavoidable focus/late-DOWN race windows despite a compensating UP attempt, UIPI restrictions, RIFT focus handling and the possibility that a background key-up is not consumed remain unproven. The supervisor child itself could crash. Its mutex covers cooperating Taxi children, not every process. Key-release packets are not independent game-state readback. No child heartbeat or release here was tested against actual RIFT key consumption.

The actual sender and release child have **not** been armed against RIFT because the live native position and actor-angle samples are still **candidates**, not a verified `LivePose`. No physical movement test or arrival claim follows from these tests.

## Validation

**187/187 tests passed on LEGION** (previously 169; **13** new supervisor-policy/actual Windows child-process tests, including an abrupt parent `os._exit(37)` test, and **5** integrated controller/supervisor tests, including a delayed-DOWN compensation test).

Run in PowerShell under `C:\work\Rift_Taxi`:

```powershell
python -B -m unittest discover -s tests -p test_release_supervisor.py -v
python -B -m unittest discover -s tests -p test_supervised_input.py -v
python -B -m unittest discover -s tests -v
```

The tests used **synthetic qualified poses, fake W/A/D senders, and dry-run child processes**. They verified Windows spawning and process independence, **an actual synthetic parent process exiting abruptly while its dry-run child recorded a later release**, lease expiry, pipe EOF, duplicate same-epoch mutex rejection, STOP, clear, failed-release retention, heartbeat renewal with W held, a delayed synthetic DOWN returning after helper expiry with compensating UP, focus-loss/failure cases, and no further A/D DOWN after a dead helper. No game input, game-memory writes, RIFT startup or sibling repository mutations occurred. Child audit files were created only in temporary test directories.

## Next M1 acceptance work

1. Obtain **independent in-game changed-state** evidence that distinguishes cached XYZ, player-system scalar, position/actor matrices, camera movement and actual actor yaw. Confirm actor+zone and clock binding to the same physical game epoch.
2. The new synthetic late-DOWN test shows the parent can attempt an immediate compensating UP after the lease expires. **Physical SendInput and game-consumption timing remain untested**; consider relocating OS key transitions into a single supervised input process if genuine timing evidence demands it.
3. The synthetic parent actually terminated via `os._exit(37)` and its separate dry-run child recorded release successfully. **Packaged runtime and physical key-up survival remain unverified**; validate actual process/job behavior before claiming dependable crash recovery.
4. Only after fully qualifying pose and release, conduct a **short, explicit physical W/A/D calibration** with independent post-release game observations.

**Source boundary:** Taxi owns these standalone Python modules. RR2 and RiftWorld remain read-only references; `C:\work\telarafly` remains permanently unmodified and is never a Taxi runtime dependency.
