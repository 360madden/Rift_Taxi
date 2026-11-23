# Proposed integration contracts — RIFT Taxi's independent runtime

> **Status:** Taxi-owned interface design, **NOT implemented**. Last reviewed 2026-11-23. The distinct upstream RIFTWorld/1 and RR2 schemas named below are **existing source facts**. The example `taxi.*` schemas are **new proposals** and must not be represented as already supported by either producer.

## 1. Two independent intake pipelines

| Intake | Input/source | Local output | Timing |
|---|---|---|---|
| **World** | Validated RiftWorld `riftworld.patch/1`, `riftworld.navigation-build/1`, `riftworld.candidate-path/1`, optional `riftworld.obstacle-aware-route/1`, destination bindings and complete referenced files | Immutable `taxi.world-bundle/1` under Taxi's private data directory | **Offline build/import only** |
| **Motion evidence** | Original RR2 current-build/retained pose, facing, action timing and post-release receipts, with hashes | `taxi.motion-trace/1` and deterministic replay fixtures | **Offline import only** |
| **Live pose** | Taxi-owned native read-only process observer | Fresh `taxi.pose/1` samples | **Runtime** |
| **Live control** | Taxi-owned exclusive input owner + key-release worker | `taxi.control-event/1` sequence and `taxi.journey/1` receipt | **Runtime** |

No installed Taxi component should import or invoke sibling projects or create a listener requiring Workbridge/AI/network. `python -m riftworld` and RR2's `physical_rift.py` are useful **development commands only**.

## 2. Versioned envelope (proposal)

Every bundle and retained trace requires:

- `schema` (exact version), `artifactId` (content-derived digest), `createdUtc` and original source-hash manifest;
- input provenance: repository name + commit SHA, producer source format and file paths **relative to the imported artifact root**; absolute source path remains optional historical evidence, not a required runtime locator;
- known game executable build/hash, host and process/player identity when the **source is live capture**, not when the source is purely offline geometry;
- coordinate frame: `frameId`, `axisOrder=["x","y","z"]`, `upAxis="y"`, `units="source-world-unit"`, transform ID/kind/qualification and scope;
- status and evidence class **per layer**: geometry, walkability, physical collision, traversability, zone/floor, destination presence. A high confidence in one layer must not automatically promote another;
- normalized point type semantics: `guide`, `optional`, `mandatory_passage`, `hard_stop`, `destination`; plus required approach height/tolerance where known.

Avoid a fake signature field. SHA-256 binds content **integrity** but does not authenticate the original RIFT client or research provenance on its own.

## 3. Upstream shape names we must preserve (already real)

| Upstream identifier | Real producer | Distinguishing fields / gate |
|---|---|---|
| `riftworld.patch/1` | `riftworld/core.py` | `patchId`, world/coordinate context, files and content SHA, evidence |
| `riftworld.navigation-build/1` | `riftworld/navigation.py` | persisted navigation manifest and `detour.bin` hash; profile/context/cache identity |
| `riftworld.navigation-query/1` | `riftworld/navigation.py` | query result, requested/snapped start/goal, source build |
| `riftworld.candidate-path/1` | `riftworld/core.py` | `candidateId`, `status` = `complete/partial/unavailable`, points, `transformToRr2Native` and separate evidence labels |
| `riftworld.obstacle-aware-route/1` | `riftworld/obstacle_navigation.py` | exact obstacle layer, geometry/route checks, `knownDecodedGeometryStatus` = `clear/blocked/indeterminate` |
| `riftworld.destination-source-binding/1` + `riftworld.destination-patch-binding/1` | `riftworld/destinations.py` | patch/source identity; unresolved floor/walkability/traversal intentionally remain unverified |
| `native-current-position-candidate-summary/1`, `native-current-facing-summary/1` | RR2 `scripts/physical_rift.py` | scoped native acquisition and subject identity, **not** Taxi's output shape |
| `native-continuous-move` family | RR2 `scripts/continuous_move.py` | action/release/result evidence; transfer only after exact receipt replay and source audit |

**Adapter rule:** validate the real upstream object first, copy source IDs and raw hashes intact, then derive a new Taxi representation. Do not rename `partial` to `complete` or `candidate` to `verified` for convenience.

## 4. Proposed world-bundle sketch (illustrative, not real export)

This structure shows **required information categories**, not a currently supported JSON schema or invented map data. `null` means genuinely unavailable.

```json
{
  "schema": "taxi.world-bundle/1",
  "bundleId": "SHA256_OF_CANONICAL_CONTENT_PLACEHOLDER",
  "source": {
    "repo": "RiftWorld",
    "commit": "EXACT_COMMIT_SHA",
    "sourceSchema": "riftworld.patch/1",
    "patchId": "SOURCE_PATCH_ID",
    "navigationBuildId": "SOURCE_BUILD_ID",
    "files": [
      {"path": "source/patch.json", "sha256": "EXACT_HEX_SHA256"}
    ]
  },
  "world": {
    "gameBuildSha256": null,
    "sourceWorld": "world",
    "liveZoneIdentity": null,
    "worldInstanceQualification": "unverified"
  },
  "coordinates": {
    "frameId": "rift-source-xyz",
    "axisOrder": ["x","y","z"],
    "upAxis": "y",
    "units": "source-world-unit",
    "transformToLive": {"kind": "unknown", "qualification": "unverified"}
  },
  "coverage": {
    "area": "SCOPED_AREA_ID",
    "floor": null,
    "obstacleCoverage": "partial",
    "traversalQualification": "unverified"
  },
  "corridors": [],
  "destinations": []
}
```

**Validation:** uppercase placeholder and null fields make this **deliberately non-executable**; never ship or run against RIFT using this example. Actual canonical digest/ID semantics must be defined in code and verified with tests.

### Persisted Detour versus pre-exported corridors

**Initial M4 strategy:** package a bounded, verified corridor and its endpoint/clearance evidence from an existing RiftWorld query. It requires no runtime Java/JPype/Recast or external RiftWorld.

**Later option:** bundle a compatible, self-contained Detour query implementation if performance and tested mesh/binary compatibility justify it. A raw `detour.bin` by itself is **not** proof that Python can load and query it or that the current actor can traverse it. Include required upstream revision, builder profile and binary compatibility tests.

## 5. Proposed live pose and control semantics

### Pose (`taxi.pose/1` — proposed)

Required: host; current executable path/SHA/build; PID/process start; RIFT window identity/foreground state; player/unit ID; current world/zone/floor if qualified; current X/Y/Z; facing yaw plus orientation basis/source; native observation timestamps and sample-age/freshness reason. Optional: speed and source clock alignment. When yaw or XYZ is unavailable, **do not substitute 0**.

### Control (`taxi.control-event/1` — proposed)

Required: journey epoch, actuator owner, target process/window, key, requested press/release time, actual OS insertion time/result, release outcome, independent post-action observation ID, STOP state. W/A/D may overlap for steering during running; no two conflicting A/D owners. Separate `insertionSucceeded`, `gameResponseObserved` and `arrivalVerified`.

### Journey (`taxi.journey/1` — proposed)

Required: destination ID/approach and tolerance, route/bundle IDs, typed hard-stop obligations, timed measured path progress along arc-length, optional guides skipped, key timeline, drift/obstruction events, retry budget, final post-release fresh pose and settled-state evidence. Success is **arrived** only after independent game-state observation. STOP, BLOCKED, release fault and source unavailable remain separate terminal states.

## 6. NPC and service destinations (small initial scope)

Curated roles: `porticulum-master`, `personal-bank`, `healer`, `auctioneer`, `auction-mailbox`, `story-quest`. The mailbox is a **mail delivery/auction collection service object**, not an invented "auction collector NPC." This phase only travels to an independently reachable approach. No service UI automation.

Local ID remains stable across sessions; transient RIFT unit IDs do **not**. Each item carries historical vs current presence, source timestamp/hash, world/floor, candidate NPC/spawn coordinates and separately validated approach polygon/XYZ + final acceptance tolerance. A named NPC behind a counter is not itself a free-space endpoint.

## 7. Build-time import CLI (proposed)

Plan minimal commands; these are **not yet implemented**:

```text
rift-taxi import-world --source-folder <EXPORTED_BUNDLE> --out <NEW_LOCAL_PACKAGE>
rift-taxi import-trace --rr2-sources <ORIGINAL_RECEIPTS> --out <NEW_TRACE>
rift-taxi replay --trace <TRACE> --route <ROUTE> --controller pure-pursuit
rift-taxi doctor --offline
```

The importer verifies file hashes, path containment/no traversal, supported schema, numeric finiteness, coordinates, exact source world, endpoint snaps, route status, obstacle coverage and unknown floor handling. It copies only the files the package needs, writes atomically and refuses accidental overwrites. It records **source** qualification separately from any **Taxi validation**.

## 8. Fail-closed acceptance matrix

| Input condition | Import/use outcome |
|---|---|
| Valid historical world patch, no proven game transform | Allow stored **review-only** map; refuse live route admission |
| Full Detour path, traversal unverified | Candidate route only until relevant physical corridor qualified |
| Partial/unavailable Detour result | Never execute as a complete journey |
| Unknown start/goal snap or wrong floor Y | Refuse route until same surface/connector verified |
| Valid mapped obstacle layer with gaps | Only covered geometry may support local clearance claims; unknown corridor unavailable |
| Different RIFT executable hash or process-start | Reacquire/requalify live reader and journey; no cached addresses |
| Cached/nonadvancing pose or unverified actor yaw | No continuing held forward/steer based on stale facts |
| Controller STOP, focus/owner loss or release fault | End or quarantine journey; no silent re-arm |
| Historical NPC position, live NPC absent | Destination may be a **historical place** if a valid approach exists; do not claim NPC presence/service ready |
| RR2/RiftWorld/Telara Fly not installed | **Expected normal condition** for packaged Taxi |

## 9. Initial tests that make these boundaries real

- Import one source-hashed RiftWorld candidate and verify exact field mapping, coordinate retention, source SHA and replay.
- Deliberately corrupt one original bundle file and confirm import refusal.
- Flip Z as the generic Telara Fly exporter would; reject mixed- or mismatched-coordinate input against the trusted source binding.
- Reject mismatched player zone, floor elevation, build, stale yaw and old PID.
- Compare a single paused/stop-at-each-guide RR2 trace versus a Taxi simulated continuous multi-bend trajectory with identical physical parameters.
- Use RiftWorld's **staged** 15-point Sanctum bridge route as a **future** continuity test with the missing pole marked unknown. A saved route is not clearance certification.
- Package and repeat offline replay in a clean Windows folder without `C:\work` access, siblings, network or AI.

Source-specific audit notes: [RR2_HANDOFF.md](RR2_HANDOFF.md), [RIFTWORLD_HANDOFF.md](RIFTWORLD_HANDOFF.md), [TELARA_FLY_REFERENCE.md](TELARA_FLY_REFERENCE.md). Product acceptance: [VALIDATION.md](VALIDATION.md).
