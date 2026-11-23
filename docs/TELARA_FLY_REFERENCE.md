# Telara Fly reference — exact read-only source inventory

**Reference-only audit:** LEGION, 2026-11-23. **Repository:** `C:\work\telarafly`, `master` at observed commit `41aacc0485ed2c90ceb1df7cdb7653853cc52d18` (commit dated **2025-11-01** in Git history). Author's README describes a **Unity3D RIFT world-model viewer**, not a ready-to-use live navigation engine.

## Absolute repo protection

**Never edit, format, build in, generate into, pull, reset, checkout, install inside, or otherwise mutate `C:\work\telarafly` or its Git state.** This includes build caches, Unity metadata, logs, viewer-generated exports and nested tool outputs. The instruction is permanent and is also recorded in `C:\work\RiftWorld\AGENTS.md` (2026-11-22).

RiftWorld has a separate **owned** extraction adapter under `tools/TelaraHook/` and its own output/cache directories. Use that existing source-based work; Taxi is only a consumer. No Telara Fly executable, Unity editor or DLL should be bundled as an implicit Taxi runtime dependency.

## What Telara Fly source actually shows

| Original source | Verified behavior | Potential use in research | Limitation |
|---|---|---|---|
| `README.md`, `RUNINGREADME.txt` | RIFT model/world viewer; camera moves with WSAD, Q/E altitude in *viewer* | Read historical display and control terminology | Viewer movement is not an RIFT player's movement controller |
| `telarafly.cfg` | `ASSETS_DIR`, `ASSETS_MANIFEST`, `REMOTE_ASSETS_URL`, `USE_REMOTE_ASSETS` and visibility/loader settings | Identify original local vs streaming asset entrypoints | Example values are historical; remote asset URL/behavior not current game evidence |
| `Assets/RiftAssets/Manifest.cs`, `AssetDatabaseLocal.cs`, `AssetDatabaseRemote.cs` | Manifest/asset database abstractions; local PAK and optional remote asset retrieval with temp caching | Source provenance, archives and missing-asset troubleshooting | Never make Taxi a game asset downloader |
| `Assets/WorldStuff/CDRParse.cs` | CDR map parsing: zones `113`, scenes `114`, point lists and localized names; `worldName + "_map.cdr"` | Trace scene/region identity and polygon provenance | Map scene polygon is not necessarily a collision/navigation polygon |
| `Assets/WorldStuff/CDRItem.cs`, `Assets/ObjectPosition.cs` | Named/indexed CDR objects, positions and render object placement | Source placement metadata mapping | No guarantee of Havok contact/filter completeness |
| `Assets/GameWorld.cs`, `Assets/WorldSpawn.cs` | Static objects, spawn list, world name; spawn point `Vector3 pos` and angle | Understand coordinate sources and cached spawn records | Spawn list is not an NPC-service directory or validated in-game path |
| `Assets/WorldLoadingThread.cs` | Tile/object jobs, terrain/object KD-trees, threaded streaming and visibility culling | Understand repeated placement loading and why visible-only exports may have limited coverage | A viewer loading radius does not establish full world/map closure |
| `Assets/NIF/*` | NIF scene/model reading; material/mesh representation | Reference asset-to-render relationships via RiftWorld | Render triangle ≠ collision solid |
| `Assets/Export/ObjExporterScript2.cs` | Unity mesh-to-OBJ conversion, world-space `TransformPoint`, **negated Z** and material/normal handling | Warn against cross-format coordinate mistakes | This generic exporter does **not** by itself define the RIFT-native coordinates of RiftWorld's separate hook |
| `Assets/MapTeleport.cs` | Map/viewer behavior by name; inspect only if needed | Historical viewer feature reference | Do not assume it exposes usable RIFT client teleport or movement control |

**No live NPC service semantics**, such as which character is a healer, banker, auctioneer or Porticulum Master, were established by the above source audit. CDR scene labels or local spawn positions are **not sufficient to resolve service identity or reachable interaction approach**.

## Crucial coordinate distinction

`Assets/Export/ObjExporterScript2.cs` comments that it converts from Unity left-handed mesh space to OBJ right-handed by negating Z at vertex emission: `v x y -z` (and applies matching Z conversion to normals). Its own comment acknowledges that conversion depends on the consuming tool.

Meanwhile, RiftWorld's `tools/TelaraHook/README.md` explicitly says its separate `riftworld-patch.obj` uses original **RIFT/Telara XYZ coordinates**, and its `riftworld-patch.json` preserves source instance transforms, mesh matrices, OBJ offsets, source NIF names and source-matching tolerance details. The adapter matches CDR placements only on unique filename/position/scale/quaternion evidence and leaves ambiguous or collision-only records unresolved.

Therefore a Taxi importer must **never infer axis flipping solely from `.obj` extension**. Validate the precise producer schema and the relevant landmark/native pose before applying any coordinate transformation. Never double-apply object/node matrices.

## Existing working boundary: RiftWorld's TelaraHook

Verified `C:\work\RiftWorld\tools\TelaraHook\README.md`:

- Its README prohibits altering or building the original `telarafly` repository.
- Separate preparation on AMD-DESKTOP uses an installed standalone viewer runtime and SHA-pinned inputs. The isolated hook is RiftWorld-owned.
- Output: `riftworld-patch.obj` plus `riftworld-patch.json`, with export report schema `riftworld-telara-patch-v1` validated by `riftworld/core.py::import_patch`.
- The hook tracks source instance transforms/mesh matrices and correlates placements only when unique matches meet its tolerances; collision-only records remain unresolved.
- On LEGION, the source-based CDR-7304 classifier compile lane reported 21 passing assertions, but the required standalone viewer runtime binaries were missing. **Do not claim a full hook/runtime build succeeded on LEGION.**

All future extraction improvements should occur in **RiftWorld's existing adapter or its build-time export tools**, not Telara Fly and not Taxi's runtime. In this documentation task, *no other repositories are edited*.

## What to reuse — and what to decline

**Useful to preserve as source evidence:** CDR scene/zone/member mappings, asset and manifest identity, NIF placement/matrix conventions, render OBJ export path/source hash, uniqueness conditions for instance matching, camera visibility/loading radius implications, origin/axis conversion history.

**Not suitable to port into Taxi:** Unity scene viewer, dynamic terrain streamer, asset download path, generic OBJ exporter, animation renderer, NIF parser, game-asset database or any "viewer's camera moves" code as player movement logic. Taxi's new product differentiator is local **continuous actor steering along a qualified route**.

## Future read-only investigation questions

1. When RiftWorld reports an unmapped pole, which Telara Fly CDR/scene placement and NIF model source, if any, can explain the omission? Read-only source examination only; implementation in RiftWorld.
2. Do any generic export paths apply Unity Z negation while the TelaraHook source-coordinate path does not? Record file/path-specific transform tests and sampled landmark reprojections.
3. What are the exact source-world and scene/floor identities, and how stable are they after a RIFT update? CDR source IDs are not the same as a current RIFT process/world-instance ID.
4. Which asset loaders are complete for the chosen tile/collision inputs? An extraction containing only rendered objects within the viewer loading radius is not whole-area closure.
5. Is any proposed source code selection allowed by original repository licensing and attribution? Review before copying; research knowledge can be restated independently without copying a bulk library.

## Pinned source register (local file SHA-256)

| Original file | SHA-256 | Role |
|---|---|---|
| `README.md` | `946cf1377fa4ba8e013515068e5ad4156b01ec09e436d6935b8d6c11e65ba147` | Original purpose |
| `RUNINGREADME.txt` | `5bfedf6b7fa5ac282f540c7a51611d6787831df8993ecfc791cb7211df14b4a2` | Viewer movement/asset setup |
| `telarafly.cfg` | `ba884ad77ed8a5292b498a0b648befcbb169708f09bc9556107164571e7dee34` | Asset/remote configuration |
| `Assets/WorldStuff/CDRParse.cs` | `69c9270e1cd54336ab8e24138fc6ad687eda6112cf1271a3d1fcae45b835e34a` | Scene/zone source |
| `Assets/WorldStuff/CDRItem.cs` | `a31ca46ce3782a1f4b72beec464da9a56cbb90316a0e2929e716ce71f4141ef4` | Placed-object metadata |
| `Assets/GameWorld.cs` | `0e0a3912d1f0562c96c7ab10ff8c702ab295d9ce98ab98254ca65f6e7b1b5bd2` | World/static objects |
| `Assets/WorldSpawn.cs` | `12beb29b783c3876fcdabd2ebe9798cc2026bb372c7928f14e769d44ea222b3f3f9d898` | Spawn fields |
| `Assets/WorldLoadingThread.cs` | `f0f3ae7d9599c0488e95ea2c207f6a8bf6074a91bb2059b066c3d171340abef6` | Terrain/object streaming |
| `Assets/Export/ObjExporterScript2.cs` | `851aa8a90194070d9814c358c656d26e6eb764ed44191c25fc486daf8be748c1` | Unity OBJ coordinate hazard |
| `Assets/RiftAssets/AssetDatabaseLocal.cs` | `96ceca0873a515839cb73efad8d49fdc58bcc33e40792b22432d04f5dbe75aec` | Local assets |
| `Assets/RiftAssets/AssetDatabaseRemote.cs` | `4ad42c20e8498107ad8d04100d9a5b3c685a62a5d33145a372792f6a7ebcad00` | Remote asset path in source |

## RiftWorld adapter source referenced separately

`C:\work\RiftWorld\tools\TelaraHook\README.md` SHA-256 `68cecfe06fc4a04ad8ac57f2343c54c4dcfa9d9b70893b895d13dc6b7c630aca`. Prefer this implementation's **documented output contract**, not assumptions about generic Unity exporters.

All hashes describe inspected bytes on the date above, not a license to use binaries or guarantee against source drift. No Telara Fly execution, generation or write operation was performed for this inventory.
