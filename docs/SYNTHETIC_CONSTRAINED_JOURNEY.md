# Synthetic constrained journey — first model execution slice

The original unconstrained simulator and its frozen research results are
unchanged. The standalone constrained runner reuses the existing ideal
approach, passive FIFO drain, terminal correction and independent
saved-journey checks. It splits the route only at explicitly declared hard
stops and the final destination. Mandatory points are retained as geometric
guides within a leg; passage evidence is a distinct sample in the declared
XYZ region during the approach. A missed region refuses that completed
model leg and prevents the next leg, rather than being silently skipped.
This is **not** a region-constrained trajectory planner or a guarantee that
the modeled approach cannot pass an unobserved region.

At each accepted endpoint the existing modeled queue is drained and the
terminal correction is checked. Additional exact zero-command intervals
span the requested dwell, with the same actual model XYZ/yaw, and the
shared sampled-obligation checker verifies the ordered witnesses. The
next leg is seeded from the actual settled pose, not the nominal waypoint.
A shared boundary sample cannot be reused for the next obligation. Unlike
the supplied-key audit, this model audit derives quiet intervals from
applied ideal speed and yaw rate; it never invents key events.

Work is bounded to 1–8 legs, at most 40 model seconds of approach and
5 model seconds of correction per leg, 0–10 nominal delayed steps,
0.02–0.2 s dt no larger than the policy sample gap, and the existing
bounded dwell. Invalid leg geometry is rejected before starting the
simulation. Failed approaches and unsettled endpoints do not acquire
extra dwell or resume. A later unexecuted obligation remains not-attempted.
The top-level allObligationsObserved flag additionally requires accepted
settlement of every planned leg. The runner ignores later source poses
and source key events because only the original route and initial pose
seed this ideal plant.

## Run the authored example

```powershell
python -B -m rift_taxi.synthetic_constrained_journey samples\synthetic_constrained_straight.json samples\synthetic_constrained_straight.policy.json --delay-steps 2 --require-observed --out artifacts\new-constrained-journey.json
```

The supplied policy pins the exact synthetic trace bytes. Use a new
output path. The report includes every attempted leg, original point
indices, local witness times with explicit leg-start offsets, dwell
frames, total modeled elapsed time/distance/duty and false physical
qualification flags. Exit 0 indicates a valid report, or all obligations
when --require-observed is supplied; exit 1 indicates a valid incomplete
model journey under that flag; exit 2 indicates refusal.

## Retained model results — LEGION, November 27

The authored fixture is not a real map or a fresh holdout. Both examples
observed two passage regions and the required hard stop and destination
dwell. Duty includes all settlement/dwell intervals and is not the
movement-eligible physical W-duty milestone metric.

| Delay steps | Accepted legs | Elapsed (s) | Distance (synthetic units) | Total forward duty |
|---:|---:|---:|---:|---:|
| 0 | 2/2 | 4.30 | 7.7331101954 | 0.7674418605 |
| 2 | 2/2 | 4.40 | 7.9851200000 | 0.6818181818 |

Original sample SHA-256:
4da24bc188addc3cd0d558b7f1132933b71be9d3e97938e67c3781f52a9cd07e.
Policy SHA-256:
4fbb9e8999a5894be582a07a7f95700dd3222f49e81fb60908898d49211b262d.

Private directory artifacts/m3-constrained-20261127-1140:
zero-delay.json (42,920 bytes) SHA-256
a880ae8bca4e92b296a5d4a377cd77f7000be4c3f6ed34648e3d3128ecd6e245;
two-step-delay.json (45,929 bytes) SHA-256
ec7a70163454b9f7e15f385bc2c65156a0128fd336dd009208bb581799fbc86a.
Eight original constraint regressions and eight new runner regressions
passed locally. The negative narrow-region and approach-budget cases
retain failure and do not start the next leg.

No live game input, continuous unobserved stationarity, physical corridor
clearance or M1/M2/M3 exit is established. The next offline acceptance
step is verification of a saved full constrained receipt against its
original trace and policy, followed by installed-package smoke tests.

## Saved-report verification

The separate auditor reconstructs per-leg seed/point identity and validates
the retained approach, drain and correction without rerunning the approach
controller. It recomputes model dwell, ordered sampled witnesses, actual pose
carryover, failure/resume boundaries and total elapsed time, distance and
forward duty. It rejects a truncated successful prefix, a resumed failed leg,
modified witness/dwell, different model parameters and inconsistent summaries.
It shares deterministic witness extraction and the existing terminal
algorithms; this is model consistency, not independent physics or collision proof.

```powershell
$pin = (Get-FileHash artifacts\new-constrained-journey.json -Algorithm SHA256).Hash
python -B -m rift_taxi.synthetic_constrained_audit samples\synthetic_constrained_straight.json samples\synthetic_constrained_straight.policy.json artifacts\new-constrained-journey.json --expected-sha256 $pin --out artifacts\new-constrained-audit.json
```

Both retained straight-course reports passed exact-report-pin verification.
They were programmatically produced and omitted the exact policy byte pin;
the semantic policy identity matched. CLI reports carry the exact byte pin.
Audit receipts in the same private artifact directory:

- zero-delay-audit.json: 4894baba46f3204d2c362ecec7232ea8dfa5c074545af955315d5bd10c1a7b28
- two-step-delay-audit.json: ad21f674fc049b68d0869b32b3debde2a0437b44d3e41b32ed8212269ed925ab

The frozen delayed multi-bend development case used dt .12, speed 3.6,
yaw rate 125 and delay 3. Both legs and four obligations completed in
18.48 modeled seconds, including first-leg correction of 1.56 s. The
identical .01 s correction budget refused resume. Both outcomes passed
the saved-model audit. The nine added audit tests and eight runner tests
passed locally before the LEGION connection terminated.

The installed-wheel constrained producer/audit workflow addition was
prepared locally, but not published in this recovery commit. Reconcile it
with the cloud checkpoint after restoring the authorized connection. Do
not discard or overwrite local uncommitted edits.

## Installed-wheel acceptance checkpoint

The comprehensive CI minimum-Python job now also invokes the installed
constrained journey producer and a separate saved-report auditor using
isolated Python mode outside the checkout, requires the pinned policy and
all two legs/four obligations, and archives the reports. The exact-head CI
checkpoint gate requires this new named step. Older historical runs use
the gate from their own revision. Hosted acceptance is pending until the
corresponding workflow run is independently verified.
