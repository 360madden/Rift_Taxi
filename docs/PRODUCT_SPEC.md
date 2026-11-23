# Product requirements — RIFT Taxi
**Status:** intended behavior, not implemented capability. **Date:** 2026-11-23.

## User experience

The user opens Taxi, chooses a known destination or safe custom endpoint, previews a proposed route, and selects **Start**. After admission, the **local runtime** makes all navigation decisions until arrival or a clear blocked/stopped outcome. Closing ChatGPT, disconnecting the internet, or not running RR2, RiftWorld or Workbridge must not affect an active journey. RIFT itself remains open for live play.

Desired experience: the character begins running, smoothly steers around bends, flows through guidance points, and stops **at the destination**, not at each intermediate coordinate. An NPC moving naturally through a world is the qualitative benchmark, with measurable travel metrics as the engineering standard.

## Waypoint and route semantics

| Type | Required meaning | Stops? | Can exact coordinate be skipped? |
|---|---|---|---|
| `guide` | Approximate direction / shape hint | No | Yes |
| `optional` | Convenience point or suggested detour | No | Yes, including dropping the point |
| `mandatory_passage` | Constraint such as bridge, portal, choke or required polygon corridor | Only if geometry demands it | The arbitrary centerpoint yes; **not** the required traversable region/transition |
| `hard_stop` | User explicitly requires arrival and stationary check | Yes | No |
| `destination` | Authoritative requested final arrival | Yes | No |

The planner may prune and smooth guides **only inside verified traversable space**. It must not cut across unknown terrain, walls, drop-offs, height-separated surfaces or unverified polygons simply to skip a waypoint. Where the world model is incomplete, Taxi selects qualified local ground or reports that the route is unavailable.

Progress is measured as **along-track distance / projected segment or corridor progress**, not a counter of reached waypoint indexes. Once the player safely passes a guide, Taxi must not reverse toward it merely because its exact coordinate was missed. Hard stops remain ordered obligations.

## Travel flow

`IDLE → PRECHECK → ROUTING → MOVING → ARRIVED`, with explicit `PAUSED`, `RECOVERING`, `BLOCKED`, `STOPPED` and `FAILED` outcomes. Route recalculation is local; it does not require AI approval or prompts. STOP overrides all other states and requests release immediately; restart never silently resumes.

### MOVING

- Hold the forward movement action through guides when the corridor and steering envelope permit.
- Compute a continuously advancing lookahead target from the path, actor orientation, speed and observed latency.
- Apply left/right steering **while forward input remains held** (when the game input binding supports it). Avoid alternating tiny A/D pulses that induce oscillation.
- Compare actual pose and movement heading independently; preserve the distinction between actor yaw, camera yaw and travel course.
- Anticipate tight bends with lookahead/curvature-based speed or pre-turn strategy; stop only when unavoidable for route validity.
- Use closed-loop position, heading, time and bounded game-response evidence—not hard-coded durations alone.
- Near destination, control deceleration/settle, release keys, and confirm the same actor has arrived within a configurable qualified tolerance.

### RECOVERING

Classify loss of progress, stale data, controller drift, blocked passage and route invalidation separately. If an alternate **verified** corridor exists, locally replan and continue within configured limits; otherwise stop/release and report the blocker. Never repeatedly push into a known obstacle.

## Constraints and non-goals

- Windows live client; direct player observation and input, not native NPC authority.
- No initial promise of arbitrary-zone travel, crossing disconnected navmesh islands, dynamic crowds, swimming, jumping, flying, mounts, combat, service interactions or porticulum interactions. Research/add only after a measured baseline.
- Curated service destinations (Porticulum Master, personal bank, healer, auctioneer, **mailbox for auction collection**, selected story quest NPCs) are **travel-only** features introduced after smooth multi-bend running. RIFT auction purchases and proceeds use in-game **mailboxes**, not a presumed separate auction-collection NPC. See [limited NPC/service scope](NPC_DESTINATIONS.md).
- No AI/cloud required at runtime; optional AI-assisted development ends at code/asset creation.
- No reading RR2 or RiftWorld from sibling paths at runtime, and no dependency on their background services.
- No general HKX reverse-engineering, world extraction, or duplicate Detour mesh builder inside Taxi.
- Initial testing stays within known clear ground and qualified route transforms.

## Definition of a useful release

A packaged local app starts on a clean Windows machine with supported prerequisites, identifies current RIFT, autonomously follows a verified multi-bend route with no unnecessary guide stops, independently confirms the final arrival, releases held controls on STOP/error, and runs without internet or other research applications. Scope-qualified limitations remain visible in the UI and README.
