# RIFT Taxi documentation index

**Status:** design and source-research foundation, as of 2026-11-23; **offline replay/control and a live-tested read-only current-build RIFT candidate reader exist; an unarmed Win32 scan-code W/A/D backend is inert-tested; actor-facing freshness, independent release, physically accepted game input and autonomous journeys remain incomplete**. Local project is `C:\work\Rift_Taxi` on LEGION.

## Start here (recommended reading order)

| Question | Document | Why |
|---|---|---|
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
| How do we pin the Windows process and game window? | [M1 Windows identity](M1_WIN32_IDENTITY.md) | Read-only PID/start/path/hash/HWND inspection and limitations |
| Can Taxi read native memory or decode XYZ/yaw? | [M1 native candidates](M1_NATIVE_READONLY.md) | Bounded read-only session, source-pinned candidate decoder and explicit one-shot/burst commands; not qualified for driving |
| Do two position/actor matrices match in one capture? | [M1 matrix comparison](M1_MATRIX_CANDIDATE.md) | Optional owner-scoped raw float32 bit comparison and unqualified candidate planar angle |
| How do we compare camera-only, A/D and forward phases? | [M1 facing signature](M1_FACING_SIGNATURE.md) | Matrix-enabled bursts, exact source checks and five-phase **offline candidate** comparisons |
| Did Taxi itself read the live physical RIFT client? | [M1 LEGION live native capture](M1_LIVE_NATIVE_LEGION_2026-11-23.md) | Original artifact hashes, exact process identity, player XYZ/yaw and 9/9 matrix candidate match |
| Can Taxi insert standard Windows W/A/D keys? | [M1 Win32 scan-code backend](M1_WIN32_INPUT.md) | Explicit arming, test-only fake insertion and the missing release-supervision boundary |
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
