# Current RIFT Taxi handoff — November 27, 2026

## November 28, 04:40 PHT — unified desktop application launcher

Consolidated checkpoint 7538ab0 passed hosted CI 46064907589. Retained the same canonical research/product-consolidated-20261128 branch and PR #26, avoiding another disconnected branch. New rift_taxi.app and installed rift-taxi-app entry point provide a local desktop chooser for the synthetic demo or a pinned imported-world catalog. Explicit expected catalog SHA, validated inventory, explicit anchor selection and fresh package validation on open; path/pin edits invalidate stale inventory. Direct demo/world command modes also available. No network, game access or movement. Three new launcher tests passed and all 66 world tests passed (2.018s). Actual LEGION Tk 9.0.4 widget smoke verified both launcher modes, wrong-pin refusal, stale-selection clearing, explicit anchor selection, and both existing viewers against the retained accepted route with zero callback errors. README documents the launcher. RIFT PID 12092 responding in current process check; in-world actor not verified. Original dirty checkout preserved. New exact-head hosted CI and installed-wheel verification pending. Next: exact-commit package, improve local journey-state workflow using synthetic-only execution, and keep physical qualification separate.


## November 28, 04:37 PHT — consolidated product and catalog construction

Prior desktop XYZ checkpoint 84fa2d5 passed hosted CI 46031663761; it was 19 commits ahead of the journey development base dc22fe5. Reused its clean LEGION worktree and cherry-picked the three independently tested catalog-builder commits 7ac7490, 6e5bcaf, dd1acc5 without conflict. All 66 world tests passed on LEGION in 4.184s. Built a new catalog from both privately retained packages using their previously pinned original catalog metadata; the generated catalog was byte-identical by SHA256 7902202b3ccf80a2c1961279873e8b7896a55f0023c7f43e942e8308fd323efa. Both routes planned successfully (26.105297766896133 and 15.293361390774125 source units). Added installed rift-taxi-world-catalog entry point. This is the consolidated product branch research/product-consolidated-20261128, targeting research/journey-automation-reporting for review; no main merge. Original dirty checkout and private assets preserved. RIFT PID 12092 responding, in-world state not independently verified. Exact-head hosted integration CI pending; physical qualification and new installed-package test remain outstanding.


## November 28, 00:12 PHT — desktop XYZ position review

Prior position review checkpoint a4c3dce passed hosted CI 46031270304. LEGION checkout clean at start; RIFT PID 12092 responding, in-world state still not qualified. New branch research/product-position-desktop-20261128 adds the imported-world viewer's Review XYZ position dialog. Reuses existing review_position, separate XYZ/XZ/Y tolerance inputs, bounded vertex and segment lists, explicit existing-vertex selection and route recalculation. Segment projections remain informational; no automatic binding. Every input edit clears old candidates and disables apply; invalid numeric inputs refused. Actual Windows Tk 9.0.4 smoke against the retained accepted route exercised dialog opening, a different existing vertex, no implicit source change, stale/invalid input refusal, explicit confirmation and route recalculation, and restoration of the original source. All 59 world tests passed in 2.351s; both viewer widget smokes passed with zero callback errors. No physical qualification, game input or screenshot-based inspection. Original checkout/private packages untouched. Exact-head hosted CI pending. Next: consolidate validated development heads, improve position and destination workflow, and separately qualify the current RIFT session through read-only evidence.


## November 28, 00:09 PHT — source-position review and exact-commit package

Map selection checkpoint 427e5df passed hosted CI 46030421044. A clean exact-HEAD wheel was built and installed offline into isolated artifacts/release-wheel-427e5df-20261128/venv. Wheel 318720 bytes, SHA256 739399781269649d689ec060dfbe46223ca428d6040fbd336557bb87d0648831; installed Tk smoke SHA256 ccc4ee135cc6fb4ded82bea1387d0a1339dfd2e610efcc1dc905a1df9ca6d3a7; release-receipt.json retains identity. Installed search, automatic recalculation, map click and both viewers passed with zero callback errors. Not a public release or reproducible-build claim. New isolated position-review worktree adds world_route_graph.review_position and locate CLI: full 3D clamped segment projection, separate XZ/Y limits, bounded deterministic candidate lists, original source identity and distinct overlapping candidates. No snapping, automatic start binding, coordinate transform or movement authority. Four new tests; all 59 world tests passed on LEGION in 2.308s. Both original retained catalog routes returned one exact source vertex and one nearby segment at their original start with .5 XZ/Y limits. RIFT PID 12092 responding, actual in-world state not verified. No live input. New hosted CI pending. Next: improve destination/position review integration, retain independent physical qualification gate and test current session read-only when appropriate.


## November 28, 00:03 PHT — interactive imported-world source selection

Previous destination UX checkpoint c8be8fb passed hosted CI 46021567142. LEGION reachable; RIFT PID 12092 responding, in-world actor state not verified. Added map_pick and actual Tk canvas source selection to the offline world viewer. Pixel hit testing admits exactly one existing graph vertex; overlapping/nearby vertices remain ambiguous, profile/header clicks are excluded, stale scene invalidated on redraw. No arbitrary XYZ connector or execution authority. Two new headless tests; all 55 world tests passed on LEGION (2.182s). Actual Tk 9.0.4 desktop smoke against retained accepted route clicked a unique interior vertex, verified source control and route recalculation, restored original source; search and exclusions also passed, zero callback errors. Synthetic viewer still passed. No screenshot-based visual inspection, physical qualification or live input. Original dirty checkout untouched. New hosted CI pending. Next: exact-commit packaging and offline position-to-route review, and separately verify live session via read-only means before physical qualification.


## November 27, 23:03 PHT — destination search and immediate route preview recalculation

Prior desktop checkpoint 40b506f passed hosted CI 45950282005. LEGION reachable; fresh process query found no RIFT process, so physical qualification was not attempted. Isolated worktree artifacts/product-destination-ux-20261127-2302. Added case-insensitive multi-word destination filtering by route ID and catalog label; never silently substitute a destination. Unmatched search clears selection and stale route. Explicit source/destination selection and edge exclusions now immediately recalculate the offline preview. One additional headless regression; all 53 world tests passed in 3.344s. Actual Tk 9.0.4 smoke on LEGION verified unmatched-search clearing, case-insensitive search, explicit selection, all-edge exclusion producing no-route, and clearing exclusions restoring route-found (26.105297766896133 source units). Synthetic viewer also passed; zero callback errors. No screenshots, live game input, physical qualification or raw asset uploads. New hosted CI pending. Original dirty checkout preserved. Next: improve interactive map selection, package exact-commit release artifact, and independently qualify current game session when available.


## November 27, 14:10 PHT — actual Windows desktop and wheel smoke

Imported-world viewer checkpoint 62779a6 passed hosted CI 45949873149. Added bounded scripts/desktop_viewer_smoke.py to invoke actual production Tk launch functions, select source/destination, invoke preview, verify mapped canvas and highlighted route, collect callback errors and close deterministically. LEGION Python 3.14.10/Tk 9.0.4: synthetic entrance-to-bank 16.000 units, 34 canvas objects and four highlighted lines; original accepted route 26.105297766896133 source units, 112 objects and 70 highlighted map/profile lines; original leg-2 route 15.293361390774125 source units, 52 objects and 30 highlighted map/profile lines. All passed with zero callback errors. This is actual widget/render-object verification in the executing Windows session, NOT screenshot or human visual inspection, and no game input.

Added installed rift-taxi-local-viewer entry point. Built wheel with isolated build dependencies, then installed offline without dependencies into a fresh venv under ignored artifacts/desktop-wheel-20261127-1410. Wheel rift_taxi-0.1.0-py3-none-any.whl, 317348 bytes, SHA256 a75d3e69b613d675cf884cd8d4d859fb305cf9757153dfcb347bfeeb67f5e73b. Both installed viewer executables passed --help; isolated Python -I imported actual site-packages modules and ran the desktop smoke script against installed synthetic and original accepted route viewers, same counts and zero errors. Private receipts desktop-widget-smoke-leg2-20261127-1410.json and desktop-widget-smoke-installed-20261127-1410.json under original ignored artifacts. Wheel was built from this checkpoint's runtime sources before commit/handoff, not a published exact-commit release artifact. No global installs or raw source uploads. New hosted CI pending. Next priorities: current-session read-only status, improve route/destination usability, and exact-commit release build; visual inspection remains outstanding.


## November 27, 14:07 PHT — imported-world graphical preview

Shared intake checkpoint fd8cd23 passed hosted run 45949569103. New isolated worktree artifacts/product-world-viewer-20261127-1405 adds world_route_viewer, with local vertex A* planning, explicit source alias and route-destination selection, blocked-edge alternatives, XZ projection, full source XYZ scene data, cumulative-distance/Y elevation profile, optional Tk desktop and standard-library SVG export. Review-only classification remains explicit; no game process access, movement, clearance or transform authority. SVG serialization escapes source strings and contains no active content or external resources; exports refuse overwrite. Five headless regression methods added, all 52 world tests passed on LEGION. Two private original-package SVGs generated and XML-checked in artifacts/m4-world-review-20261127-1108: viewer-accepted-20261127-1406.svg SHA256 267db4eadcb8fd8e2e0f0d7f9382df88d5703215b337404e1e6c53a9dfbe852c; viewer-leg-2-20261127-1406.svg SHA256 f8e7bf994fc52872a9e37798376834325e2d8f4375bf940678a34057f49620ff. Neither original geometry nor generated previews uploaded. Actual desktop launch and visual inspection remain outstanding; the headless tests do not certify them. New exact-head CI pending.

Commands: python -m rift_taxi.world_route_viewer CATALOG --catalog-sha256 SHA --anchor-route ROUTE desktop ; or replace desktop with svg --start ROUTE:0 --destination ROUTE --out NEW.svg. Installed console entry: rift-taxi-world-viewer. Next prioritize a real desktop smoke, named-destination UX, package release checks, and current-session read-only qualification.


## November 27, 14:04 PHT — shared world-package intake

Unified product checkpoint d507f3e passed comprehensive hosted run 45949263999. Isolated worktree artifacts/product-intake-20261127-1403. Consolidated the catalog package identity and scope checks into world_route_catalog.open_catalog_package and scoped_packages, reused by both graph planners and the single-route selector. Deterministic scope selection validates matching packages even when excluded by planner build, refuses conflicting full world metadata, and never opens unrelated scopes. Graph topology contracts remain distinct: complete package chains versus vertex-level A* with ordinary Detour flags. Three cross-entry regression methods added; all 47 world tests passed on LEGION. Both original retained catalog paths reopened through both graph planners and agreed on total 3D distances within 1e-9 source units: accepted 26.105297766896133 (35 vertex edges / 1 package), leg-2 15.293361390774125 (15 vertex edges / 1 package). Physical flags remain false. Raw assets remain private, original dirty checkout untouched. New exact-head hosted CI pending. Next build imported-world review viewer using the shared verified intake and preserve classification boundaries; current-session physical qualification remains separate.


## November 27, 14:01 PHT — unified local product checkpoint

Isolated LEGION worktree artifacts/product-unified-20261127-1400, based on 7d9b69d (desktop source/test copies) and independently validated integration 6e36bd7 / desktop 8d4ed7c. Cherry-picked recovered local world adapter 7c428c5 without conflicts and imported the metadata fix from ff90ba6. Found and fixed a cross-lane classification defect: synthetic edge binding could otherwise recreate a review-only graph with the default synthetic class. Synthetic locator, edge binding, preview, scene and desktop entry now reject review-only graphs; derived graph retains its original classification. The existing model runner also refuses imported graphs. All 37 focused tests passed locally (20 synthetic planner/viewer, 17 world graph tests), including a new cross-lane regression. Imported vertex-level A* and complete-package chain review remain separate contracts for now; neither implies physical traversal. Full local/hosted validation pending. Original dirty checkout and private geometry packages not changed. No game input or main merge. Next consolidate shared review graph intake, test full integrated wheel and add a dedicated imported-world review viewer rather than relabeling the synthetic viewer.

## November 27, 13:58 PHT — recovered local source-world A* adapter

LEGION returned online and RIFT PID 24896 was responding; game-world/actor qualification remains unverified. The original checkout at dc22fe5 had four pending source/test/package files. All four were copied with SHA-256 equality checks into an isolated worktree under ignored artifacts/recovery-local-world-20261127-1357, leaving the original checkout untouched. Recovery commit 7c428c5 was pushed to research/recovered-local-world-20261127. The existing local world_route_graph adapter uses A* over route-local interior vertices and exact shared endpoints, preserving source elevation and ordinary Detour flags. The reviewed graph and synthetic execution stay separately classified. Added complete source-world metadata identity comparison; conflicting metadata now refuses graph construction. Six focused regression tests passed on LEGION. Reopened the privately retained review-catalog-02.json with its known SHA-256 7902202b3ccf80a2c1961279873e8b7896a55f0023c7f43e942e8308fd323efa: accepted route 35 edges, 26.105297766896133 source units; leg-2 15 edges, 15.293361390774125 source units. Both succeeded before and after the metadata fix, physicalQualification=false. No original geometry uploaded or edited. Hosted exact-head CI pending. The independently developed product-integration branch (6e36bd7) and desktop preview (8d4ed7c) have successful hosted CI; preserve both while reconciling their overlapping planning contracts with this recovered adapter. Production navigation remains unqualified; do not treat review geometry as physical clearance.

## November 27 — standalone desktop route preview

Based on directed interior start checkpoint `f9c0f11` (hosted run 45947889610 passed). Added `rift_taxi.local_taxi_gui`, an optional Python Tk desktop preview, with named starts, explicit directed interior start/fraction, destination selection, blocked-edge multi-selection and local A* preview. Pure scene projection fits XZ bounds with a constant scale across reroutes, positive Z upward, route/exclusion/start/goal roles, and the derived graph identity checked against the plan. No game execution, external service, sibling import or dependency beyond optional Tk. Six headless regression methods exercise planner reuse, detours, projection, no-route/same-node, invalid parameters, single-axis geometry and map pins. Hosted exact-head CI pending; actual Windows GUI launch and visual inspection are not yet verified.

```powershell
python -m rift_taxi.local_taxi_gui
python -m rift_taxi.local_taxi_gui --map LOCAL_GRAPH.json --map-sha256 SHA256
```

The map argument accepts only authored synthetic graph schema, not a RiftWorld review package. Choose a start and destination, select optional blocked edges, and click Preview route. This is a route preview, not Go/STOP or physical arrival. Missing Tk or display produces a clear error. Next reconcile with the independently developed world named-destination lane once CI passes; then build a review-only viewer for imported world geometry and perform actual desktop smoke testing.


## November 27 — consolidated product integration checkpoint

This integration branch starts from accepted directed-interior checkpoint `f9c0f11` (CI 45947889610). The two world review graph files are copied byte-for-byte from accepted named-destination checkpoint `3a27946` (CI 45948041613); GitHub blob identities were independently matched after publication. Common base `dc22fe5`. The independent lanes changed distinct code/test files; this handoff retains both histories. Existing synthetic execution and imported-world review remain separate classifications. The desktop preview branch is not included until its own exact-head CI passes. No changes to main or sibling repositories, no source exports or game input. Combined-head CI still required; prior separate passes do not imply integration acceptance. 


## November 27 — directed interior start for authored synthetic maps

Based on coordinate-entry checkpoint `626bc67` (successful hosted run 45947523131). The local Taxi CLI now accepts `--start-edge EDGE --edge-fraction T` for both plan and journey, with strict finite interior fraction (0 < T < 1) and explicit directed edge. A query-local virtual node has exactly one outgoing suffix; the original graph stays unchanged. No guessed reverse edge or intersection link. The selected original edge must not be blocked, and numerical degeneracy or collision with an authored node is refused. A derived graph identity binds the original byte SHA and selection; optional full receipts and compact CLI output retain the start binding. Existing exact XYZ and named starts remain available. Four new regression methods cover identity, directional behavior, blocked and invalid starts, crossing isolation and model execution. Hosted validation pending. This is authored synthetic geometry only, not live position admission or obstacle clearance. Separate world review graph PR #12 remains an independent lane.

```sh
python -m rift_taxi.local_taxi plan --start-edge main-west-to-main-east --edge-fraction .5 --destination bank
python -m rift_taxi.local_taxi journey --start-edge main-west-to-main-east --edge-fraction .5 --destination bank
```

Expected planned distance is 10 synthetic units from XYZ (6,0,0). No original-route history or previously passed obligations are asserted. Next: reconcile tested branches, test original world packages privately and develop route viewer/destination selection.


## November 27, 13:42 PHT — local position entry (isolated continuation)

Base product checkpoint `dc22fe5` passed hosted Offline regression run 45945997639. This branch adds local coordinate entry to the existing synthetic A* prototype, with no dependency on a live client or cloud runtime. `locate --xyz X Y Z` ranks authored nodes by 3D distance (stable ID tie-break), reports separate XZ/Y offsets, and distinguishes exact binding from review suggestions. `plan` and `journey` accept either `--start NODE` or `--start-xyz X Y Z`; only exact authored XYZ is admitted. Optional full receipts retain the original query. Off-node positions, including points on a declared edge, do not create connectors or silently snap. Four new regression methods cover exact and wrong-floor binding, deterministic suggestions, invalid input, CLI refusal and modeled execution. Hosted acceptance pending; do not promote to main or physical authority. No sibling changes, no live input. Next prioritize a provenance-preserving real-map review adapter and explicit directed-edge interior admission with separate geometry evidence.

Examples (from repository root or installed wheel):
```sh
python -m rift_taxi.local_taxi locate --xyz 4 0 0
python -m rift_taxi.local_taxi locate --xyz 4.1 0 0
python -m rift_taxi.local_taxi plan --start-xyz 4 0 0 --destination bank
python -m rift_taxi.local_taxi journey --start-xyz 0 0 0 --destination bank --delay-steps 2
```
Locator returns 0 for exact node, 1 for review-only candidates, 2 for invalid input. A plan/journey off-node request is invalid (exit 2). This exact-only first step is intentionally not arbitrary-world position navigation.


## November 27 — named source-world destination selection

Based on world graph checkpoint `e609abf` (hosted run 45947714186 passed). Added local `destinations` discovery and `plan --destination ID` to the offline review graph. Catalog IDs retain exact requested goal coordinates. At least one scoped original package must end exactly at the requested goal to bind a name. Nonzero snapped alternatives stay visible and cannot be silently substituted, even if another unrelated package reaches the requested coordinate. Existing exact XYZ planning remains available. A blocked route cannot be traversed but its original goal binding is retained; another valid directed review chain can reach the same exact goal. Four new regression methods exercise selection, blocked alternatives, snap-only refusal, grouping and CLI. All physical/transform/junction authority flags remain false. Hosted exact-head validation pending; no actual source exports uploaded.

```sh
python -m rift_taxi.world_review_graph catalog.json --catalog-sha256 HASH --source-world WORLD --frame-sha256 FRAME --patch-id PATCH --build-id BUILD destinations
python -m rift_taxi.world_review_graph catalog.json --catalog-sha256 HASH --source-world WORLD --frame-sha256 FRAME --patch-id PATCH --build-id BUILD plan --start-xyz 0 0 0 --destination bank
```

Unknown or unbound destination returns exit 1, with explicit status and no segments. Named destination IDs are user/catalog labels, not authenticated in-game names. Next reconcile with the synthetic position-entry lane after both exact-head checks; then develop a route viewer and privately test retained original packages.


## November 27 — source-pinned world review graph

Independent continuation from accepted product checkpoint `dc22fe5` (hosted run 45945997639). New `rift_taxi.world_review_graph` reopens exact catalog/package pins, requires source-world/frame/patch/planner-build scope and consistent complete world metadata, and treats each original complete candidate as a directed edge between its exact snapped source XYZ endpoints. Dijkstra ranks complete chains by full 3D polyline length; an excluded edge can select a detour. Original package/source identity, requested versus snapped coordinates, evidence, endpoint offsets and all waypoint flags remain in each segment. Only exact shared endpoints produce a review junction; no proximity linking, interior split, reverse edge, coordinate conversion or verified connector. The graph cannot execute a journey and is not a live navigation mesh. Six new synthetic fixture test methods cover route selection/detour, exact scope and endpoints, corruption, tie-breaking and CLI. Hosted exact-head validation pending. No real export uploaded; local original-package compatibility and physical qualification remain outstanding. Coordinate entry is independently developed in PR #11; reconcile after both checks pass.

Example (substitute actual locally retained source pins):
```sh
python -m rift_taxi.world_review_graph catalog.json --catalog-sha256 HASH --source-world WORLD --frame-sha256 FRAME --patch-id PATCH --build-id BUILD endpoints
python -m rift_taxi.world_review_graph catalog.json --catalog-sha256 HASH --source-world WORLD --frame-sha256 FRAME --patch-id PATCH --build-id BUILD plan --start-xyz 0 0 0 --goal-xyz 8 0 0 --out new-review.json
```

CLI exit 0: endpoints or review chain found (including same endpoint); 1: no endpoints/chain or unknown exact endpoint; 2: invalid/corrupt input. A mathematical junction is not a traversable connection. Next: test against privately retained real packages, integrate explicit review endpoint/destination selection, and qualify route geometry separately before any live controller admission.


## November 27, 13:24 PHT — product-first local Taxi prototype

User explicitly prioritized a usable standalone prototype with locally computed routes and pathfinding over further audit/statistics work. Recovered LEGION `35d15f1` to remote `4f0516a` by verifying all three pending files were byte-identical to the remote commit, preserving copies under ignored `artifacts/reconcile-remote-20261127-1320`, and fast-forwarding. Exact-head comprehensive CI run 45937080464 passed all three jobs including installed constrained acceptance (106 s); no duplicate commits needed. New `rift_taxi.local_taxi` implements bounded local directed-graph A*, destination listing, blocked-edge alternate routes and a single call into the existing constrained synthetic journey controller. Named start node, no implicit connectors/reversals, hard stops and explicit passage regions preserved. Built-in demo main route and blocked-edge detour both reached the modeled destination with two delayed steps. Six focused tests initially passed; installed-wheel CI now exercises route choice, detour and no-route. This is actual local pathfinding and model execution, NOT physical RIFT navigation. Next prioritize a local real-map review graph adapter, usable destination/position entry, and independent movement admission when physical prerequisites return. Do not create more research-only instrumentation without a direct product blocker. Local full regression completed: 788/788 on Python 3.14.10 (job taxi_20261127_local_pathfinder_full_01, exit 0); after the final CI/readme/test edits, local pathfinder and CI checkpoint focused suites passed 6/6 and 9/9. Hosted exact-head product acceptance is pending publication.


## November 27 — installed constrained acceptance proposal

Recover the prepared installed constrained CLI producer/auditor step and its exact-head metadata admission requirement. The minimum-Python wheel job checks exact source policy bytes, all modeled obligations and false physical flags, archives both reports, and the checkpoint verifier refuses a skipped mandatory acceptance step. LEGION is unavailable; prior local uncommitted changes must be reconciled carefully after reconnect. No physical qualification or live input. Hosted verification pending. Older historical runs require the gate version from their own revision.

## November 27 — saved constrained report audit recovered through cloud

35d15f1 passed comprehensive CI 45935823679 (105 s; Windows 772/772 in 76.179 s). Added synthetic_constrained_audit: reconstruct per-leg source identities, verify approach/drain/correction, recompute dwell/ordered witnesses, actual pose carryover, failure boundaries and aggregate totals, reject truncated success or resume after failure. Both exact retained model receipt pins verified (audit SHA pins in SYNTHETIC_CONSTRAINED_JOURNEY.md); frozen delayed multibend case completed 2/2 legs and four obligations in 18.48 s, first modeled correction 1.56 s, .01 s budget refused resume. 17/17 runner+audit tests passed on LEGION. LEGION session terminated during final CI/docs edit; recovered exact locally tested audit module and test bytes with their recorded SHA-256s in this cloud-side commit. Local uncommitted workflow edit and any partial CI/docs changes require careful reconciliation; do not reset or overwrite. Installed-wheel constrained acceptance is not yet published. No physical qualification or game input. New comprehensive hosted verification pending.

## November 27, 11:41 PHT — synthetic constrained journey execution slice

b4a3d12 passed all three comprehensive CI jobs, run 45934467951 (87 s; Windows 764/764 in 62.068 s). Added `synthetic_constrained_journey`: split ideal model at explicit hard stops only, reuse existing approach/drain/terminal correction and independent saved-journey verifier, carry actual settled pose and yaw between legs, append bounded zero-command model dwell, check distinct ordered mandatory region witnesses from approach samples and sampled stop evidence. A missed region/failed approach/unsettled leg blocks resume; no region-aware trajectory guarantee or physical authority. Shared sampled audit consumes explicit quiet interval flags rather than invented key events. Existing eight constraint tests and eight new runner tests passed locally. Added SHA-pinned synthetic sample/policy and retained two actual model receipts under ignored artifacts/m3-constrained-20261127-1140. Both complete 2/2 legs and four obligations: zero delay 4.30 s / 7.7331101954 units / 0.7674418605 total duty; two-step delay 4.40 s / 7.98512 units / 0.6818181818 duty. See SYNTHETIC_CONSTRAINED_JOURNEY.md. No live input or sibling changes; physical M1 and actual traversability remain unqualified. Next independently verify saved constrained reports and installed-wheel invocation; full hosted regression pending.

## November 27, 11:28 PHT — local review-only destination catalog

8a00db9 passed comprehensive CI 45933645353 (81 s; Windows 754/754 in 51.897 s). Added `world_route_catalog`: externally pinned flat catalog, exact package IDs and source-world/frame/patch scope, requested destination XYZ binding, independent start and endpoint-snap XZ/Y limits, deterministic ranking and explicit no-match result. No route joins, connectors, reversal or execution authority. Ten additional focused tests; all 27 world tests pass. Actual retained accepted/leg-2 packages reopened and selected independently; wrong patch yielded no match. Final catalog review-catalog-02.json SHA 7902202b3ccf80a2c1961279873e8b7896a55f0023c7f43e942e8308fd323efa; selection receipts accepted-selection-02.json SHA 352e44a249eb663cc782ee0bb48730e131abb9719d893c9da35e69b0b0034102 and leg-2-selection-02.json SHA 997f0fa3fdccf96b8811d65779d4716f5a7e0838501eb89d8b900ba60163c4ce. Private artifacts only. Previous draft catalog-01 lacks final destination binding; retain as historical, not valid current input. Last observed RIFT PID 33672 responding on LEGION; desktop still DESKTOP_TREE_UNSETTLED, no fresh physical qualification. No sibling writes or game input. Hosted regression pending. Next prioritize independent synthetic constraint execution or local review selection packaging tests rather than more unqualified world promotion.

## November 27, 11:19 PHT — original world-chain metadata and payload review

1ba144a passed comprehensive CI 45932638518 (82 s; Windows 748/748 in 45.208 s). The new `world_chain_review` module independently pins candidate/patch/build metadata and four explicit payloads, recomputes upstream patch/build content IDs and compact request coverage, checks frame/world/profile/region bindings and route containment for one scene request box. No implicit manifest path following. All 17 focused world tests pass (six added). Actual original accepted candidate chain reviewed on LEGION; receipt artifacts/m4-world-review-20261127-1108/chain-review.json SHA 85f33d71edff72bc3981a42e8d5c7d524efa9333910995266106a4ba3851d268; all four original payload hashes matched. Source coverage remains partial, transform unknown, scene/pipeline dependencies/Detour compatibility and physical traversal unqualified. No sibling modifications or physical input. User reaffirmed continuous milestone-driven autonomous workflow: prefer actual implementation, use existing assets, resolve feasible blockers and progress independent workstreams, no routine user questions. See WORLD_CHAIN_REVIEW.md. Full hosted verification pending.

## November 27, 11:09 PHT — local world-candidate review and portable package

Prior afbd1b5 checkpoint passed comprehensive CI 45931353312 (74 s; Windows 737/737). Added strict `world_candidate_review` and self-contained `world_review_package` modules, preserving exact original source bytes, semantic candidate ID, source context, points, endpoint offsets and false execution authority. Eleven focused tests passed on LEGION. Read-only upstream inspection used RiftWorld core.py SHA bf62cb53abe8d39b4789af49fbc7037617613f3133c3113357ce9243f482d688, current inspected checkout 21379d48af770942174175cbb97457183f615903 (not authenticated producer revision of historical files). Five complete retained candidate exports accepted for review; two unavailable exports refused. Two original packages written to Taxi ignored artifacts/m4-world-review-20261127-1108, independently reopened and exact original bytes checked. See WORLD_REVIEW_PACKAGE.md for original pins. No source artifacts uploaded, sibling edits, runtime imports or physical authority. Comprehensive CI pending; next inspect source patch and coverage provenance before any new route-admission contract.

## November 27 — explicit synthetic route-obligation evidence

56ac154 installed-wheel journey-audit checkpoint passed all three jobs, PR 45930812586 (100 s; Windows 729/729). Added `rift_taxi.synthetic_route_constraints` offline sampled-evidence checker: explicit XYZ passage regions pinned to trace SHA/ordered point indices, distinct ordered witnesses, exact repeated synthetic XYZ plus bounded sample gaps and no supplied key activity for stop dwell, destination must remain settled through final sample. Ordinary guide/optional points are not obligations. Eight focused tests pass on LEGION, including wrong floor, missing/interpolated-only passage, between-sample key pulse, drift, gap, late departure, malformed policy and retained failed receipt. No claim of continuous stationarity, swept-volume clearance, physical arrival or constraint-execution controller. Full hosted regression pending. M1 physical gates remain unchanged.

## November 27 — installed saved-journey audit acceptance

753b236 passed 728/728 Windows tests and 712 passes +16 platform skips on each Linux lane (PR 45930463887, 68 s); local audit tests 6/6. Existing frozen staggered-finish case verified on LEGION: delay 3, dt .12, speed 3.6, yaw rate 125, initial yaw -50, passive error .3608799296 -> .1500000000 after 1.56 s correction, .2108799296 modeled travel; .01 s budget leaves the journey terminal-unsettled. Added exact budget mismatch/active correction regression and isolated installed-wheel audit checks for all existing journey modes. Documented CLI invocation and v1 budget limitation. No physical input, source promotion or runtime dependencies. New hosted validation pending.

## November 27 — complete saved synthetic journey audit

f2132ec passed 722/722 Windows and 706+16 skips on each Linux lane; exact-head CI gate passed run 45929896160 in 89 s. Added standalone `python -B -m rift_taxi.synthetic_journey_audit TRACE REPORT --terminal-budget 5 --expected-sha256 HASH` with optional new audit output. Independently checks existing approach trajectory, reproduces deterministic terminal phases using existing implementations, recomputes disjoint phase totals, preserves failed journeys, rejects malformed/ambiguous/hash-mismatched reports. V1 reports omit terminal budget, so explicit caller policy is required; a successful reproduction cannot recover an unknown historical budget. Six focused tests, no game access or physical claims. Hosted regression pending.

## November 27 — offline control gate STOP metadata hardening

Independent projection/ordered-witness audit and diagnostic repair aad6f9b passed comprehensive run 45929599645 (110 s; Windows 717/717; both Linux lanes 701 passes + 16 expected skips). Harden the driver-neutral gate so an invalid diagnostic STOP reason never prevents release attempts; preserve ValueError after STOP, retain the first reason and uncertain-release retries. Reject custom collection subclasses and requests over the three-entry W/A/D bound; validate one immutable request snapshot. Five new inert backend tests. Fresh LEGION Workbridge 0.16.4-dev service PID 32544, started 02:23 UTC; read-only desktop query refused DESKTOP_TREE_UNSETTLED. 02:40 UTC process inventory returned no rift_x64 process and all six desktop runtime staged files plus manifest remained absent. No alternate desktop access, service modification or input. No physical qualification. New hosted regression pending.

## November 27 — ordered audit diagnostic compatibility repair

The first projection-audit checkpoint a6ab933 failed Linux 3.14 CI run 45929450044 on an existing corner-witness diagnostic regex: the forged XYZ was correctly refused but the newer message lacked the established `invalid ordered corner passage` prefix. Preserve that prefix while retaining the precise underlying failure and the stricter independent projection check. Existing and new corruption tests must still reject. No reduction in checks or simulator changes. New comprehensive CI required.

## November 27 — independent synthetic route projection audit

Indexed lookahead head 3178560 passed comprehensive run 45929131072 (68 s; Windows 714/714 in 44.611 s). Strengthen existing synthetic trajectory verifier using an independent full-scan bounded XZ projection, reconstructed prior applied-displacement budget, ordered sharp-corner gates, per-frame counts and passage witness checks. Reject internally plausible forged progress or coordinated cross-track/summary changes. Three focused tests added, including an ordered reversal fixture. No simulator or runtime steering change. The verifier still checks model consistency, not controller optimality, physical geometry or arrival. Full hosted validation pending.

## November 27 — indexed offline lookahead lookup

Added a binary-search starting index to the existing lookahead geometry for routes longer than eight vertices; short routes retain a linear walk. Exact vertex and repeated-horizontal-arc ties, degenerate-segment handling and interpolation arithmetic are preserved. Added two regressions with seeded full-scan oracle and a vertical duplicate boundary. An isolated Linux microbenchmark of the original versus indexed primitive (not whole application) checked 67,468 exact results; median 20k queries on 500 vertices 0.154647 vs 0.021102 s, on 50 vertices 0.028281 vs 0.018453 s, on five vertices indexing was slower. These timings are not full-suite or live-navigation speed claims; the committed hybrid retains the original short-route path. No physical qualification or input. Verify comprehensive hosted CI before acceptance.

## November 27 — offline replay metric efficiency and finite range

Replay snapshot hardening e8e51ed passed PR 45928654361 in 73 s (Windows 708/708; both Linux lanes 692 passed + 16 skips). Refactored release proximity proxies to interpolate each relevant W-up once and retire matched hard-stop points, preserving original per-event/per-point semantics and duplicate points. Added 100 seeded pairwise comparisons, interpolation-call bound, overflow rejection and extreme finite interpolation tests. No physical release or traversal-order proof; no game access. Full hosted validation pending.

## November 27, 10:28 PHT — offline replay provenance hardening

Cloud checkpoint e1acbca passed both hosted workflows (Windows 701/701, comprehensive 102 s; Linux pilot 36 s). Return to core Taxi reliability: strict duplicate-key/nonfinite/deep JSON rejection, bounded reads of actual bytes, canonical numeric RR2 coordinates and typed source/phase failures. Historical normalization consumes exactly the hash-verified original snapshot rather than reopening the path. Seven focused regressions cover ambiguity, bounds, malformed types and source replacement after pin. This does not authenticate historical data, prevent all filesystem races, or qualify current physical pose. Hosted verification pending; no live game activity or sibling changes.

## November 27 — Windows pilot evidence and catalog

33f8ab4 serial recovery passed 699/699 (67.824 s; discovery 1.520, recovery 69.397, verification .195 s), PR 45901392841 complete. 3ca0c35 independent Windows pilot 45901611083 passed 699/699/zero skips, 69 modules, 62 s workflow/145 summed job s; max shard 16.367 s. Same-head comprehensive 45901619301 passed. Retained Windows-specific cost profile, platform-selective planning and final observable checkout identity recheck with two new tests. Keep Windows profiling opt-in and serial recovery required; next return to Taxi product priorities after hosted validation. No live input or runtime dependency.

## November 27 — isolated Windows profiling experiment

Added opt-in four-host Windows test-shard workflow, independent Windows merge and strict no-skip/floor check. Triggers only its own workflow changes or explicit dispatch, no routine duplicated runs. Keep original comprehensive serial recovery gate; collect measured Windows module costs and compare wall/job seconds before deciding whether a parallel contract is worthwhile. No game activity or additional paid runner infrastructure.

## November 27 — Windows exact-inventory CI admission

acfd567 comprehensive PR 45891478942 passed (101 s, Windows 694/694 in 69.124 s); weighted pilot 45891470995 passed (37 s, 678 passes/16 skips, max shard 13.859407 s). Hardened synthetic Windows recovery wrapper to require exact single-shard discovery count/HEAD, historical floor 694, zero declared skips, and independently matched receipt counts; added phase timings and five focused tests. Underlying serial patch-check/verifier remain unchanged. New hosted checkpoint pending. No live game or service changes.

## November 27 — measured module-cost allocation experiment

Timing-enabled pilot 45891235786 at 6c04452 passed in 40 s, 691 discovered/675 passed/16 skips, 68 modules. Count-balanced max 14.326 s; historical weighted allocation predicts ~10.37 s. Added explicit source-pinned Linux/Python 3.14 module cost catalog, deterministic weighted planner, count fallback and three focused regressions. No coverage reduction. Validate new hosted result before claiming speed improvement; Windows/minimum-Python remain comprehensive gates.

## November 27 — first parallel pilot and module profiling

20294ee pilot 45890935749 succeeded (46 s, 688 discovered, 672 passed/16 skips, exact coverage); shards 172 tests each took 9.845/5.143/18.108/7.588 s. Comprehensive PR run 45890943852 passed in 78 s. Added complete per-module fixture-inclusive timing and independent timing-inventory checks, actual module identity, and focused regressions. Use the next pilot to obtain real weighting evidence. No change to active workflow, physical gates, or main. See [cloud development](CLOUD_DEVELOPMENT.md).

## November 27, 04:25 PHT — workflow scope resolved and CI activation

User completed OAuth authorization; LEGION verified account 360madden and workflow scope. Fast-forwarded clean local branch 4183046 -> 5bd9be7, then exact-head CI gate passed for run 45889172411 attempt 1 (96 s; Windows longest 92 s). Activated optimized existing PR workflow and separate four-shard Linux pilot with narrower infrastructure-only push paths and attempt-specific artifact names. Main and required cross-platform gate unchanged. Hosted activation and speed/coverage remain to be verified. This supersedes the historical inactive-workflow permission blocker. See [cloud development](CLOUD_DEVELOPMENT.md#november-27-0425-pht--authorized-ci-activation).

## November 27 — tight CI checkpoint admission

Fixture-library head 005a8bc passed all three hosted jobs in 98 s (Windows 680/680; both Linux 664 passed +16 skips). Added exact-head/attempt CI metadata gate and latency reporting, eight focused tests, durable CI acceptance policy, and inactive optimized existing-workflow proposal (obsolete-run cancellation and removal of redundant minimum-version focused tests). Windows is currently the longest observed lane. Active CI remains unchanged because workflow-write permission is unresolved. See [cloud development](CLOUD_DEVELOPMENT.md#continuous-integration-as-a-development-gate). No physical qualification or service deployment.

## November 27 — hosted portable batch validation and fixture library

Cloud-only commit 5e79dcd passed all three hosted jobs (PR run 45888250727, 69 s total; Windows 672/672, Linux 656 passed + 16 platform skips on both Python versions). Added explicit SHA-256-pinned synthetic fixture catalog and standalone verification against existing trace contracts, plus eight focused corruption/coverage tests. No physical capture or proprietary assets imported. New parallel Actions template still inactive pending authorized workflow-write scope. See [cloud development](CLOUD_DEVELOPMENT.md). The full-suite parallel speedup remains unmeasured; no LEGION edit or live activity.

## November 27 — portable cloud batch execution

Cloud foundation 4183046 passed hosted PR CI run 45887826247 (Linux 3.14, Windows 3.14 recovery, Linux 3.11 wheel). Added portable single-host subprocess sharding/merge, run/batch/attempt identity and real disposable Git checkout integration tests. See [cloud development](CLOUD_DEVELOPMENT.md). This change is authored directly through the GitHub connector, without LEGION edits. New Actions workflow remains an inactive template; do not claim full pilot timing or M1 physical qualification.

## November 27 — cloud-first development foundation

User approved cloud-first workflow. LEGION full release-clock regression completed 660/660 in 112.650 s; hosted PR run 45886526464 succeeded in 86 s (Linux full test step 42 s, Windows recovery 62 s, Linux minimum-version full test step 49 s). Added [cloud development policy](CLOUD_DEVELOPMENT.md), deterministic whole-module sharding and exact-coverage receipt merge, plus inactive four-lane hosted Linux pilot template. GitHub denied the workflow file push (missing OAuth workflow scope); original local commit a1322aa preserved on cloud/pilot-workflow-local-20261127. Publish ordinary code and inactive template through existing PR CI only; actual pilot requires authorized workflow-write access. Existing PR validation remains authoritative. Cloud results are development-only; physical M1, Workbridge desktop recovery, native freshness/heading/release gates remain separate and unqualified.

## November 27, 03:48 PHT — independent release lease clock hardening

Six new state regressions reproduced unsafe lease clock admission on the old implementation. Corrected `ReleaseState` to use one validated monotonic clock sample per operation, refuse invalid/rollback time even when idle, latch STOP and attempt every reserved release, retaining failed-release uncertainty. 28/28 supervisor tests passed (all inert/dry-run, including actual child/parent-crash fixtures); full regression pending. See [release supervisor evidence](M1_RELEASE_SUPERVISOR.md#november-27--independent-lease-clock-admission-hardening). Workbridge validated-release directory listing refused PROTECTED_PATH; no alternative access attempted, no service deployment or restart. Keep existing desktop prerequisite and all physical M1 gates. No actual RIFT input or new physical evidence.

## November 27, 03:46 PHT — desktop deployment dependency diagnosed

Verified 654/654 full regressions and the remote 9ec24bd checkpoint. Fresh LEGION OS metadata revalidated PID 24992/start ticks/HWND/build, no new native pose or scene evidence. The active Workbridge 0.16.4-dev Node process uses checkout dist; all six required desktop staging source files exist under scripts/ but all six deployed copies and desktop-runtime-manifest.json are absent. Existing runner resolves dist-relative scripts and refuses uncertain process trees. This is a confirmed missing deployment dependency consistent with prior desktop refusal, not proof of sole cause or repaired capture. See [desktop dependency diagnosis](M1_DESKTOP_DEPENDENCY_2026-11-27.md). Recovery belongs to separately authorized Workbridge WB-001 sealed deployment, not ad hoc live dist edits or bypasses. No service/addon/game/sibling modifications or new input; retain disarmed production and prioritize current independent heading/position/release evidence after legitimate desktop recovery.

## November 27, 03:42 PHT — strict telemetry audit admission

The 651-test suite completed (162.942 s, exit 0) and checkpoint 00bc7c0 was pushed and independently verified at the remote branch. Hardened the downstream offline telemetry audit against ill-typed replay counts, malformed agreeing process pins (canonical positive decimal epoch, nonempty host, valid SHA, bounded PID), and unrecognized skipped-frame categories. Three extra focused regressions; 12/12 focused tests passed. Third real-original audit reproduced the original SHA-256 37bd785a3652297df753c79da1c059d60b47e12b8df731ec68b6df0283342b62 byte-for-byte. Full post-hardening regression completed: 654/654 tests in 182.625 s, exit 0; pushed 9ec24bd independently verified at the remote branch. No change to physical qualification or runtime motion authority. Historical RR2 facing evidence and Taxi's two-heading controls remain candidates, not an independent current-session body-heading source. Avoid relaunching stale movement probes or repeated stationary captures; prioritize independent changed-state observations and the unresolved desktop evidence gate.

## November 27, 03:20 PHT — retained API motion fields and source progression

Added offline `rift_taxi.telemetry_motion_audit` reusing the prior pinned API-zone summary/replay; original wire SHA and player/generation/sequence/clock checks, deduplicated XYZ coverage and missing-data-safe comparisons. All 73 wire occurrences / 39 unique sequences verified; all 39 had XYZ, one unique coordinate, 0/38 changed adjacent pairs, only eight consecutive publisher pairs, five new second-pass sequences, no heading-like field. Source span 15.25390625 s and median retained gap .3115234375 s are NOT host cadence or latency. Installed Telemetry 0.5.0 source allowlist has XYZ and no body-heading field; Unit.Detail can affect native cache freshness. Two audit outputs byte-identical SHA-256 37bd785a3652297df753c79da1c059d60b47e12b8df731ec68b6df0283342b62. Nine focused tests and the completed 651/651 full regression suite passed. See [motion-field evidence](M1_TELEMETRY_MOTION_FIELDS_2026-11-27.md). No new live acquisition/input, source authority, body heading, passive freshness, world instance or game-consumed release qualification. Next prioritize genuinely independent current-session changed-state/heading evidence rather than static resampling.

## November 27, 02:14 PHT — independent API zone corroboration

Reused RR2's existing read-only Telemetry zone bracket, explicitly pinned LEGION PID 24992 and the prebuilt reader, and wrote all new evidence under Taxi's own ignored artifacts/m1-20261127-0214-api-zone/. Capture and separate original-source replay both exited 0: native/Lua zone z487C9102D2EA79BE, API name Sanctum, 34+39 frame occurrences, 39 unique sequences, five advancing second-pass frames, epoch 8, 4.613 s host span. Separate Taxi audit matched stored host/PID/start/path/build/HWND, owner/API player ID and raw-zone prefix; earlier Taxi native series was not contemporaneous. Original summary SHA-256 5d86c28cf8d84ffdf3cc36da292d9b8b321a828037c7b0c1faf1b364e37b8bc0; replay SHA-256 02dbef2e6e144c860299a9ac3268ff6e8ff6fba41e08d3d698dcd51def400b48. See [same-epoch API zone evidence](M1_API_ZONE_CORROBORATION_LEGION_2026-11-27.md). Independent API reference now observed in bounded scope; do not claim unique instance, continuous freshness, body-heading or physical release qualification. No game input, addon edits, sibling builds, runtime change or production promotion. Next prioritize producer timing/heading and remaining physical M1 gates. Last code baseline 642/642 tests; this is evidence-only.

## November 27 — fresh M1 session and stored native-series verification

Moved priority from synthetic tuning to M1. Fresh LEGION process (PID 24992, start ticks 639313044653553067, HWND 4198144, unchanged supported executable SHA) was foreground. Existing read-only native series succeeded 24/24: stable same-owner XYZ/heading candidates, 24/24 matrix matches, raw zone key 0x487C9102, all 48 W/A/D polls per key UP, guard handle/flag 0/0. Median capture gap 100.348 ms; largest acquisition bracket 25.446 ms. Added offline-only `rift_taxi.verify_native_series` for SHA/expected identity, sample timing and candidate summaries; both actual receipt audit outputs byte-identical. Eight focused regressions passed. Saved addon metadata inspected but predated current process; desktop enumeration refused DESKTOP_TREE_UNSETTLED. No independent current API producer, visual scene clearance, passive freshness, authoritative heading, public zone/world instance or game-consumed release established. See [current native series evidence](M1_NATIVE_SERIES_REVALIDATION_2026-11-27.md). Next prioritize genuinely current independent producer evidence; do not repeat stationary captures as a substitute or promote archived candidate pins. Production remains disarmed; no movement input.

## November 27 — tapered certified-corner approach

Added opt-in bounded-taper speed cap (4d + 4 max(0,d-.25)), same .08 per-axis certificate, near-corner braking, arrival and fault gates. Pinned 192 historical baseline results and executed 288 new runs across 240 conditions / 480 policy outcomes. Usable 160/160 both; 384 valid candidate certificates; 80/80 candidate dropout expiries; both cohort screens passed. Mean time 17.033984 vs 16.953906 s (0.47% improvement), 73 faster/78 equal/9 slower (worst 1.0625 s). Separate audit checked 192 archived baseline outcomes, independently repeated four baseline and four candidate outcomes exactly, and verified report SHA. Nine focused tests and 634/634 full regression passed. See [tapered corner evidence](LEGION_CORNER_SPEED_2026-11-27.md). Keep experimental opt-in; prioritize actual M1 readiness and remaining source/physical evidence gates rather than repeated small synthetic tuning. No live input, physical qualification or default promotion.

## November 27 — uncertainty-aware sharp-corner admission

Added an opt-in fixed .08-unit per-axis error rectangle certificate and local corner approach braking, retaining the original .15 corner radius and .3 terminal tolerance. All three prior adverse cases settled; two recovered V2 losses and one preserved gain. Frozen comparison: 192 conditions / 576 runs, prior usable V1/V2/bounded 63/62/64 of 64 and new usable 59/63/64 of 64. Overall 128/128 bounded, six gains versus V1 and three versus V2, zero losses, 256 valid certificates, all 192 prolonged-dropout policy runs expired. All research-screen checks passed. V2/bounded mean time 15.0745/15.9405 s on 125 common successes (+5.74%); retain tradeoff. Independent audit matched all 192 prior comparator outcomes and repeated nine targeted policy outcomes exactly. Full suite 625/625; no default promotion. See [bounded corner evidence](LEGION_BOUNDED_CORNER_2026-11-27.md). Next: improve corner approach efficiency without weakening certificates, broader timing/geometry tests, and fresh eligible M1 qualification. Production disarmed; no live input or physical claims.

## November 27 — robust response estimation and noisy observations

Added opt-in V2 robust estimator, deterministic sensor noise, and retrospective actual-corner witness checks; legacy adaptive benchmark remains byte-identical. Fixed study 96 conditions / 288 runs: nominal 49/64, V1 63/64, V2 62/64 settled; one V2 gain and two losses from noisy sharp-corner admission. All 96 prolonged-dropout policy runs expired. V2 mean reacquisition .984375 vs 2.9453125 s, conditional fit accuracy 95.62% vs 91.17%, coverage 92.85% vs 88.51%. V2 fails the no-settled-losses screen; no default promotion. All 616 regression tests passed. See [robust response evidence](LEGION_ROBUST_RESPONSE_2026-11-27.md). Next: separate uncertainty-aware sharp-corner admission experiment; preserve the adverse cases and prioritize fresh live M1 qualification when eligible. No game input or physical claims.

## November 26–27 — adaptive synthetic response estimator

Added opt-in causal rolling delay/gain estimation and hidden plant response-change support, with no changes to legacy defaults. New benchmark: 336 matched conditions / 672 runs (144 prior plus 192 new). Prior usable 108/108 both, new usable nominal 123/144 vs adaptive 144/144; 21 gains, no losses. All 84 adaptive prolonged-dropout cases expired. New common-success mean time 18.9502 vs 15.2165 s; five adaptive slowdowns, mean forward duty slightly lower. New qualified-estimate conditional accuracy 89.78% (95.11% frame coverage); all 72 usable switched-gain cases reacquired in 2.5–3.125 s. The prior report and repeated adaptive reports match byte-for-byte; 144 prior nominal outcomes independently matched. Fourteen focused tests passed. See [adaptive response evidence](LEGION_ADAPTIVE_RESPONSE_2026-11-27.md). Next: measurement noise and faster change detection, then live M1 qualification when eligible. Production disarmed; no live input or physical claims.

## November 26 — combined observation and actuator uncertainty

Extended the offline sampled model with independently declared actual/assumed command delay and velocity/yaw response gains, preserving the prior benchmark byte-for-byte. New fixed comparison: 144 matched conditions / 432 runs, usable telemetry settled 92/108 held pose, 108/108 nominal prediction, 108/108 exact-model reference; 16 recovered baseline failures, no losses. All 108 prolonged-dropout runs expired. On 92 common successes mean duration 11.5713, 10.4823, 9.4823 s; nominal slower than baseline in 43 cases. Six focused tests passed; repeated combined reports byte-identical. See [combined uncertainty evidence](LEGION_COMBINED_UNCERTAINTY_2026-11-26.md). Next consider bounded offline response estimation from admitted samples and command history; independently specified variable-response validation before promotion. Production disarmed, no physical qualification.

## November 26 — sampled closed-loop steering

Added separate offline `rift_taxi.synthetic_sampled_steering` model: 56 conditions / 168 runs with held-pose, predictive application and predictive age-cap policies. All 72 unusable-telemetry runs stopped; usable cases settled 31/32, 32/32, 32/32 respectively. On 31 common successes, mean duration 11.0464, 10.1351 and 11.9556 s. Prediction merits further research; age-cap had no extra arrival benefit and was slower. Source-only progress, sharp passage, actual FIFO, forecasts and arrival internally audited. Seven focused tests passed; two report hashes match. See [sampled steering evidence](LEGION_SAMPLED_STEERING_2026-11-26.md). Next: combined sampled-observation and command-model mismatch; no runtime promotion, no live input.

## November 26 — observation timing and inert control-gate replay

Added `rift_taxi.synthetic_observation_replay` with 28 cases (four verified synthetic truth prefixes, seven delivery schedules). Sixteen normal/short-gap cases completed; twelve long-dropout, reordered and stale cases latched STOP, released inert held keys or never pressed, and refused 532 later packets. V2 tracks gaps and held-pose age/errors separately from packet latency; two report hashes match. Nine focused tests passed. See [observation replay evidence](LEGION_OBSERVATION_REPLAY_2026-11-26.md). Truth is fixed, not closed-loop; no live input, no native freshness or physical release claim. Next: bounded closed-loop sampled-observation study, keeping production disarmed.

## November 26 — assumed command-delay mismatch

Added an opt-in separate estimator FIFO and independent report verification; preserved exact-estimate and legacy output. New fixed 36-condition/144-journey study: no prediction 30/36 settled, exact prediction 36/36, mismatched estimates 71/72; one severe-underestimate cross-track failure retained. Two reports byte-identical; historical 48-case benchmark also byte-identical after change. Six focused tests passed. See [latency mismatch evidence](LEGION_LATENCY_MISMATCH_2026-11-26.md). Next: observation timing uncertainty and bounded synthetic comparison; no controller promotion or live input.

## November 26 — verified patch recovery and repeatable synthetic comparison

LEGION checkout recovery at 7323d03 passed 559/559 tests and an independent 29-file receipt verification. Reused today's independently verified Update Helper two-pass inventory: all 266 files unchanged, executable SHA unchanged. Fresh OS identity passed but the RIFT window was not foreground; no game-memory read or movement occurred. The standalone `rift_taxi.synthetic_journey_batch` CLI now reconstructs all 48 previously observed smoke cases, executes 128 eligible complete journeys, and reports matched settled gains/losses and common-success time/duty. All 128 prior compact outcomes reproduced; two new reports were byte-identical. Five focused tests passed. See [November 26 recovery and batch benchmark](LEGION_RECOVERY_JOURNEY_BATCH_2026-11-26.md) for exact pins, paths, results, and reproduction instructions. Keep production disarmed. Next offline research: prespecified timing mismatch and independent geometry; live M1 qualification remains pending an eligible session.

## November 25 morning — recovery and standalone automation

PR #8 accepted at 93199e2; hosted synthetic Windows recovery rehearsal and independent verifier succeeded (556/556, 29 files). LEGION synchronized to that main; current-main recovery replay using archived manifests passed 556/556 and 29-file verification. Current executable hash matches the baseline, but updater completion and full current inventory remain unverified. RIFT login unavailable. See [recovery runbook section 9](PATCH_RECOVERY_2026-11-24.md#9-november-25-morning-legion-validation).

New standalone CLI reporting supports --summary (compact JSON, with optional full receipt saved separately) and --require-settled (exit 1 for a completed but unsettled model run; invalid inputs and I/O refusals remain exit 2). Legacy defaults unchanged. Local focused suite 17/17; full 559/559 passed (66.049 s, exit 0).

Matched complete-journey comparison on the previously observed 48-case fixed smoke geometry (source SHA-256 7f25b693911db7c824f48a8996eda8de2e7e4727e4f5450062f54fe85d6bc90e): zero-delay recovery settled 16/16 vs 12/16 baseline; on 12 common successes, mean total seconds 4.483 vs 4.483 and full-journey duty .9558 vs .9558. For both prediction variants on 32 delayed cases, 32/32 settled vs baseline 30/32; zero baseline settled losses. Among 30 common successes, baseline mean total time 6.764 s and duty .8837, near-goal 6.341 s and .8871, near-stall 5.768 s and .9192. Includes approach, drain and terminal correction, matched delay/profile, not live or new holdout evidence. Compact report receipt artifacts/legion-journey-end-to-end-20261125.json, SHA-256 dd75e75be12a1fc04c8a797379d98bc04b666f5090dc1bee4836533ab6a9d9ec. This is a descriptive comparison on observed development cases; retain baseline, do not promote the experimental controller. Next prioritize reproducible standalone batch comparison and fixed-design timing mismatch research.
 Keep all modes synthetic and production disarmed.


## Accepted baseline and recovery rehearsal (November 24 PST)

PR #7 accepted at `4803c92`; hosted run 45563551288 passed 556 Windows tests and installed all three experimental modes. Latest LEGION doctor returned offline-replay-ready; historic V2 receipt independently reverified (29 files, no-content-change). LEGION subsequently returned session terminated; no new installation state or local sync is asserted. New hosted synthetic recovery rehearsal is under review, using fake manifest data on a Windows runner and the actual recovery commands, not RIFT or LEGION evidence. Current test floor 556; see [patch runbook section 8](PATCH_RECOVERY_2026-11-24.md#8-current-accepted-baseline-and-hosted-synthetic-rehearsal--november-24-pst). Keep production disarmed. Resume actual post-patch capture only after host and updater readiness are confirmed.

## Zero-delay recovery and standalone mode integration (November 24 PST)

See [zero-delay recovery](LEGION_ZERO_DELAY_REJOIN_2026-11-24.md). PR #6 accepted at db161f0; separate opt-in zero-delay rejoin recovers the four observed short-final-z failures, with no losses on 288 factorial zero-delay cases. Standalone demo exposes both prediction modes and zero-delay recovery; four local CLI modes settled. All frozen defaults preserved. No physical qualification.

## Near-stall prediction V3 (November 24 PST)

See [near-stall study](LEGION_LATENCY_NEAR_STALL_2026-11-24.md). PR #5 accepted at a60efca; V2 comparison preserved byte-for-byte. Opt-in near-stall mode restores seven factorial high-duty successes while retaining 864/864 settled. New 48-case smoke: 44/48 settled, four shared zero-delay short-final-z failures remain. No default promotion or physical qualification. Next investigate baseline terminal progress failure separately from prediction.

## LEGION restored — current research branch (November 24 PST)

See [LEGION latency recovery](LEGION_LATENCY_RECOVERY_2026-11-24.md) for source receipts, original archive authentication, preserved negative results and new smoke design. Local main synchronized to PR #4 merge 134b7c7 (545 hosted Windows tests and installed-wheel journey execution). Interrupted work preserved separately; research branch reconciled at cd9d592. V2 opt-in terminal rejoin corrects one lost arrival; 864/864 factorial settled, 216/216 observed V3 settled, 24/24 new smoke settled. Full LEGION regression 550/550 passed (57.448 s, exit 0). Duty losses remain; do not promote default policy. RIFT unavailable, no physical qualification. Historical sister verification only partially complete. Continue bounded offline functionality and independent fixed-design tests.


**Host:** LEGION · **Repository:** `C:\work\Rift_Taxi` · **Branch:** `main`
**Historical November 23 baseline:** `2109a3e55225b35952b8d7aaae7ecad59e2f865e`
**Remote:** https://github.com/360madden/Rift_Taxi.git
**State:** M1 in progress; production navigation disarmed. M0 complete. M2/M3 experiments are offline only; M4–M6 remain planned.

## Latest accepted functionality checkpoint — November 24, 2026 (EST)

**Remote main:** merged [PR #2](https://github.com/360madden/Rift_Taxi/pull/2) at `946e6952992420f114232931a8ecccd1adb70f7a`. The exact tested PR head was `a2779094562552766548205ac97871ed69662650`, based on `c4a3bd6b213020c301442e3d874231929fd1c0ed`. [Hosted run 45549457994](https://github.com/360madden/Rift_Taxi/actions/runs/45549457994) completed all three jobs: Windows Python 3.14 539/539 (47.280 s), Ubuntu Python 3.14 523 passed/16 Windows-specific skips (22.503 s), Ubuntu Python 3.11 523 passed/16 skipped (37.284 s). Nine new functional tests passed. Local LEGION checkout was not synchronized or inspected; this is a GitHub-hosted checkpoint.

### New functionality

- `rift_taxi.synthetic_terminal_finish`: bounded stop-align-translate reference in an ideal synthetic plant, from an already drained stationary endpoint. Five-second default correction budget, rate bounds, FIFO delay and final stationary witness; preserve already-settled endpoints without extra motion. Observed V4 long-short-ladder cases: 24/24 settled after correction versus 11/24 passively, preserving 11 successes and correcting 13 failures. These are observed development cases, not fresh validation. The V4 lookahead candidate remains rejected.
- `rift_taxi.synthetic_journey_demo`: composes unchanged ordered approach, passive FIFO drain, and optional terminal correction in one synthetic journey report. Four integrated tests cover phase continuity, failed approach exclusion, historical trace refusal and invalid budget. A failed approach cannot become a terminal success. CLI uses an existing versioned synthetic trace and refuses overwriting output.
- Main remains disarmed for production movement. These modules neither open a game process nor send input; exact fractional commands, ideal flat geometry and no collision/inertia model are explicit limitations.

### Resume checklist

1. Read AGENTS.md, AUTONOMY_POLICY.md and this handoff. Confirm actual remote head and machine before making local claims.
2. Prioritize a usable standalone offline journey demonstration: identify existing synthetic fixtures, run the module CLI on them, preserve failed journeys, and expose concise status/phase results. CLI end-to-end execution and installed-package use of these two new modules are not yet independently verified.
3. Evaluate independently specified synthetic cases and budget refusals before considering any model-policy change. Measure elapsed time, final error and motion duty; keep approach and terminal correction costs distinct. No more audit-only work unless a consequential issue appears.
4. Keep M1 preparation practical and bounded; current actor/session, zone/world identity, independent heading and freshness, release and physical journey evidence remain outstanding. Existing sister-project assets are read-only development references, never runtime dependencies.
5. Batch related edits, run focused and full hosted regressions, and merge/push at meaningful verified checkpoints. The earlier 100-step online backlog is 99/100; step 090 requires independent local sister-repository verification. Original LEGION factorial archive remains unavailable and unverified; it is a separate evidence task, not a blocker for independently tested offline code.

Commands from repo root (synthetic input only):

```powershell
python -B -m rift_taxi.synthetic_terminal_finish
python -B -m rift_taxi.synthetic_journey_demo --help
python -B -m rift_taxi.synthetic_journey_demo PATH_TO_SYNTHETIC_TRACE --delay-steps 2 --out NEW_REPORT.json
python -B -m unittest discover -s tests -p 'test_synthetic*.py' -v
python -B -m unittest discover -s tests -q
```

The commands are reproduction instructions, not a claim that these CLI invocations have already been run. Preserve earlier physical and patch receipts, frozen V4 outputs, and negative results. No native or physical test was performed during this session.

## Accepted main checkpoint — November 24, 2026

**Merged:** PR #1 at `4a25968c2826f888f40a3509639c72ace5006c75`. Run [45549011214](https://github.com/360madden/Rift_Taxi/actions/runs/45549011214) verified exact premerge head `8d2bb60225652a7f4b617c73ebdad1b0851da3a1`: Windows 530/530, Ubuntu Python 3.11/3.14 each 514 passed and 16 skipped. User-approved strategy separates historical archive authentication from offline code acceptance. The original archive remains unavailable; physical M1 qualification and production disarm are unchanged. Stop expanding auditors unless a consequential defect appears; prioritize bounded offline functionality and meaningful grouped CI checkpoints.

## Historical online review branch checkpoint — November 24, 2026

**Former review branch:** `research/factorial-archive-audit` · [draft PR #1](https://github.com/360madden/Rift_Taxi/pull/1). The following is the historical premerge checkpoint, not the current main baseline. GitHub-hosted regression run [45548072486](https://github.com/360madden/Rift_Taxi/actions/runs/45548072486) at review head `630959ceeb0018703c52fada498628827298361a`, base `2e0a8cf65ea6345bf1b82c8b76ecf367260f7b94`, verified Windows Python 3.14 523/523, Ubuntu Python 3.14 and 3.11 each 507 passed/16 skipped, and Python 3.11 wheel installation with five isolated installed research module imports. This is the online research branch baseline, not the main baseline or a packaged Windows executable.

The V4 lookahead sensitivity candidate was rejected by its prespecified research screen: 360 ms geometric arrivals 43 to 46, settled arrivals 40 to 26. All 216 matched scenario/delay pairs agree on discrete outcomes across the original downloaded Windows and Ubuntu reports. A new per-route recount found 11 previously settled long-short-ladder cases lost with all 12 geometric arrivals retained. Prioritize separate synthetic terminal-settling evidence analysis, without reusing observed V4 as an unseen holdout. See [full research handoff](DELAY_FACTORIAL_AUDIT_HANDOFF.md), [protocol](V4_OFFLINE_COMPARISON_PROTOCOL.md) and [backlog](ONLINE_DEVELOPMENT_100_STEPS.md).

Original LEGION factorial report is still unavailable; do not substitute generated evidence or waive the recorded merge gate without a separate documented decision. No local sibling checkout inspection, current live qualification, or new physical journey was performed. Production remains disarmed.

## Latest checkpoint — November 24, 13:28 EST

The new [matched delay-factor study](M2_M3_DELAY_FACTORIAL_2026-11-24.md) retains 864 simulations and separates speed, yaw cap, timestep and nominal FIFO latency on the previously observed V3 geometries. At 330 ms, 263/288 reached the destination and 225/288 settled inside tolerance. Faster movement and higher yaw caps were adverse in matched comparisons; finer timesteps alone did not rescue the same 12 high-speed/high-yaw approach failures. Report bytes reproduced exactly. Four new focused tests passed; **498/498 full regressions passed** in 60.685 s, exit 0. Next investigate a separate latency-aware synthetic control experiment. No frozen policy changes or physical qualification.

## Previous checkpoint — November 24, 13:20 EST

The six recovery commits through `8e491db6fb894a0620d69fb037a740b69d2415b0` were pushed and independently checked against GitHub main. The current-install comparison found zero content changes across 266 files; publisher maintenance status is unconfirmed. V2 receipt verification and the committed 487-test recovery baseline remain documented in [the recovery runbook](PATCH_RECOVERY_2026-11-24.md).

The next offline steering revision shares one displacement-bounded arc projector between preview and simulation. It corrects false arrival at a stationary closed-loop start, future-leg jumps at overlaps, and misleading cross-track error while backtracking. A binary-search index skips ineligible route segments without changing clipping or earlier-arc tie behavior. Seven new regressions (including 1,500 exact full-scan oracle comparisons); focused suite 14/14, full suite **494/494** in 53.093 s on LEGION, exit 0. The original V3 evidence SHA and all 72 scenarios / 432 outcomes matched frozen replay. A new independent audit receipt is byte-identical to the previous receipt. See [validation](VALIDATION.md) for measurement and source details. These remain synthetic geometry improvements; no live game observation or input, no physical qualification, and no new default simulator policy.

## Resume here

The detailed, chronological technical handoff is [M1_HANDOFF_2026-11-23.md](M1_HANDOFF_2026-11-23.md), especially sections 33–35. This short checkpoint does not replace its original evidence or older physical experiment records. Read [AGENTS.md](../AGENTS.md), [autonomy policy](AUTONOMY_POLICY.md), [roadmap](ROADMAP.md), and [validation](VALIDATION.md).

At the historical November 23 checkpoint, the original pasted 421-test transcript was an earlier result. The baseline's verified end-of-day handoff records 442/442 passing tests. A fresh independent LEGION full-suite rerun at this checkpoint also passed all 442 tests in 55.750 seconds (exit 0). Local HEAD and independently queried GitHub main both matched the baseline before this handoff. A new doctor check on LEGION confirmed Python 3.14.10, stdlib runtime and the following qualification gates:

- native read-only candidate capture, burst and series available;
- physical A/D, W and camera-only calibration commands available as separately bounded diagnostics;
- public zone/world instance and native movement qualification false;
- qualified native reader not implemented, production game input disabled;
- no sibling repository required at runtime.

## Preserve the latest evidence

The frozen V3 benchmark includes 72 scenarios and 432 runs. Ordered-policy geometric arrivals for zero/one/three delayed steps were 72/72/60; corresponding settled-in-tolerance results were 72/72/47. Arrival plus 95% modeled forward duty was 26/22/12. Twelve high-delay approach timeouts and thirteen terminal tolerance exits remain negative evidence. All outcomes and source reports must remain frozen. Model parameters are coupled and delays idealized; these figures cannot establish actual RIFT performance.

The latest baseline independently validated saved V3 report bytes, scenario hashes, coverage, aggregate counts and full frozen replay. See section 35 of the detailed handoff for hashes and local artifact locations. Artifacts are Git-ignored; a GitHub push backs up tracked code, tests and documentation, not those original local receipts.

## November 24 possible patch — recovery first

Follow [the prepared patch recovery runbook](PATCH_RECOVERY_2026-11-24.md) before making new live-client claims. A pinned LEGION game manifest is verified; the Taxi-owned `rift_taxi.patch_readiness` offline gate requires two consistent post-update manifests and always leaves production input unauthorized. Reuse the existing Update Helper's `post_patch.py` two-capture workflow and `verify_cycle.py` independent bundle verification. Taxi's `python -B -m rift_taxi.patch_check` runner then performs the offline evidence, doctor, regression and source recheck ladder and preserves immutable local receipts; use the explicit runbook commands and a fresh run ID. Preserve the November 23 evidence as historical and keep all current M1 qualification gates intact.

## Priority for the next session

1. Continue read-only evidence integrity, reproducibility and source qualification; use existing sister-project research rather than duplicate tools.
2. Resolve M1's outstanding independent actor-heading, current public zone/world-instance identity, observation freshness, and release qualification. Preserve candidate-only classifications and do not use archived process identities as current ones.
3. Keep the V1/V2/V3 holdouts and all failures immutable. Evaluate synthetic lag and terminal-error improvements separately; do not promote an experimental policy based on training-grid success.
4. Keep the product destination-first: ordinary guides do not require stops, but mandatory passages, hazards and explicit hard stops remain binding. Prioritize smooth validated end-to-end travel over broad feature growth.
5. Preserve the standalone runtime and curated NPC/service scope. RR2 and RiftWorld are development references; Telara Fly remains permanently read-only. Do not introduce sibling runtime dependencies.

## Offline verification

From PowerShell in the repository root:

```powershell
git status -sb
python -B -m rift_taxi doctor
python -B -m unittest discover -s tests -q
git log -3 --oneline
```

No live RIFT action is part of this handoff. Keep production navigation disarmed until its actual evidence gates are met. Preserve detailed code commentary and commit only related, tested work.
