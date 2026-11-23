# Architecture — independent local navigation
**Design proposal, not implemented.** Updated 2026-11-23.

## Runtime and build-time boundaries

`RiftWorld` and `RR2` are **development references and optional offline asset producers**. The installed RIFT Taxi distribution must include every runtime component and local world package it needs. It must **not** import Python modules, invoke executables, read live data, or depend on daemons from `C:\work\riftreader2`, `C:\work\RiftWorld` or Workbridge. ChatGPT and other AI are **only engineering scaffolding**.

`User destination → local route planner → trajectory/corridor tracker → continuous steering controller → Taxi-owned Windows input adapter → RIFT client`

`RIFT client → Taxi-owned read-only pose/facing adapter → fresh identity-bound observations → progress estimator + steering + recovery`

`Local signed/versioned world-package files → route planner` (no live world research service).

The engine must be runnable headless with reproducible traces; the future desktop UI is an observer and operator control surface, not the control loop.

## Suggested internal modules (logical, introduce only when needed)

- `taxi.domain`: versioned pose, facing, game session, waypoint types, destination and corridor geometry.
- `taxi.telemetry`: current-game locator, read-only pose/facing, sample freshness and owner identity.
- `taxi.input`: current-window keyboard action delivery, pressed-key state, bounded release and STOP.
- `taxi.navigation`: route progress projection, optional-guide pruning, mandatory passage recognition, local trajectory generation and steering.
- `taxi.world`: validated package loader and coordinate transformations; no HKX reconstruction.
- `taxi.recovery`: bounded stationary/stale/blocked/drift diagnosis and local route repair.
- `taxi.replay`: record/replay, deterministic dynamics models and comparable metric output.
- `taxi.cli`: diagnostics, replay, route preview and guarded live execution.
- `taxi.ui`: eventual PySide6 application consuming state snapshots/events.

Prefer one Python installable package and a CLI. Do **not** scaffold separate services, microservices, protocols or repositories until a concrete requirement demands them.

## Contracts to define first

### `PoseSample v1`

`monotonicTime` and separately the acquisition/source time; machine; RIFT executable SHA/build; PID/process-start; player/unit identity; zone; coordinate frame; XYZ; actor yaw in declared units/reference; reader/source and confidence; freshness/age. Unknown facing is **unavailable**, not a zero angle. Heading of travel and camera angle are not actor yaw.

### `NavigationRoute v1`

Destination identity and tolerance; game/zone applicability; frame/transform identity; route/corridor geometry; typed guides, optional points, mandatory passages, explicit hard stops; width/height/clearance limits; source package/hash and qualification state. Imported suggestions are *inert* until validated against the current zone, transform, scope and player.

### `ControlFrame v1`

Observation ID; route epoch; target arc-length and preview point; desired yaw/turn-rate; tracked cross-track/heading errors; desired held-key set; commanded finite hold/maximum key-down time; state and explanation; release evidence. Store requested versus actual key timing separately.

### `JourneyReceipt v1`

Same game/player/session/route identity; actual input down/up intervals; timed XYZ/facing samples; guide crossings; hard-stop arrivals; STOP/recovery events; independent final-pose readback; movement metrics; observed outcome and exact blocker when unresolved.

Use schema-versioned local JSON initially. Compare transport options only after measuring serialization/IPC overhead; do not introduce a network bridge by default.

## Steering and motion-control design

1. **World plan:** Use a qualified corridor from stored navmesh/world data. A funnel/string-pulling path is only a candidate until corner cutting and clearance are verified.
2. **Trajectory:** Smooth geometric turns *within clearance constraints*. Estimate feasible turning radius from measured RIFT forward speed and in-game A/D yaw response. Tight corners may require slowing, stopping, or reporting unavailable; never smooth across a wall.
3. **Progress:** Project current pose onto the forward portion of the trajectory. Track increasing route arc-length with a bounded backtracking allowance; guide indexes are not the movement objective.
4. **Lookahead tracking:** Start with Pure Pursuit using dynamic lookahead based on velocity, latency, curvature and corridor width. Compare Stanley-style cross-track + heading feedback as a replay baseline. Consider MPC only if the simpler controller demonstrably fails.
5. **Actuation:** Keep forward input down through ordinary guides; add A or D simultaneously for a measured bounded steering interval. Avoid chattering left/right, stale-input oversteer and strict stop/turn at every segment. Use feedback and angle normalization.
6. **Approach/arrival:** Anticipate stopping/coast distance rather than braking exactly at a waypoint; release controls once near the destination and verify settled XYZ within the selected tolerance.

### Actual timing is a measurement, not a guess

Instrument: acquisition age → pose availability → planner compute → requested/actual key-down/up → next source observation → verified movement. Use monotonic clocks per subsystem and qualify cross-clock alignment. An OS input receipt proves delivery into the Windows stream, **not** client motion or a server-side result. Windows is not a hard-real-time OS.

### Controller architecture

A single local **journey owner** runs a state machine (`IDLE / PRECHECK / ROUTING / MOVING / PAUSED / RECOVERING / ARRIVED / BLOCKED / STOPPED / FAILED`). The UI posts destination and STOP requests and receives immutable status snapshots. The controller grants no second input owner. Observation, decision and input are independently logged. STOP and key release must function even if normal steering code stalls.

## Runtime input/observation choice

**Option A (default to prototype):** Python controller with Taxi-owned read-only Windows interfaces and explicit finite-key control. Reuse proven RR2 algorithms/ABI information selectively with attribution, without importing its runtime. **Option B (measurement-driven):** a small packaged .NET/native helper for a narrowly scoped memory read or key-control path if timing, key release, bitness or OS integration is demonstrably unreliable in Python. Do not choose a full C# rewrite by default.

No hard-coded Windows paths or other repos on the search path. Build-specific offsets require executable SHA checks and rediscovery/explicit unavailable on a changed build. Live testing must be explicitly authorized for the chosen target and held-input scope.

## World package contract

Taxi consumes a packaged, local, versioned bundle containing:
- `schemaVersion`, game build/zone, coordinate system, transform and transform provenance;
- source hashes for WorldPatch/navigation/Detour inputs, build tool and creation timestamp;
- verified-versus-candidate walkable polygons, connectivity, slope/clearance metadata, elevation/height transitions;
- named destinations, portal/transition rules and authored mandatory passages;
- route query output (or a locally bundled supported query implementation) with clear off-mesh/unreachable outcomes.

**Do not assume every RiftWorld route is collision-qualified.** The 2026-11-22 evidence includes a successful LEGION pillar contact observation, but generalized collision coverage, region connectivity and novel-path clearance remain separate research.

At a map/version mismatch, refuse that route and provide a reason. Unavailable geometry cannot be made safe by drawing a straight line between guides.

## Distribution

Target Windows 11 x64; one portable folder or installer with Python runtime/dependencies bundled, optional approved native helper, local maps, clean user data directory, logs and an offline replay CLI. No Git checkout, administrator command shell, remote host, internet or AI needed after installation. Verify packaging in a clean user context with no sibling repos and with network access disabled.

## Explicitly deferred

Automatic game interactions beyond grounded locomotion, smart mounts, portals, NPC interactions, multi-zone travel, dynamic avoidance with no sensor evidence, full game-engine NPC-path access, performance optimization without measurements, new HKX parser, exotic AI/RL runtime control, and a high-polish GUI before first physical smooth multi-bend acceptance.
