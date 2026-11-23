# RIFT Taxi 🚕
**Standalone, destination-driven navigation for RIFT MMORPG**

> **Project status — 2026-11-23:** Git initialized; architecture, source-repository handoffs and integration contracts documented. **No Taxi navigation executable, live input, successful journey or packaged distribution is claimed.**

## Product goal

Select a destination, press **Go**, and let the **local application** guide the character from start to finish: keep running over ordinary route guides, steer *while moving*, follow verified traversable corridors, recover from interruptions where possible, and stop at the final destination. An intermediate point is **not** a required stop unless its type explicitly says so.

**Success means a smooth end-to-end journey, not a high count of individually reached waypoints.**

## Non-negotiable principles

1. **Standalone at runtime.** No RR2, RiftWorld, Workbridge, ChatGPT, cloud AI, or external developer process must run during a journey. RIFT itself is required for live gameplay.
2. **All driving decisions are local.** Planning, steering, progress, recovery, obstacle decisions and arrival checks are deterministic application logic—not agent prompts.
3. **Destination first.** Ordinary waypoints are geometric suggestions; the controller may skip or merge them. Mandatory passages and explicit hard-stop points remain binding.
4. **Continuous motion by default.** Forward movement stays engaged across intermediate guides when traversable; steering happens during forward travel. Only genuine constraints, explicit hard stops, cancellation and final arrival require stopping.
5. **Evidence before claims.** A simulated success, OS input receipt, native candidate read, Detour path, and measured in-game arrival are distinct.
6. **No reinvention for its own sake.** Refer to existing research as scaffolding, selectively incorporate proven techniques or independently packaged data, and retain source provenance without requiring those repositories at runtime.

## Technical direction

- **Python-first** application, command-line core and later PySide6 desktop UI.
- A small bundled native Windows component may be adopted *only if measurements establish a need* for reliable input delivery, read-only game observation, or key-release behavior.
- Local, versioned world/navigation packages imported from RiftWorld research, never a live service dependency.
- Small, curated **travel-only** destinations for key NPCs and services; auction collection uses a **mailbox**, separately from auctioneers and personal bankers.
- Read-only, process/build-bound pose and actor facing; finite, observable movement input with independent release and STOP.
- Offline deterministic replay and benchmarks developed **before** wide-area live runs.

## Development order

| Stage | Result | Primary proof |
|---|---|---|
| M0 | Contract, repository, measurement plan | Docs and initial Git commit |
| M1 | Standalone pose + bounded input | Exact client identity, fresh facing/XYZ and verified release |
| M2 | Continuous straight travel | Sustained W and clean final stop on clear ground |
| M3 | Smooth multi-bend travel | Three or more bends, steering with W held, no stops at guides |
| M4 | Independently packaged destination routes | Same result without RR2/RiftWorld installed or running |
| M5 | Obstacle/recovery intelligence | Verified corridor handling and bounded, local replanning |
| M6 | User-friendly standalone taxi | UI, build/package, installation and complete live acceptance |

Detailed dependencies, tests, and gates: [Development roadmap](docs/ROADMAP.md).

## Documentation

- [Product and waypoint semantics](docs/PRODUCT_SPEC.md)
- [Standalone architecture and control design](docs/ARCHITECTURE.md)
- [Development roadmap and milestones](docs/ROADMAP.md)
- [Benchmarks and acceptance criteria](docs/VALIDATION.md)
- [Documentation hub and reading order](docs/README.md)
- [RR2/RiftWorld/Telara Fly research reuse inventory](docs/RESEARCH_IMPORTS.md)
- [RR2 source handoff](docs/RR2_HANDOFF.md) · [RiftWorld source handoff](docs/RIFTWORLD_HANDOFF.md) · [Telara Fly read-only inventory](docs/TELARA_FLY_REFERENCE.md)
- [Versioned integration contract design](docs/INTEGRATION_CONTRACTS.md)
- [Durable decisions](docs/DECISIONS.md)
- [Limited NPC and service destinations](docs/NPC_DESTINATIONS.md)
- [Developer instructions](AGENTS.md)

## Local repository

Repository: `C:\work\Rift_Taxi` on **LEGION**, branch `main`, Git author `360madden <360madden@gmail.com>`. GitHub remote/publication is a separate operation; no remote is implied by creating a local Git repository.

## First implementation task

Build a minimal **trace-replay CLI** with typed, time-stamped pose/facing, route, and input-event contracts. Reproduce a known stop-turn-run failure offline using genuinely time-aligned original RR2 observations when available; do **not** invent missing yaw or key timing. Then implement and compare a running/steering controller against the same trace. The November 23 15-point Guardian bridge route is a staged-travel reference, not an already accepted uninterrupted journey. Do not begin with a large GUI or a duplicate geometry extractor.
