# Durable design decisions — 2026-11-23

| ID | Decision | Why | Revisit trigger |
|---|---|---|---|
| D001 | Repo name `Rift_Taxi` under `C:\work`, branch `main` | Distinct product from RR2 and RiftWorld | Explicit user rename |
| D002 | Standalone local runtime | No hidden dependence on research apps or remote services | Never dilute without explicit approval |
| D003 | Python-first engine and eventual PySide6 UI | Rapid geometry/control iteration and familiar local tooling | Measured latency or native interoperability bottleneck |
| D004 | Small Taxi-owned native helper is optional | Preserve reliable Windows input/pose access where Python adds timing risk | Evidence from benchmarks |
| D005 | Destination-first, guide points skippable | Avoid stop/start navigation disguised as waypoints | Never dilute without explicit approval |
| D006 | Continuous forward with steering while moving | Smooth NPC-like travel is the central product capability | Measured game-control limitation |
| D007 | Mandatory passages, hard stops and destination are binding | Smooth shortcutting cannot invalidate a route | Only explicit route authoring |
| D008 | Verified world packages are local assets | RiftWorld remains a research producer, not runtime dependency | Versioned data contract enhancement |
| D009 | Independent STOP, exact game identity and fresh observations | Existing RR2 tests exposed timing, stale-source and release failures | Evidence of a stronger mechanism, not convenience |
| D010 | Offline replay first; clear-ground physical test second | Fast reproducible iteration and measured control quality | After deterministic baseline established |
| D011 | No new HKX/collision reconstruction framework | RiftWorld already owns research; Taxi owns consumption and navigation | Explicit ownership change |
| D012 | Git author `360madden <360madden@gmail.com>`, repo-local | Match existing verified LEGION author settings | Explicit user change |
| D013 | Planning/bootstrap does not imply game input or GitHub remote | Separate initial setup from runtime tests and publication | Later explicit instruction |
| D014 | NPC and service destinations stay small and curated: Sanctum Porticulum Master, personal bank, healer, auctioneer, separate auction-collection **mailbox**, and selected main-story quest NPCs | Useful destinations without becoming a broad NPC directory; official RIFT auction delivery occurs through mail | Explicit user expansion and verified evidence |
| D015 | Maintain source-pinned read-only RR2/RiftWorld references and **permanently read-only Telara Fly**; Taxi only imports validated, locally packaged data and selectively reviewed implementation techniques | Prevent duplicated world research, source mutation, hidden runtime coupling and coordinate mistakes | Explicit change of project ownership |
| D016 | A complete Detour path or composite staged movement route is never by itself clearance or one continuous successful Taxi trip | Nov 23 bridge includes an unmodeled banner pole; prior RR2 arrivals include steering stops | Only independently verified continuous live receipt and corridor coverage |

Decisions are requirements until revised. A new result that challenges one should document evidence and a proposed replacement rather than silently changing direction.
