# RIFT Taxi documentation index

**Status:** design and source-research foundation, as of 2026-11-23; **offline replay/control and a live-tested read-only RIFT candidate reader exist; two physical A/D pulses succeeded with OS release receipts, and a separate W-only probe passes 278 offline/fake-sender regressions; game-consumed release, physical W motion, actor-facing freshness, crash recovery and autonomous journeys remain incomplete**. Local project is `C:\work\Rift_Taxi` on LEGION.

## Start here (recommended reading order)

| Question | Document | Why |
|---|---|---|
| Where should the next development session resume? | [Current M1 handoff](M1_HANDOFF_2026-11-23.md) | Verified baseline, physical A/D outcomes, source hashes, blockers and next autonomous acceptance sequence |
| How should the AI conduct the development autonomously? | [AI-first execution policy](AUTONOMY_POLICY.md) | User directive: minimize manual interventions, deliver tests/commits and automated evidence |
| What is Taxi supposed to do? | [Product requirements](PRODUCT_SPEC.md) | Final destination first, continuous W+steering, guide/hard-stop semantics |
| How will the standalone app work? | [Architecture](ARCHITECTURE.md) | Local controller, world packages, pose/input, recovery, deployment |
| What does each sister repo provide? | [Research reuse index](RESEARCH_IMPORTS.md) | Source pinning, confidence levels and no runtime coupling |
| What has RR2 really demonstrated? | [RR2 handoff](RR2_HANDOFF.md) | Native XYZ/yaw, physical movement, existing sparse steering limitations, release |
| What can RiftWorld export? | [RiftWorld handoff](RIFTWORLD_HANDOFF.md) | WorldPatch/Detour, obstacle evidence, transforms, bridge/pillar regressions |
| Why preserve Telara Fly as reference only? | [Telara Fly inventory](TELARA_FLY_REFERENCE.md) | Unity asset/CDR/NIF/OBJ provenance and Z-flip hazard |
| What should our import formats contain? | [Integration contracts](INTEGRATION_CONTRACTS.md) | **Proposed Taxi schemas** versus existing upstream names; import rejects |
| What should be built first? | [Roadmap](ROADMAP.md) | M1 trace/reader → M2 straight → **M3 smooth bends** → M4 map |
| What's already implemented? | [M1 implementation](M1_IMPLEMENTATION.md) | Executable offline CLI, original RR2 import, synthetic steering, tests, and remaining live-control gaps |
| How does STOP and held W+A/D behave offline? | [M1 control boundary](M1_CONTROL_BOUNDARY.md) | Same-session gate, watchdog, input rejection and driver-neutral fault tests |
| Has Taxi physically turned RIFT and released keys? | [First bounded A/D calibration](M1_PHYSICAL_AD_TURN_CALIBRATION_2026-11-23.md) | Physical A/D down/up, separate release process, native angle delta and screen receipts; body yaw pending |
| Is a supervised W-only movement experiment ready? | [Bounded W diagnostic](M1_BOUNDED_W_FORWARD_PROBE_2026-11-23.md) | Default dry-run, 60–160 ms W gate, new delayed readback and release tests; physical W **not performed** |
| How do we pin the Windows process and game window? | [M1 Windows identity](M1_WIN32_IDENTITY.md) | Read-only PID/start/path/hash/HWND inspection and limitations |
| Can Taxi read native memory or decode XYZ/yaw? | [M1 native candidates](M1_NATIVE_READONLY.md) | Bounded read-only session, source-pinned candidate decoder and explicit one-shot/burst commands; not qualified for driving |
| Do two position/actor matrices match in one capture? | [M1 matrix comparison](M1_MATRIX_CANDIDATE.md) | Optional owner-scoped raw float32 bit comparison and unqualified candidate planar angle |
| How do we compare camera-only, A/D and forward phases? | [M1 facing signature](M1_FACING_SIGNATURE.md) | Matrix-enabled bursts, exact source checks and five-phase **offline candidate** comparisons |
| Did Taxi itself read the live physical RIFT client? | [M1 LEGION live native capture](M1_LIVE_NATIVE_LEGION_2026-11-23.md) | Original artifact hashes, exact process identity, player XYZ/yaw and 9/9 matrix candidate match |
| Are the cached XYZ refresh guards active? | [M1 live XYZ refresh guards](M1_LIVE_XYZ_REFRESH_GUARDS_LEGION_2026-11-23.md) | Exact-build 0/0 guards on real client, four-sample evidence and API-refresh caveat |
| Does the actor component expose another world translation and changed state? | [M1 actor-world changed-state](M1_ACTOR_TRANSLATION_CHANGED_STATE_LEGION_2026-11-23.md) | Live model-transform reconstruction, original hashes and two-capture same-epoch candidate differences |
| What can historical key/pose timing really measure? | [M1 source timing + Telemetry audit](M1_MOTION_TIMING_AND_TELEMETRY_AUDIT_2026-11-23.md) | Source-hashed RR2 sample-speed timing, 0.10s installed addon polling and evidence caveats |
| Can Taxi sample native player data ~10 times a second? | [M1 pinned live native series](M1_LIVE_NATIVE_SERIES_LEGION_2026-11-23.md) | Source-hashed real 24-sample sessions, corrected cadence, exact identity and pending movement proof |
| Can a person manually press W/A/D while Taxi observes native XYZ? | [M1 passive Windows key snapshots](M1_READONLY_MANUAL_KEY_OBSERVATION_LEGION_2026-11-23.md) | Optional sampled high-bit W/A/D states; physical read-only test and no game-consumption claims |
| Is Taxi's production W/A/D backend armed? | [M1 Win32 scan-code backend](M1_WIN32_INPUT.md) | No; driver-neutral backend tested, with separate physically executed A/D diagnostics and W pending |
| Can key-release continue if steering stalls? | [M1 external supervisor](M1_RELEASE_SUPERVISOR.md) | Windows child process, lease, EOF and mutex regressions; real game release unverified |
| What qualifies as a successful journey? | [Validation](VALIDATION.md) | Measured W duty, running turns, stops, clearance and final readback |
| Which NPC/services are initially supported? | [Curated destinations](NPC_DESTINATIONS.md) | Porticulum, banker, healer, auctioneer, mailbox, story NPCs (travel-only) |
| Which choices are durable? | [Decisions](DECISIONS.md) | User-approved architecture and priority |
| How should code agents operate? | [../AGENTS.md](../AGENTS.md) | Repository boundaries, test discipline and independent runtime |

## Evidence and implementation labels

- **Implemented upstream:** actual source function/schema inspected in a named repository.
- **Observed upstream:** time/build/host/actor-bound live result with retained evidence; never claim Taxi achieved it.
- **Candidate upstream:** generated geometry, native field, NPC data or route without required independent checks.
- **Proposed Taxi:** interface/algorithm/test written in this repository; it remains *not implemented* until code and tests exist.

This separation is deliberate. A saved full route, a complete Detour query and a success flag from an input worker are not automatically a live, smooth Taxi arrival.

## Source protection

RR2 and RiftWorld are **read-only references** for Taxi development; never modify their working trees just to implement Taxi. **Telara Fly is permanently read-only**, including any action that could generate build/caches/logs. Changes and adapted code belong in `Rift_Taxi`; broad world decoding improvements belong to RiftWorld in a separately owned effort, not to the original Telara Fly tree.

No developer repository or cloud AI is part of the installed Taxi runtime. Generated map packages, calibrated input data and native helpers must be bundled with source/build identities and tested in isolation.
