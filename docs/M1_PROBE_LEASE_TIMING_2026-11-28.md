# M1 bounded probe lease timing — November 28, 2026

**Scope:** offline-tested lease and cleanup repairs to the existing A/D turn,
W forward and separate A-only parent-crash diagnostics. These repairs do not
arm production navigation. Subsequent physical moving-series evidence is
recorded separately and linked below.

## Reproduced failures

At predecessor commit `0a00a3b469f468ee81d1e2a5d8e4a5d59828c2fe`, the
diagnostic reserved a release lease before repeating full foreground/process/
executable admission. A/D then submitted DOWN without renewing. If that
admission took longer than the 0.6-second lease, the independent child could
release the reserved key and stop before the parent submitted a new DOWN.

A deterministic regression used the actual pure `ReleaseState`, an injected
clock and inert senders. Advancing the clock by 0.61 seconds during the final
identity check reproduced DOWN after guard release for both A and D; the
existing W renewal refused that case. This is an offline reproduction, not
a new physical failure experiment.

A separate regression showed that the cleanup clock read occurred before the
UP/STOP cleanup. NaN and rollback produced falsely successful timing receipts;
a clock exception escaped before local UP. The forward path also accepted a
structurally plausible renewal whose reply could already be too old.

## Implemented repair

The shared calibration path in [turn_probe.py](../rift_taxi/turn_probe.py):

1. Renews for A, D and W after the final identity and key-state checks.
2. Requires an unstopped reservation for exactly the requested key.
3. Checks a finite, nondecreasing monotonic clock and finite same-domain deadline.
   The deadline cannot be further away than the fixed 0.6-second lease and must
   leave more time than the requested 60–160 ms hold.
4. Rechecks deadline budget and child liveness after the sender returns. A late
   return goes directly to UP/STOP cleanup, without another hold.
5. Attempts local UP and worker STOP even if timestamp acquisition fails. It
   refuses a successful receipt after invalid cleanup time or an expired hold.

The public probe signatures and report schemas remain unchanged. Native XYZ,
body heading, game-consumed input/release and movement qualification remain
candidate-only. The separate release worker's existing protocol is unchanged.

## Verification

[Focused regressions](../tests/test_turn_probe.py) cover expiration during
identity admission, renewal failure, wrong/malformed/stopped acknowledgments,
expired or insufficient deadlines, delayed sender returns, invalid/rollback
clocks, cleanup exceptions and ordinary A/D/W operation.

Before the repair, the new expiration and cleanup regressions failed against
the original production source. After the repair, **25 focused tests passed
on LEGION in 0.752 seconds**. An existing Windows integration test now runs the
complete probe with an actual spawned release child and real monotonic clock/
sleep, while injecting identity/capture and retaining dry senders. It submitted
no OS keys.

Independent review also exercised six inert cases: A/D/W with the helper
disappearing immediately before or after DOWN. All refused, skipped the hold,
and attempted UP/STOP; pre-DOWN disappearance submitted no DOWN.
The full-suite and exact-head hosted results are recorded in
[the current handoff](HANDOFF_CURRENT.md) and the associated PR check.

## Physical follow-up

The lease checks and input insertion remain separate operations. They do not
make Windows scheduling atomic, guarantee recovery from every sender stall/
crash, or prove game-consumed release.

A fresh foreground-only screen copy at 06:00 PHT showed the current character
on the Sanctum Watch pavilion beside a steep drop. No game input was sent.
Before a physical changing-pose experiment, establish a clear-ground scene,
current movement bindings and released mouse/modifier/movement controls,
then reacquire the exact process, owner and reviewed scene receipt. Existing
native series can measure the action interval; no new pose parser is needed.

Actor stored translation is derived from the same native position cache.
Visible telemetry addon panels and matrix/position agreement do not establish
an API-quiet interval or passive freshness. Keep the remaining
[M1 admission requirements](ROADMAP.md) explicit.

## 07:17 PHT continuation — separate A-only crash worker

The moving-series follow-up used the repaired shared W probe successfully;
see [the original 96-sample evidence](M1_MOVING_NATIVE_SERIES_LEGION_2026-11-28.md).
Reviewing the next release-fault path found the same ordering defect in
`crash_release_probe._child` at source commit `a97bac9`. It reserved and
renewed a 0.55-second lease before a full identity/hash check, then sent A DOWN
without checking the remaining deadline. Ordinary sender, marker or hold
failures also lacked an explicit compensating parent UP.

The inert reproduction used the actual pure `ReleaseState` with a controlled
clock and fake input. Job `taxi_crash_lease_red_20261128_01` exited 1 with 28
failing subcases across 21 tests. It reproduced DOWN after lease expiry,
malformed/delayed renewal acceptance and omitted local compensation.
No physical A input was sent by this reproduction or repair.

The crash worker now renews after final identity, rescue-launcher and key
checks. It reuses the shared finite/nondecreasing clock and deadline checks,
then applies its stricter 0.55-second upper bound. It verifies remaining hold
budget and child liveness before DOWN, after sender return, after marker
flush/fsync, and after the hold before intentional exit.

Any ordinary exception after possible DOWN insertion attempts parent UP,
then child STOP. Cleanup does not depend on a working clock or further disk
I/O; unsuccessful UP leaves the independent reservation available to STOP.
Only the real `os._exit(37)` branch bypasses Python cleanup. The marker records
intent with `intentionalCrashVerified=false`; a marker plus child UP cannot
qualify the experiment unless the actual worker exited with code 37.

Final focused job `taxi_crash_lease_green_20261128_02` passed 22 tests in
0.844 seconds. Cases cover expiry during admission, invalid or stale ACKs,
worker disappearance, late/throwing DOWN, invalid clocks, failed/slow marker
writes, hold failures, and failed compensating UP. An isolated subprocess
with every input/native endpoint replaced by inert fixtures performed real
`os._exit(37)` and verified that Python cleanup did not run. A retained marker
and child-UP receipt with a non-37 exit remained unqualified.
Independent source and regression review passed. Full-suite and exact-head
CI acceptance are recorded with the checkpoint in the current handoff.

| Reviewed file | SHA-256 |
|---|---|
| `rift_taxi/crash_release_probe.py` | `97ef62482db943297b4cc8a87a00df5f9ba8c4d9d340fa16b084be6f69ac9ae9` |
| `tests/test_crash_release_probe.py` | `bdbbdc51739b25b7fceefcb93bfb475a97ed0ba8dfcc21474a76b62a42c9ba43` |

The check/send/exit sequence remains non-atomic. The surviving launcher and
independent release worker remain necessary; no new physical crash, focus-loss,
release-child-death or universal release claim follows from these tests.
