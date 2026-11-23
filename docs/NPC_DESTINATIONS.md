# Curated NPC and service destinations — deliberately limited initial scope

**Decision date:** 2026-11-23. **Status:** planned only. NPC travel and live NPC identification have not yet been implemented in RIFT Taxi.

## Purpose

Provide a small set of practical **travel-to-NPC or service-object** destinations. The core taxi milestone remains smooth, continuous start-to-finish movement. Do not divert early development into a general NPC directory, combat logic, quest automation, or service UI interactions.

## Prioritized categories

| Priority | NPC destination | Scope |
|---|---|---|
| **P0 pilot** | **Sanctum Porticulum Master** (the Porticulum NPC in/at the Sanctum castle/keep, per operator) | Establish actual NPC identity, position, room/floor, reachable approach, then make it a selectable taxi destination |
| **P1** | **Personal storage NPCs — bankers / vault access** | Select one or more convenient regular **character bank** NPCs in Sanctum; navigate to a reachable approach point |
| **P1** | **Healers / soul healers** | One verified service NPC and approach point first; expand only after travel is proven |
| **P1** | **Auction-house NPCs / auctioneers** | One verified auctioneer destination and approach point first |
| **P1** | **Auction collection — mailbox** | A separate destination for collecting auction purchases, won items, returned bids and sale proceeds through in-game mail; use a verified accessible mailbox approach point, not an assumed auction-collection NPC |
| **P2** | **Selected main-story quest NPCs** | Hand-curated high-value storyline NPCs only; verify quest context/location/phase before offering travel |

**Auction collection versus auctioneer:** Gamigo's official RIFT mail instructions confirm that auction purchases, outbid returns and sale proceeds are delivered through the mail system. Players retrieve attached items by accessing a **mailbox**. A mailbox is therefore a distinct **service-object destination** from an auctioneer or banker; do **not** invent a dedicated auction-collection NPC. Only travel-to-mailbox is in scope; opening mail or removing attachments is deferred. See the official source below.

**Personal bank versus guild bank:** The main storage destination is the *player's own bank/vault*. Guild-bank NPCs are distinct and optional, not substitutes. Gamigo's official guild-bank support lists Sanctum guild banks near south-side bankers in Thontic's Row and Bahralt Street; do not assume these provide ordinary personal storage.

**Porticulum location caution:** A historical Sanctum porticulum waypoint `/setwaypoint 7451 3050` exists, but it is a **porticulum area marker, not a measured Porticulum Master NPC position**. The user specifically wants the Porticulum NPC at Sanctum castle; validate the actual current game NPC and reachable approach rather than treating the portal marker as exact.

**Personal-bank location lead:** CADRIFT's historical guide places a Sanctum banker in the crafting area near `/setwaypoint 7393 2998` and mentions additional bankers near the pub. This is a discovery lead only: current NPC presence, height/room, interaction range and route clearance need physical confirmation.

**Other service leads:** A historical Sanctum walkthrough describes merchants/auctioneers, bankers, and a healer in Thontic's Row near the fountain and pavilions. These labels are not qualified current player coordinates. **New RiftWorld November 23 bridge handoff** confirms a Quicksilver Medic beside the **Watch temple** at the start but **does not** identify a healer in Sanctum's city-side area; the bridge journey ended at Tavril Plaza. The catalog must distinguish those areas and withhold an unverified city healer arrival.

## Definition of travel to an NPC or service object

1. User selects a curated destination (e.g., `Sanctum → Personal Bank` or `Sanctum → Auction Collection (Mailbox)`).
2. Taxi loads a **locally bundled** destination record, checks zone/map/build/coordinate transform and selects an approach on a known accessible floor.
3. Taxi plans a valid corridor and runs continuously through guidance waypoints; does not stop at intermediary guides.
4. At the final approach, release input and independently confirm player arrival in position and height.
5. If applicable, make a **fresh local NPC identity/name/position or mailbox-object check**; distinguish `arrived-at-approach` from `npc-present-confirmed`. A historical spawn marker must never count as live NPC confirmation.
6. No automatic banking, mail opening/attachment retrieval, item transfer, auction posting, healing, accepting quests, porticulum menu activation or teleportation during this phase.

NPC or service-object coordinates may lie behind a counter, across an obstruction, or on a different elevation. The destination must be a **qualified reachable approach point**, not necessarily the NPC's exact XYZ. Unknown height, disconnected buildings and unqualified route geometry yield an honest unavailable result.

## Local destination record — suggested `npc-destination/1`

- Stable local `id`, user label and role: `porticulum`, `personal-bank`, `guild-bank` (optional), `healer`, `auctioneer`, `auction-mailbox`, `story-quest`.
- Game/zone, world instance, floor/height band, source and NPC template ID if verified; do not confuse transient exact unit IDs with durable NPC identity.
- Source-tagged spawn coordinates; verified approach XYZ/polygon and tolerance; map/scene transform and corridor evidence.
- Timestamp, acquisition class (`historical-source`, `native-candidate`, `live-confirmed`), game-build applicability, source hashes, provenance and confidence.
- Optional quest phase availability/selection rules. Never invent an interaction range.
- Mark `navigable` separately from `known-location` and `current-npc-present`.

## Milestone position

- **No comprehensive NPC index or dynamic NPC pursuit in M1–M3.** Smooth steering through multiple bends remains the primary product gate.
- **M4:** Introduce a *small, locally packaged curated destination registry* and offline import validation. Start with Sanctum Porticulum Master and one personal banker only when the records have qualified approach coordinates.
- **M5–M6:** Add healer, auctioneer, **auction-collection mailbox**, and a handful of main-story quest NPC destinations. A Guild Bank and additional NPCs are optional future scope.
- A future `visit service` action is separate from `drive to NPC`, requires its own evidence, and is not part of this feature.

## Historical sources (not game-build-specific current validation)

- CADRIFT porticulum location guide (Sanctum marker, not exact NPC): https://www.cadrift.net/lists/locations/porticulums/
- CADRIFT new-player guide (ordinary Sanctum bankers): https://www.cadrift.net/gameplay/character/new-player-guides/
- Gamigo official RIFT Using In-Game Mail (auction purchases and sale proceeds use mailboxes): https://support.gamigo.com/en/support/solutions/articles/201000105465-rift-using-in-game-mail
- Gamigo official RIFT Guild Bank Overview: https://support.gamigo.com/en/support/solutions/articles/201000105433-rift-guild-bank-overview
- Historical Sanctum walkthrough: https://www.alteredgamer.com/rift/111534-planes-of-telara-navigating-sanctum/
- RiftWorld's Sanctum Watch NPC catalog and RR2's nearby unit readers are useful **reference patterns**, not the Sanctum castle NPC's confirmed current coordinates. Source handoffs: [RiftWorld](RIFTWORLD_HANDOFF.md), [RR2](RR2_HANDOFF.md); the November 23 source is `RiftWorld/HANDOFF-2026-11-23-SANCTUM-BRIDGE.md`.

## Acceptance tests for each curated destination

One selected NPC/role or mailbox service-object destination at a time: verified NPC identity or explicitly flagged historical-only; validated coordinate/height/floor; locally packed data without runtime access to RR2/RiftWorld; continuous movement across guides; independent final stop and arrival receipt; no unexpected service clicks; clear absence/unreachable outcomes.
