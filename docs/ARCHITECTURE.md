# RIFT Taxi architecture — standalone local autopilot

> **State:** architecture specification, not an implemented application. **Reviewed:** 2026-11-23 on LEGION. The source-checkpoint inventory is in [RESEARCH_IMPORTS.md](RESEARCH_IMPORTS.md).

## 0. Product invariants

1. **Destination authority:** navigate from current RIFT character pose to the chosen **final reachable approach**, not point-by-point arrival at all guides. Intermediate `guide` and `optional` samples may be merged or skipped. A `mandatory_passage`, `hard_stop`, floor/zone transition or final destination remains binding.
2. **Fluid travel:** sustain forward travel through ordinary guides, continuously adjust heading **while moving** when a verified corridor and measured turn response allow it. An unnecessary stop-turn-run sequence is an acceptance failure regardless of final positional accuracy.
3. **Local autonomous decisions:** routing, lookahead, steering, progress, recovery and arrival happen inside the app on the user's Windows machine. No remote AI, ChatGPT, online service or manual AI dispatch participates in a journey.
4. **Standalone deployment:** the installed Taxi can operate without running or installing RR2, RiftWorld, Telara Fly, Workbridge, a developer Python environment, or Git. The RIFT game client is the necessary live-game target. Offline replay works without RIFT.
5. **Evidence-defined capability:** a Recast path does not prove collision clearance; a historical NPC X/Z does not prove a reachable live service; an input-insertion receipt does not prove movement. Separate candidate and accepted states at every boundary.
6. **Honest stopping:** STOP, source loss, owner change, impossible route and release faults take precedence over smoothness. Smoothness never authorizes crossing unknown surfaces.

## 1. What the sister repositories supply

| Repo | Verified research/build role | What Taxi takes | What Taxi deliberately does not take |
|---|---|---|---|
| **RR2** — `C:\work\riftreader2` | Current-client native position/facing and unit readers; controlled movement, held-key release and exact-process evidence; historical failed/successful navigation receipts | Tested algorithms/ABI facts, timestamped movement traces, failure lessons, a **Taxi-owned** observation and input interface | Running RR2 executable, Waypoints process, addon/receiver daemon, private calibration path, its sparse stop/turn controller |
| **RiftWorld** — `C:\work\RiftWorld` | Source-coordinate WorldPatch, Recast/Detour builds, candidate paths, verified local obstacle evidence, scene placements and curated NPC-location leads | A validated **offline** export of relevant geometry, routes, source provenance and reachable approaches | A running RiftWorld process, Java/JPype builder in Taxi by default, live map server, blanket assertion of Havok collision authority |
| **Telara Fly** — `C:\work\telarafly` | Historical Unity/C# asset/world viewer with CDR parsing, manifest/archive loading, NIF/world placement and OBJ exporter code | Read-only implementation reference, interpreted **through RiftWorld's existing TelaraHook adapter** | Direct runtime dependency, an in-Taxi Unity port, edits/builds in its source tree, generalized terrain/collision ownership |
| **RIFT game client** | Live actor state and movement response | A uniquely identified, freshly observed player and explicitly controlled game input | Assumptions based on stale process, prior build or camera-only yaw |

Source audits and limitations: [RR2_HANDOFF.md](RR2_HANDOFF.md), [RIFTWORLD_HANDOFF.md](RIFTWORLD_HANDOFF.md), [TELARA_FLY_REFERENCE.md](TELARA_FLY_REFERENCE.md). The **entire** Telara Fly repository is permanently read-only, including build and generated/cache writes.

## 2. Development data flow versus deployed data flow

### Development / import (offline, explicit)

`Telara Fly evidence (read-only) → RiftWorld's existing adapter → riftworld.patch/1 + navigation-build/1 + candidate-path/1 + obstacle evidence → Taxi import/validation → **Taxi-owned, local, versioned world bundle**`

`RR2 native-reader/action receipts → source-hashed historical evidence → Taxi importer/trace normalization → **replay fixtures + measured control response**`

The import program runs as a separate **build-time** operation. It can use validated source directories; none are searched automatically by an installed Taxi. The importer must distinguish unchanged source metadata from derived/requalified Taxi conclusions.

### Runtime (no sibling repos, no remote AI)

`Destination request → destination resolver → zone/world-package admission → local route query → corridor & trajectory → continuous feedback controller → Taxi-owned input adapter → RIFT`

`RIFT → Taxi-owned native pose/actor-facing reader → timestamped observations → progress/heading estimator → controller and recovery → UI/CLI status`

All callbacks and state transitions run in Taxi's process or in a narrowly scoped **bundled** native helper. The desktop GUI should never be responsible for holding keys or choosing the next steering action; use a headless CLI/simulator first.

## 3. Recommended modules, introduced only as needed

| Logical unit | Responsibility | Initial implementation |
|---|---|---|
| `taxi.contracts` | Versioned game owner, pose, route, world qualification, decision and receipt structures | M1: validated dataclasses/typed JSON |
| `taxi.replay` | Synthetic dynamics and imported original-source traces; deterministic output | M1: single CLI + fixtures |
| `taxi.live` | Exact Windows RIFT process/window/player/build acquisition and freshness | M1: scoped read-only interface |
| `taxi.input` | One held-key owner, W/A/D state, safe key down/up, STOP, independent release | M1: finite control only, then sustained holds |
| `taxi.steering` | Path arc-length, pure-pursuit/Stanley tests, bounded digital steering, coast/arrival | M2–M3: separate from input/GUI |
| `taxi.world` | Offline world-bundle reader, hash/check/coordinate transform, query | M4: no HKX parser |
| `taxi.destinations` | Reachable local endpoints, curated NPC/service roles and floor constraints | M4–M5: travel-to-only |
| `taxi.recovery` | Detect stale/blocked/deviating motion; local replans and finite budgets | M5 |
| `taxi.ui` | PySide6 route choice, progress, status, Go/Pause/STOP | M6; status subscriber |
| `taxi.cli` | `doctor`, `replay`, `plan`, `run`, `stop`, `trace` | Minimal at M1; expand at gates |

Keep a **single local controller** rather than microservices. Evaluate NumPy/SciPy if they shorten trajectory work; no computational optimization without measurement. A tiny packaged native .NET/Win32 adapter is acceptable when Python's access or release timing cannot meet measured targets, not as an excuse to bring RR2 into the runtime.

## 4. World-space and coordinate rules

- RIFT/RiftWorld source pose is `[X,Y,Z]` with **Y up**; walking/navigation is normally evaluated in **X/Z**, with Y used for floor, grade and clearance. Distances are **game source units**, not verified meters.
- RiftWorld's `rift-source-xyz` and `source-world-unit` metadata must remain explicit in the bundle, along with source zone/world scope, `transformToRr2Native` and its qualification. The original source map string `world` alone is **not** a validated live world-instance identity.
- **Do not silently accept an identity transform.** RiftWorld identifies landmark-reprojection candidate alignments; build scope and individual scenes/floors need their own evidence.
- **Telara Fly's generic `Assets/Export/ObjExporterScript2.cs` converts Unity-to-OBJ by negating Z.** RiftWorld's TelaraHook export instead documents original RIFT/Telara XYZ. These are different output paths: never apply or omit a Z flip merely because a file is `.obj`. Confirm source adapter, transform provenance, winding and landmark/pose reprojection first.
- Three-dimensional placement transforms, node matrices, mesh origins and CDR instance matrices have distinct meanings. Do not double-apply source matrices or equate render geometry with Havok collision.
- A path must retain a **specific surface/floor** and valid elevation transitions. X/Z proximity across different floors is not destination arrival or a traversable connection.

See [INTEGRATION_CONTRACTS.md](INTEGRATION_CONTRACTS.md) for planned versioned boundaries.

## 5. Geometry confidence and route authority

Evidence classes are intentionally independent:

| Observation | Supports | Does **not** establish |
|---|---|---|
| NIF/CDR/Telara render triangles | Visible terrain/object placement candidates | Solidness, current contact, floor traversability |
| Recast/Detour complete query | Candidate connected path in the **chosen** mesh | Correct game instance, full collision coverage, clearance to physical actor |
| Mapped decoded obstacle + swept-capsule checks | Scoped geometric nonintersections/collisions for included shapes | Unmodeled objects, dynamic blockers, complete-world clearance |
| Executed same-epoch Havok contact | Contact with the particular captured body/face and conditions | Every collision channel, all NPCs/obstacles, whole-zone path safety |
| RR2 observed successful traversal | One real player traversal under its exact path, build and epoch | Repeatability, a different path, uninterrupted journey, other zone |

**Concrete regression:** RiftWorld's November 23 bridge handoff records a banner pole **missing from the assembled map**. The Watch-temple → Guardian bridge → Tavril Plaza route completed only **in staged segments**. It saved 15 measured points but an uninterrupted single replay is **untested**. Taxi should import this as *historical traversed segments* and a future smoothness test, not a certified continuous clear corridor. The handoff's local artifact SHA and exact vertices are indexed in [RIFTWORLD_HANDOFF.md](RIFTWORLD_HANDOFF.md).

A candidate route is inadmissible when the requested endpoint, snap-to-mesh connectors, floor, transform, or essential region cannot be verified. The user may see it as a **proposal**, but input is not issued merely because a route exists.

## 6. Planning and continuous trajectory execution

### Stage A — Route admission

1. Get fresh player pose, actor-facing value and current world/build/session identity. Verify input ownership, STOP state, game foreground and version-supported reader.
2. Resolve destination to a **reachable approach region** (or explicitly unavailable), not blindly to a named NPC's body coordinate.
3. Verify local world bundle hashes/schema, source world, coordinate frame, transform qualification, floor, route completion and included collision evidence.
4. Compute a corridor using a **Taxi-bundled** query engine or an already-exported corridor. No live RiftWorld dependency.
5. Convert corridor to a feasible trajectory using corner curvature, actor radius/height and measured turn-rate and coast response. Distinguish `guide`, `optional`, `mandatory_passage`, `hard_stop` and `destination`.

### Stage B — Feedback control (one journey owner)

At each valid **fresh** sample: project current pose onto the forward route arc-length; compute lookahead according to speed, curvature, corridor width and measured sensor delay; choose desired heading and A/D steering. **Keep W held across ordinary guides**. Do not re-center on a passed optional guide or turn in place for every corner.

Avoid control chattering with calibrated hysteresis, minimum useful steering pulses, rate limits, finite key-down limits and explicit release receipts. Cornering remains conditional: if a bend cannot be made at the verified speed/turn radius inside clearance, choose an allowed slower movement strategy or stop as **required** by geometry, not to satisfy a guide index. A controller that achieves endpoint precision with repeated unnecessary stops fails M3.

### Stage C — Final approach and hard stops

An explicit hard stop ends a continuous span: verified approach, keys released, stationary observation, then resume the following leg when appropriate. The **final destination** is authoritative. Predict coasting and let the controller issue final release/settle with an independently acquired final same-actor XYZ/Y. Never infer arrival only from an input-worker `completed` flag.

### Stage D — Recovery

Separate (a) observation stale, (b) key delivery fault, (c) position unchanged while input was held, (d) cross-track violation, (e) genuine mapped obstruction, (f) possible wrong floor/zone. Choose bounded read-only reacquisition or a valid local replan; **do not** send repeated pushing input into the same blocked body. Each failure has a finite retry budget and machine-readable reason.

## 7. Game observation and held-input lifecycle

### Pose and heading

Use a Taxi-owned read-only reader to obtain executable SHA, process ID/start, player identity, zone, XYZ, **actor yaw with declared angle convention**, acquisition time, confidence and freshness. A camera matrix yaw, travel-course angle or old cached pointer is never silently promoted to body yaw. Track source timing and sequence advancement; failure to update counts as unavailable.

### Control authorization and release

- One controller owns the relevant RIFT window and pressed keys. It confirms current foreground, identity and session before input; manual input or another owner invalidates assumptions.
- Control frames record **requested versus actual** key transitions and source observations. `SendInput` success shows OS insertion only.
- Input-release worker/fallback must remain callable when steering stalls. Every terminal path—including crash/restart/focus loss—must be handled as a separate test case. A queued key-up is not evidence the game processed it.
- **STOP wins** over future movement, replanning and resume. Fail closed on release uncertainty and do not silently clear STOP/re-arm.
- Explicit test consent applies to the current target/session. Nothing in a prior RR2 VM receipt grants automatic input authority to an arbitrary physical RIFT process.

### Timing

Measure actual end-to-end response: sample collection age → data ready → trajectory calculation → input down/up → independently newer game response → released settle. Windows timers are not hard real-time. Set loop intervals and deadlines **from measured latency**, not an assumed 60 Hz game update. Use monotonic clocks within one runtime and preserve original acquisition timestamps and clock domains across imported traces.

## 8. Local destination and service catalog

A future local curated catalog focuses on **Sanctum Porticulum Master, personal bank, healer, auctioneer, auction-collection mailbox, and selected storyline quest NPCs**. A mailbox is a **service object**, not a special auction-collection NPC. Travel-only; no mail opening, item transfers, auction transactions, quest acceptance or portal interaction in the early scope.

Catalog entries require stable local ID, role, region/floor, evidence-backed anchor, **reachable approach region**, source history and presence/qualification. Historical NPC positions are search/display hints. A moving or absent NPC may force the destination to unavailable; Taxi does not blindly chase a transient unit pointer. [NPC_DESTINATIONS.md](NPC_DESTINATIONS.md).

## 9. Runtime/package verification

- Distribute a Windows x64 app with **all** modules, any small native helper, optional qualified map bundles and local configuration; no hard-coded `C:\work` or developer account.
- Execute offline replay and `doctor` without RIFT, internet, RR2, RiftWorld, Telara Fly, Workbridge, Python CLI or Git.
- For live acceptance, compare identical selected route/terrain and game build with RR2 historical behavior. Record actual simultaneous W+A/D and forward-key duty cycle, not just waypoint arrivals.
- Keep immutable source hashes and versioned import IDs; human-readable documentation links are **developer references only**.

See [VALIDATION.md](VALIDATION.md), [ROADMAP.md](ROADMAP.md), and the specific [sister-repository integration contracts](INTEGRATION_CONTRACTS.md).

## 10. Immediate implementation path

**M1:** offline `PoseSample/Route/ControlFrame/JourneyReceipt` fixture + CLI; import evidence without live input; then standalone, qualified pose and bounded key release.

**M2:** sustained straight travel and final settle.

**M3:** multi-bend path tracking with W held through guides and A/D adjustments while running, with accepted real-key-state and XYZ/yaw receipts.

Only **after M3** widen map coverage, NPC destinations, obstacle-aware detours and app/UI polish. The current repo contains **no implemented Taxi movement executable**.
