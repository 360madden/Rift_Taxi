# M1 bounded probe lease timing — November 28, 2026

**Scope:** an offline-tested repair to the existing A/D turn and W forward
calibration diagnostics. This does not arm production navigation or provide a
new physical movement receipt.

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
