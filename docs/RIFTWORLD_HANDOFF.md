# RiftWorld handoff — maps, Detour, collision and landmarks for Taxi

**Read-only audit:** LEGION, 2026-11-23. **Source repository:** `C:\work\RiftWorld`, `main` at observed commit `0f154804eabf54608216c2c84a05468d8076a5cb`. This is research data and contract provenance, **not** a current runtime dependency or blanket claim that all world collision is solved.

## Responsibility boundary

RiftWorld reconstructs source geometry, CDR placed instances and collision evidence; prepares persistent Recast/Detour navigation builds; and publishes **candidate** paths. RR2 previously reviewed and executed selected candidates. Taxi should consume **locally packaged** routes/corridors and map evidence, then own its own world admission, player steering, input and arrival verification.

**Do not duplicate inside Taxi:** HKX decoding, NIF extraction, CDR tile/scene assembly, broad Silverwood rendering, bulk asset downloading, the Java Recast build pipeline or world research viewer. If a needed world attribute is not exported, first document the missing contract/field before implementing an equivalent general extractor.

## Source code and implemented formats

| Format / component | Source file | Key verified properties | Taxi use |
|---|---|---|---|
| `riftworld-telara-patch-v1` | `riftworld/core.py::import_patch` | TelaraHook report + OBJ; `sourceWorld`, source XYZ/Y-up, `rift-source-xyz`, manifest checks, unknown/landmark-based RR2 transform | Offline producer input; never blindly equate render OBJ with collision |
| `riftworld.patch/1` | `riftworld/core.py` | Content-based patch identity, geometry/placement hashes, coordinate frame, requested bounds, separated geometry/walkability/traversal evidence | Primary **world snapshot** input |
| `riftworld.navigation-build/1` | `riftworld/navigation.py` | Persistent Recast build descriptor plus hashed `detour.bin`; build cache identity binds source, profile and context | Bundle the qualified build or a normalized local corridor; runtime query implementation needs its own packaging decision |
| `riftworld.navigation-query/1` | `riftworld/navigation.py` | A query of the persisted build, with explicit requested/snapped endpoints and source qualification | Producer evidence; importer must verify endpoint connectors |
| `riftworld.candidate-path/1` | `riftworld/core.py::validate_candidate` | `complete/partial/unavailable`, point IDs/XYZ, source frame, transform-to-native, query and planner IDs, independent geometry/walkability/traversal evidence | Candidate route input, **not** automatic game input authorization |
| `riftworld.obstacle-aware-route/1` | `riftworld/obstacle_navigation.py` | Pinned obstacle layer/geometry, route and capsule checks, known geometry `clear/blocked/indeterminate` | Strengthen route confidence **inside the mapped scope** |
| `riftworld.destination-source-binding/1`, `destination-patch-binding/1` | `riftworld/destinations.py` | Exact patch or source-index binding; validates world/frame/bounds and preserves `floor/walkability/traversal=unverified` when not established | Build-time destination candidate import only |
| `riftworld.route-draft/1` | `riftworld/route_draft.py` | User-authored visual points with optional surface projection, **not floor authority** | Review/example format, not a trusted path |

### Field-level caveats from implementation

`riftworld/navigation.py` qualifies current builds as **"candidate navigation over render geometry; traversal and authoritative collision remain unverified"**. Its default agent profile declares cell size 0.25, cell height 0.125, agent height 1.8, agent radius 0.5, max climb 0.5, max slope 45°, region min size 4. These are **builder defaults**, **not** proven Atank dimensions, current run speed, world units in meters or universally valid collision tolerances.

`riftworld/core.py::validate_candidate` requires explicit source XYZ with Y up, source world/authority, `transformToRr2Native` metadata, unique point IDs and matching planner data. It distinguishes geometry ∈ {`render-mesh-approximation`, `measured`, `unknown`}, walkability ∈ {`estimated`, `unknown`}, traversal ∈ {`verified`, `unverified`}. A `complete` Detour result may still have **unverified** physical traversal.

`riftworld/destinations.py` checks patch/context binding but its source-binding path intentionally preserves `manual-unverified` or `geometry-derived-unverified` destination states. A correct schema and verified hash do not establish that an NPC exists on the correct floor or behind which side of a counter.

## Coordinate and world-identity trap

- Source geometry uses `X,Y,Z` with **Y up**; X/Z is the horizontal plane. Original values must survive the producer/consumer boundary.
- `sourceWorld=world` is a source map declaration. Same RIFT world-instance/zone, shard, interior and floor remain **independent questions**.
- `transformToRr2Native` may be `identity` with **landmark-reprojection-candidate** qualification; the assertion is not universally demonstrated. Preserve transform ID, matched landmark evidence and exact geographic scope.
- Render-only polys, estimated surface hits and endpoints snapped onto a navmesh do not certify vertical access, bridge grade, clearance or actual player reachability. Inspect requested versus snapped **both XZ and Y**.
- Handoff from Telara Fly must use source-format-specific transforms; see [TELARA_FLY_REFERENCE.md](TELARA_FLY_REFERENCE.md).

## Real physical regressions Taxi should keep

### A. Watch pillar / face 90 — November 22 LEGION (RIFT 1179)

`START-HERE.md` records a guarded Havok world-step contact and contemporaneous measured player blockage on a particular mapped pillar face. Forward progressed on open deck and ceased on contact; retreat succeeded. Detour/capsule checks and later RR2 physical route evidence showed a path avoiding the measured face.

The fixed Watch pillar out-and-back ended with **0.127** / **0.220** horizontal error, after a controller overshoot correction. The imported Detour destination arrived at **0.260 ≤ 0.300** error. Those are **scoped** measurements, not general proof that every CDR obstacle has an executable collision mesh.

### B. Watch temple → Guardian bridge → Tavril Plaza — November 23 LEGION

`HANDOFF-2026-11-23-SANCTUM-BRIDGE.md` records real traversal in **staged segments**, final stationary XYZ **(7377.9561, 871.7761, 3069.3726)**, median moving east-half horizontal speed **6.1 source units/s**, and keys released. Combined route has **15 measured waypoints** (file SHA-256 `2A0E497A08F34F8626960E8110149EE218A809C36E8659CEF87061792BC37952`). The path crosses source `world_7168_2816.cdr` placement **384**, mesh `A_C_guardian_bridge_01.nif`. A render deck report sampled **1,431** points with zero gaps along its selected deck lines.

**Critical negative evidence:** a banner pole encountered on the first approach was **absent from the assembled map**. The controller tripped window/cross-track limits, released keys, and completed later shorter runs. A *single unbroken* replay along the saved 15-point route was **not performed**. This is ideal as a Taxi **continuity and unexpected-obstacle regression**, not yet a fully admitted clearance route.

### C. NPC location scope

`MAGELO-SANCTUM-WATCH-2026-11-14.md` recorded **171 historical location entries** (25 Watch, 146 adjacent), and `LIVE-NPC-SURVEYS-2026-11-14.md` merged **3 scoped exact-instance observations** from live addon captures. The latest bridge handoff identified a **Quicksilver Medic near the Watch temple**, but city-side scans did **not** verify a healer position. A historical guide mentions Thontic's Row; that is only a lead.

For Taxi, named-location and service-role evidence must stay separate from current NPC presence, correct height/floor and **reachable approach**. The initial curated roles are Porticulum Master, personal banker, healer, auctioneer, mailbox, selected story quest NPCs; no broad NPC directory or service clicks.

## Outstanding research blockers relevant to Taxi

| Missing proof | Navigation effect | Planned handling |
|---|---|---|
| Full collision coverage including unmodeled pole, benches, rails, thin obstacles | Smoothing may cut into solid objects | Keep mapped route scopes limited; preserve unknown obstacles and STOP/replan |
| Whole-zone connected navmesh, especially historically disconnected Silverwood seams | Some destinations may return no route | Declare partial/unavailable; never bridge gaps with a straight line |
| Trusted source-to-live transform and world/floor identity for every patch | Valid source path may be on wrong surface or location | Validate explicit coordinate, scene, instance and floor before admitting |
| Physical actor clearance / slope / step response | Recast default profile may be wrong | Calibrate with original current-game receipts, not source guesses |
| Query portability/Java dependencies | Taxi installed alone may not read raw `detour.bin` | Define validated exported corridor format first; implement/bundle local query engine if needed |
| Live dynamic blocker identity and obstacle freshness | Route may be blocked even if static corridor looked open | Wait for scoped live evidence; classify blocked without uncontrolled pushing |
| NPC role, service access and exact approach | Name record not enough to deliver to a banker/medic | Use curated per-location evidence and independently check arrival |

## Export/import design suggested for M4 (Taxi-owned)

A local `taxi.world-bundle/1` package must bind original schema/version, source commit, exported file SHA, navigation build/cache ID, world/coordinate frame, height/floor identity, actual geometric coverage, corridor points/polygons, obstacle clearance classification, destination anchors and import-level qualification. The importer refuses partial/unavailable unless explicitly stored for display-only.

Choose whether to bundle a self-contained Detour query library **after** confirming binary compatibility; do not assume `detour.bin` is directly readable by Python or means every path is safe. Until then, an **already validated, scoped corridor** can be packaged with no Recast/Java runtime. Do not borrow RiftWorld process IPC or invoke `python -m riftworld` during a trip.

See [INTEGRATION_CONTRACTS.md](INTEGRATION_CONTRACTS.md) for proposed schemas and tests.

## Source register (surveyed bytes on LEGION)

| Source relative to `RiftWorld` | SHA-256 | Relevance |
|---|---|---|
| `ARCHITECTURE.md` | `7ed0772b60c9fbc4c09d170488109fe2d19072577731f1a896a632bbfab68c1` | World/Detour contracts, coords and qualification |
| `START-HERE.md` | `472cd0df3a6b8e337ce2c0e00674cede89998f32d258af911c4ec3a416a09e5a` | Latest pillar/route status |
| `HANDOFF-2026-11-23-SANCTUM-BRIDGE.md` | `344e15578ec9b796adc403629898b221efcad88533e386ee79150691c6017ef2` | Measured staged bridge, missing pole |
| `riftworld/core.py` | `bf62cb53abe8d39b4789af49fbc7037617613f3133c3113357ce9243f482d688` | Source-coordinate import and candidate validation |
| `riftworld/navigation.py` | `0e5bad994f6dbae3f875070e61650b8fb0f342cd0ffaf1c153589c244eefc023` | Recast profile/build/query |
| `riftworld/destinations.py` | `c5b8a4d653f0a7c3e2954d7acc20c0c272b5e65efa9a34e8be5a6eea72cd6686` | Source/patch destination bindings |
| `riftworld/obstacle_navigation.py` | `1c83678c34339eee0d2035a513c1c8a0d28a4550fdfc51fe8f9dc076b14359f4` | Geometric obstacle route checks |
| `LIVE-NPC-SURVEYS-2026-11-14.md` | `6e474769ccbacd189428dad20e1be268e99009556cc6a09a2f19f12fb7c74eac` | Live vs historical NPC distinctions |
| `MAGELO-SANCTUM-WATCH-2026-11-14.md` | `28f60813a76a9436602610bb25d18f78708b31e38f34c6aabbcdd2348da3bd6f` | Historical NPC positions |

Original geometry/manifests under ignored `artifacts`/`cache` may exist only on a particular machine. Do not equate tracked documentation with an independently packaged and hash-verified world bundle. No RiftWorld files were modified during this review.
