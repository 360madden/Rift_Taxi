<div align="center">

<img src="assets/rift-taxi-banner.svg" alt="RIFT Taxi — destination-first navigation across Telara" width="100%" />

<br />

**Choose your destination. Keep moving. Let the local controller handle the route.**

[![Project status](https://img.shields.io/badge/status-M1%20in%20progress-9c78ea?style=for-the-badge)](docs/ROADMAP.md)
[![Offline tests](https://img.shields.io/badge/regression%20tests-442%20passing-27ae80?style=for-the-badge)](docs/VALIDATION.md)
[![Python-first](https://img.shields.io/badge/core-Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](pyproject.toml)
[![Runtime](https://img.shields.io/badge/target-Windows-344866?style=for-the-badge)](docs/ARCHITECTURE.md)

*A standalone, destination-driven navigation project for the RIFT MMORPG.*

[**Explore the roadmap**](docs/ROADMAP.md) · [**Current M1 handoff**](docs/M1_HANDOFF_2026-11-23.md) · [**See what works**](#-current-state) · [**AI-first development policy**](docs/AUTONOMY_POLICY.md) · [**Run the offline tools**](#-try-the-offline-tools) · [**Documentation**](#-documentation)

</div>

---

## 🚕 The idea

**Select a destination, press Go, and travel smoothly from start to finish.**

RIFT Taxi is being built to treat the **destination** as the objective—not each waypoint as a place to stop. The eventual controller will follow qualified, traversable corridors, steer **while moving**, skip or merge ordinary guide points where safe, and stop for genuine constraints or final arrival.

> **The measure of success is a verified, smooth end-to-end journey—not a high count of waypoints reached.**

### ✨ Design pillars

| 🎯 Destination-first | 🛣️ Continuous motion | 🧠 Local autonomy |
|:---|:---|:---|
| Navigate toward a chosen destination rather than a rigid chain of stop points. | Keep moving through ordinary route guides; turn while forward movement is active. | Planning, steering, progress checks and recovery run locally—no AI service is required during a journey. |

| 🧭 Evidence-backed routes | 🛑 Reliable STOP | 📦 Standalone by design |
|:---|:---|:---|
| Respect verified corridors, mandatory passages, build/zone provenance and unknown obstacles. | Treat input release, stale observations and session changes as explicit control conditions. | Reuse sister-project research without depending on those projects at runtime. |

**Development workflow:** [AI-first autonomous execution](docs/AUTONOMY_POLICY.md) is the default. The AI should carry out coding, investigation, Windows/game inspection, evidence collection, testing and GitHub synchronization with minimal user intervention while preserving accurate live-game qualification.

## 📍 Current state

> [!IMPORTANT]
> **M1 is in progress, not complete.** A Taxi-owned **read-only physical RIFT capture succeeded on LEGION** (same-owner XYZ/yaw candidates, matching actor/position matrix bits, and an actor-world translation reconstruction). Two original captures also show **changed XYZ and orientation values in the same process/owner epoch**, without a synchronized action timeline. A new **24-sample, ~100 ms read-only native series** also succeeded on the physical client using one pinned process handle. A separate **Win32 W/A/D scan-code backend** and **external release-supervisor prototype** are implemented and tested with fake input; **442 regression tests passed on Nov 23**. A **bounded W-only forward probe** has now passed dry-run/fake-sender and external-child tests, and **two real bounded 100 ms W-only pulses** now show 0.640 and 0.654 XZ source-unit candidate displacement at headings **59.25° apart**, accepted OS releases and separate stationary post-release checks. The native actor-matrix candidate matches their travel bearings within **0.061°** in both source-hashed experiments. Two 100 ms **physical A/D turn tests** now show complementary orientation changes, screenshot scene rotation/return, and accepted OS key-up with a supervised release child. A **real bounded left-mouse camera orbit** visibly changed the world view with zero same-owner XYZ, scalar yaw or actor-matrix yaw change, supported by independent mouse release and later stationary samples. An actual **A-only sender process crash** has now been survived by the independent release child, which issued a real OS-accepted A UP **without launcher backup**. A 100 ms pre-crash A hold produced a **−17.979° native actor-matrix turn**, followed by stable native state and all released W/A/D snapshots. [Original physical failure evidence](docs/M1_PHYSICAL_PARENT_CRASH_RELEASE_LEGION_2026-11-23.md). A new **read-only same-owner raw zone-key** acquisition found `0x487C9102` on the current physical client, stable across 12 source-pinned samples; it is **not** a public zone ID or world instance. [Original zone-key evidence](docs/M1_RAW_ZONE_KEY_LEGION_2026-11-23.md). A prebuilt, read-only RR2 zone-seed command has since returned **full native zone-ID candidate `z487C9102D2EA79BE`**, with a new offline Taxi importer verifying original SHA/owner/build/raw-key agreement; **Current-session public addon API correspondence and world instance remain unverified**. A historical RR2 validation document associates the same ID with the public API zone name Sanctum on a different build/session; this is corroboration, not current location proof. [Cross-source native zone study](docs/M1_RR2_NATIVE_ZONE_ID_CANDIDATE_LEGION_2026-11-23.md). The offline control gate now revalidates pose and lease timing after supervisor responses and every key edge, and attempts release even when its clock fails. The release-supervisor client now permanently invalidates timed-out or malformed acknowledgement channels, serializes requests, and preserves unresolved keys in partial STOP receipts. Native series scheduling now avoids catch-up bursts after slow reads, reports actual capture-start gaps, and refuses invalid or backward clock behavior. A new offline synthetic feedback simulator reached the three-bend fixture destination in 5.20 simulated seconds, with 100% forward-motion duty and 0.2842 synthetic units final XZ error. A fixed 180-case synthetic sensitivity benchmark subsequently produced 165 arrivals and 131 arrival-plus-duty successes; all 15 failures occurred at the lowest tested synthetic yaw-rate cap (60°/s). An opt-in turn-limited speed policy subsequently achieved arrival and at least 95% modeled forward duty in all 180 cases, with no lost baseline successes. A subsequent 162-case untuned route-shape holdout revealed 27 candidate short-zigzag failures and 15 lost baseline arrivals; the candidate remains opt-in. A third opt-in local-projection rejoin variant subsequently rescues all 27 zigzag failures (162/162 arrivals, 101/162 arrival-plus-duty successes) without losing prior successes or changing the original baseline. This is an ideal kinematic model, not a calibrated game actuator or live journey. **Authoritative actor/zone identity, body-heading, passive XYZ freshness, release under other failure modes, journeys and packaging** remain unverified or incomplete.

| Component | Status | Evidence / next gate |
|:---|:---|:---|
| Repository, contracts and design | ✅ Documented | [Architecture](docs/ARCHITECTURE.md) · [Product specification](docs/PRODUCT_SPEC.md) |
| Deterministic motion-trace replay | ✅ Implemented offline | [M1 implementation](docs/M1_IMPLEMENTATION.md) |
| RR2 source-provenance importer | ✅ Implemented offline | Historical original-source receipt; not a Taxi live run |
| Source-aware movement timing | ✅ Original RR2 trace analyzed offline | [Motion timing audit](docs/M1_MOTION_TIMING_AND_TELEMETRY_AUDIT_2026-11-23.md); 6.63-unit/s median sample speed, no causal input proof |
| Synthetic continuous-steering preview | ✅ Implemented offline | Produces steering intent, not physical movement |
| Driver-neutral W/A/D and watchdog STOP gate | ✅ Implemented offline | [M1 control-boundary tests](docs/M1_CONTROL_BOUNDARY.md); production input still gated |
| Single bounded A/D turn calibration | ✅ Two physical pulses, OS release observed | [Original visual/native/action evidence](docs/M1_PHYSICAL_AD_TURN_CALIBRATION_2026-11-23.md); body heading not yet fully qualified |
| Bounded W-only forward calibration | ✅ Two 100 ms physical W pulses, two angles | [Two-heading source-hashed alignment](docs/M1_TWO_HEADING_ALIGNMENT_LEGION_2026-11-23.md); max 0.061° residual, game-consumed release not proven |
| Camera-only orbit negative control | ✅ Physical left-mouse orbit and unchanged native angles | [Original screen/native/release receipts](docs/M1_PHYSICAL_CAMERA_NEGATIVE_CONTROL_LEGION_2026-11-23.md); body heading still candidate |
| Offline physical forward-bearing analysis | ✅ Two original W/release pairs verified | [Two-heading heading evidence](docs/M1_TWO_HEADING_ALIGNMENT_LEGION_2026-11-23.md); candidate kinematics only, no production yaw promotion |
| Independent release following real sender crash | ✅ **Physical A-only parent crash, child OS UP observed** | [Crash/release experiment](docs/M1_PHYSICAL_PARENT_CRASH_RELEASE_LEGION_2026-11-23.md); −17.98° actor-matrix rotation, no backup UP, stable later readings; not universal crash proof |
| Read-only Win32 process/window identity candidate | ✅ Implemented and OS smoke-tested | [M1 identity tests](docs/M1_WIN32_IDENTITY.md); actor/zone not yet verified |
| Same-owner raw self-zone key | ✅ Physical one-shot and 12-sample series | [Raw zone-key evidence](docs/M1_RAW_ZONE_KEY_LEGION_2026-11-23.md); `0x487C9102`, source-backed but not a public zone/instance ID |
| Typed native zone-ID candidate through existing RR2 | ✅ Source-hashed live read + standalone offline Taxi comparator | [RR2 reuse and comparison](docs/M1_RR2_NATIVE_ZONE_ID_CANDIDATE_LEGION_2026-11-23.md); `z487C9102D2EA79BE` candidate, public/API confirmation pending |
| Bounded native memory, candidate decoder and one-shot capture CLI | ✅ Live read-only candidate captured | [LEGION physical native evidence](docs/M1_LIVE_NATIVE_LEGION_2026-11-23.md); player semantics still candidate-only |
| Read-only multi-sample candidate burst | ✅ Four live stationary candidates captured | [Original source-hashed evidence](docs/M1_LIVE_NATIVE_LEGION_2026-11-23.md); static readings cannot prove freshness |
| High-cadence pinned native series | ✅ Three live 24-sample runs | [LEGION time-series handoff](docs/M1_LIVE_NATIVE_SERIES_LEGION_2026-11-23.md); candidate-only |
| Optional read-only Windows W/A/D key snapshots | ✅ Physical third 24-sample run | [Manual-key observation handoff](docs/M1_READONLY_MANUAL_KEY_OBSERVATION_LEGION_2026-11-23.md); 48 polls/key, no key-down observed or input injected |
| Optional same-owner position/actor matrix comparison | ✅ 9/9 live raw bits matched | [Matrix diagnostic](docs/M1_MATRIX_CANDIDATE.md); still not verified body yaw |
| Native XYZ cache-refresh guard diagnostics | ✅ Live one-shot + 4-sample burst | [LEGION refresh-guard evidence](docs/M1_LIVE_XYZ_REFRESH_GUARDS_LEGION_2026-11-23.md); both known guard routes ineligible, other writers unknown |
| Same-owner actor translation + two-capture comparison | ✅ Live candidate + offline evidence analysis | [Changed-state study](docs/M1_ACTOR_TRANSLATION_CHANGED_STATE_LEGION_2026-11-23.md); model transforms may share cached XYZ |
| Matrix-enabled bursts + five-phase offline comparison | ✅ Synthetic-tested | [Facing signature](docs/M1_FACING_SIGNATURE.md); source-hashed comparisons without action/heading claims |
| Taxi-owned fresh XYZ and actor-facing reader | 🔧 Next | Process/build/actor binding and observation freshness |
| Native Windows W/A/D scan-code backend | ✅ Production backend fake-sender tested; disarmed | [M1 Windows input](docs/M1_WIN32_INPUT.md); real OS W/A/D used only by separate bounded diagnostics |
| Separate-process release lease and cooperative ownership | ✅ Real A-key parent-crash recovery observed | [Physical fault evidence](docs/M1_PHYSICAL_PARENT_CRASH_RELEASE_LEGION_2026-11-23.md); actual child OS key-up and later stable game state, other release modes still unverified |
| Live input/release and navigation acceptance | 🔧 Next | Independently qualified actor/zone/pose and other fault modes, including late-DOWN/child loss; no route run yet |
| Smooth multi-bend live journey | ⏳ Not verified | Measured course with continuous forward travel |
| Desktop UI and portable distribution | ⏳ Planned | PySide6 target after the control milestones |

**Evidence matters:** simulated steering, successful OS input insertion, candidate native coordinates, a computed path and actual in-game arrival are **different claims**. RIFT Taxi will report them separately.

## 🗺️ Roadmap

```text
M0  Foundation & contracts           ✅ Documented
 │
 ▼
M1  Replay + pose/input substrate    ◐ Offline implemented · live pending
 │
 ▼
M2  Continuous straight travel      ○ Planned
 │
 ▼
M3  Smooth multi-bend driving        ○ Planned  ★ Core experience
 │
 ▼
M4  Verified local destination maps  ○ Planned
 │
 ▼
M5  Obstacle detection & recovery    ○ Planned
 │
 ▼
M6  Standalone desktop experience    ○ Planned
```

**Immediate critical path:** fresh, Taxi-owned XYZ/facing telemetry → bounded movement input and STOP → measured straight travel → smooth multi-bend travel. The [full roadmap](docs/ROADMAP.md) contains acceptance gates and evidence requirements for every milestone.

## 🧩 How it fits together

```text
                   ┌─────────────────────────────┐
                   │         RIFT TAXI           │
                   │  destination & local logic  │
                   └──────────────┬──────────────┘
                                  │
                ┌─────────────────┴─────────────────┐
                ▼                                   ▼
       Pose / facing reader                  Movement controller
       (OS & candidate built; qualification pending)      (Gate built; driver planned)
                │                                   │
                └─────────────────┬─────────────────┘
                                  ▼
                       Future verified RIFT session

       Versioned, local route evidence ──► Route acceptance
       (imported from research)           and trajectory tracking
```

**Runtime boundary:** RIFT is needed for live play; RR2, RiftWorld, Telara Fly, Workbridge, ChatGPT, cloud AI and other development tools are **not** runtime requirements. The design is **Python-first** with a scriptable CLI and a **planned PySide6 UI**. A small bundled Windows-native helper is possible only if measurement shows it is necessary.

### 🔗 Related research — reused, not duplicated

- **RiftReader2 (RR2):** native pose/input research and original movement evidence. Source receipts are imported with provenance.
- **RiftWorld:** world, geometry, collision and route research. Taxi should consume qualified **versioned local packages**, not rebuild the map pipeline.
- **Telara Fly:** permanently **read-only reference**; no direct Taxi runtime dependency or source modification.

See [research imports](docs/RESEARCH_IMPORTS.md), [RR2 handoff](docs/RR2_HANDOFF.md), [RiftWorld handoff](docs/RIFTWORLD_HANDOFF.md), [Telara Fly reference](docs/TELARA_FLY_REFERENCE.md) and [integration contracts](docs/INTEGRATION_CONTRACTS.md).

## 🧪 Try the offline tools

The CLI commands below are **offline analysis**. The test suite also performs read-only **process metadata and known-buffer memory checks on its own Python process**, plus synthetic native-field decoding. None of these commands launch RIFT, read RIFT memory or send game input.

Open **PowerShell** in the local repository directory (documented working checkout: `C:\work\Rift_Taxi` on **LEGION**):

```powershell
cd C:\work\Rift_Taxi

# Environment and fixture diagnostics
python -B -m rift_taxi doctor

# Compare stop/go with synthetic continuous travel
python -B -m rift_taxi compare samples\synthetic_stop_go.json samples\synthetic_continuous.json

# Preview steering intent against a synthetic motion trace
python -B -m rift_taxi preview-steering samples\synthetic_continuous.json

# Inspect pose/key timing (offline, never sends game input)
python -B -m rift_taxi measure-motion-timing samples\synthetic_continuous.json

# Re-run the regression suite
python -B -m unittest discover -s tests -v
```

The **opt-in, read-only** `inspect-native-candidate`, `inspect-native-burst` and `observe-native-series` commands require exact PID, process creation ticks, executable path/hash, window handle and host. `observe-native-series` acquires 3–128 owner-checked candidates from one pinned read-only process handle, recording observed sample timing and enforcing foreground/identity on every sample. Its opt-in `--observe-manual-keys` switch also polls Windows W/A/D high-bit states before/after native reads **without inserting any keys**; these snapshots are not proof of RIFT input consumption. See the [physical sampler evidence](docs/M1_LIVE_NATIVE_SERIES_LEGION_2026-11-23.md) and [key-observation experiment](docs/M1_READONLY_MANUAL_KEY_OBSERVATION_LEGION_2026-11-23.md). Both commands support `--include-matrix-candidate` and `--include-refresh-guard-candidate`: the burst compares 2–8 XYZ/yaw observations, optional matrices and source-pinned cached-XYZ refresh guards. Guard eligibility never establishes writer execution or passive freshness. The one-shot command also supports `--include-actor-translation-candidate` to reconstruct the source-pinned model-world translation; it is **not** an independent position provider. `compare-native-candidates` compares two exact-source, same-session saved one-shot reports **offline**. `compare-facing-phases` analyzes five complete, separately labeled matrix bursts **offline**. The native commands also offer `--start-delay-seconds` (0–15) to switch focus back to RIFT before reading, and refuse occupied output paths before capture. **These read-only commands alone do not establish physical movement, passive freshness or qualified body heading.** None of the commands auto-selects RIFT or enables movement; see [capture instructions](docs/M1_NATIVE_READONLY.md#explicit-pinned-candidate-capture-cli-m1-diagnostic-only).

The diagnostic commands `probe-ad-turn` and `probe-w-forward` are **separate from route navigation**. Both default to dry-run; physical input additionally requires explicit opt-in, a fresh independently reviewed suitable scene, exact process/actor pins, a short bounded action and an external key-release lease. Two A/D turns and one W-only pulse now have actual source-hashed physical results, still not autonomous navigation. See [A/D evidence](docs/M1_PHYSICAL_AD_TURN_CALIBRATION_2026-11-23.md) and [W-only implementation](docs/M1_BOUNDED_W_FORWARD_PROBE_2026-11-23.md).

The historical RR2 import includes a **72-position / 14-key-event** original-source receipt. Taxi's source-aware timing analysis found **6.63 source units/s median sampled speed during recorded W-held intervals**, but this is **not a qualified RIFT speed model or a new Taxi journey**. The installed Telemetry addon contains two 0.10-second `Inspect.Unit.Detail` polling paths, making naive API-quiet claims unreliable when active. See the [motion timing and producer audit](docs/M1_MOTION_TIMING_AND_TELEMETRY_AUDIT_2026-11-23.md) and [original M1 implementation handoff](docs/M1_IMPLEMENTATION.md).

## 📚 Documentation

| Start here | Deep dives |
|:---|:---|
| [📌 Product specification](docs/PRODUCT_SPEC.md) | Waypoint types, destination semantics and stopping rules |
| [🏗️ Architecture](docs/ARCHITECTURE.md) | Local controller, observation and input boundaries |
| [🗺️ Development roadmap](docs/ROADMAP.md) | Milestones, priorities and acceptance gates |
| [📏 Validation](docs/VALIDATION.md) | Benchmarks and measurable movement quality |
| [🔬 M1 implementation](docs/M1_IMPLEMENTATION.md) | Commands, trace provenance, test receipts and limitations |
| [🛑 M1 control gate](docs/M1_CONTROL_BOUNDARY.md) | Driver-neutral W/A/D, expiry watchdog, STOP/fault tests and live blockers |
| [🪟 M1 Windows identity](docs/M1_WIN32_IDENTITY.md) | Read-only PID/start/hash/HWND qualification and test evidence |
| [🔍 M1 native candidates](docs/M1_NATIVE_READONLY.md) | Read-only memory sessions, exact-build owner/XYZ/yaw decoding and unresolved live semantics |
| [🧭 M1 matrix comparison](docs/M1_MATRIX_CANDIDATE.md) | Source-pinned position/actor raw matrix comparison; no body-heading promotion |
| [📐 M1 facing signature](docs/M1_FACING_SIGNATURE.md) | Optional matrix bursts and five-phase source-verified offline comparison |
| [🧪 First live native capture](docs/M1_LIVE_NATIVE_LEGION_2026-11-23.md) | Source-hashed physical XYZ/yaw and 9/9 matrix evidence; explicit limitations |
| [🔬 XYZ cache-refresh guards](docs/M1_LIVE_XYZ_REFRESH_GUARDS_LEGION_2026-11-23.md) | Live branch input diagnostics, source hashes and why API/native agreement can be circular |
| [🧩 Actor-world translation and changed-state](docs/M1_ACTOR_TRANSLATION_CHANGED_STATE_LEGION_2026-11-23.md) | Physical actor translation, same-epoch XYZ/yaw differences and source-hashed offline pair proof |
| [📈 Source timing and Telemetry audit](docs/M1_MOTION_TIMING_AND_TELEMETRY_AUDIT_2026-11-23.md) | Historical RR2 speed/timing candidates and installed-addon API polling provenance |
| [⏱️ Live pinned native series](docs/M1_LIVE_NATIVE_SERIES_LEGION_2026-11-23.md) | 24 real owner-checked samples, cadence correction, evidence SHA-256s and limits |
| [⌨️ Passive manual-key observations](docs/M1_READONLY_MANUAL_KEY_OBSERVATION_LEGION_2026-11-23.md) | Optional W/A/D state snapshots, 48 key polls per key in live session; no injected input |
| [⌨️ Win32 input backend](docs/M1_WIN32_INPUT.md) | Standard scan-code W/A/D adapter and explicit arming |
| [🛟 External release supervisor](docs/M1_RELEASE_SUPERVISOR.md) | Separate-process lease, mutex, actual A-parent-crash OS release and remaining unverified failure modes |
| [🎮 First physical A/D turn calibration](docs/M1_PHYSICAL_AD_TURN_CALIBRATION_2026-11-23.md) | Real 100 ms A/D actions, native angle changes, screenshots and actual OS DOWN/UP receipts |
| [🚶 Bounded W-only calibration](docs/M1_BOUNDED_W_FORWARD_PROBE_2026-11-23.md) | Fail-closed W-only tool, default dry-run and release tests |
| [🏃 First physical W-only pulse](docs/M1_PHYSICAL_W_DISPLACEMENT_LEGION_2026-11-23.md) | Real 100 ms W, 0.640 XZ displacement candidate, accepted key-up and independent later stable pose checks |
| [🖱️ Bounded camera orbit](docs/M1_CAMERA_ONLY_ORBIT_PROBE_2026-11-23.md) | Dry-run-default left-mouse-only diagnostic and supervised release design |
| [📸 Physical camera negative control](docs/M1_PHYSICAL_CAMERA_NEGATIVE_CONTROL_LEGION_2026-11-23.md) | Same-owner unchanged native angles and position while actual world view changed |
| [🧭 Two-heading kinematics](docs/M1_TWO_HEADING_ALIGNMENT_LEGION_2026-11-23.md) | Two source-hashed physical W motions 59° apart, near-exact actor-matrix directional agreement |
| [🛟 Physical crash-release recovery](docs/M1_PHYSICAL_PARENT_CRASH_RELEASE_LEGION_2026-11-23.md) | Actual abrupt input-parent exit, independent child A-up, native turning response with bounded A prehold and 12 stable post-release samples |
| [🗺️ Read-only raw zone context](docs/M1_RAW_ZONE_KEY_LEGION_2026-11-23.md) | New opt-in self-owner raw zone-key reader, 12 stable physical samples, original hashes and strict public-zone limitations |
| [🧩 RR2 native zone-ID reuse](docs/M1_RR2_NATIVE_ZONE_ID_CANDIDATE_LEGION_2026-11-23.md) | Reused built read-only RR2 zone seed, SHA-pinned typed native ID and Taxi-only offline comparison; no duplicated TLS parser |
| [🔌 Integration contracts](docs/INTEGRATION_CONTRACTS.md) | Existing upstream formats versus proposed Taxi formats |
| [📖 Documentation hub](docs/README.md) | Index of research, handoffs and architecture notes |
| [📝 Durable decisions](docs/DECISIONS.md) | Project decisions and non-negotiable boundaries |
| [📍 Curated destinations](docs/NPC_DESTINATIONS.md) | Travel targets for services and selected NPCs |
| [🤝 Developer instructions](AGENTS.md) | Local workflow and repository-specific guardrails |

## 🔭 What's next?

1. **Finish M1:** independent body-facing verification using the two-angle physical W evidence and camera negative control, repeatable time-resolved W response under independent actor/zone and source-freshness checks, current actor/zone/native XYZ and body-heading qualification, and qualification of crash-release behavior beyond the demonstrated A-only parent exit.
2. **Measure real behavior:** verify yaw response, movement latency, coast and post-release evidence rather than extrapolating from synthetic traces.
3. **Prove M2–M3:** achieve a measured straight arrival, then a qualified multi-bend journey with no unnecessary stops at guide points.
4. **Expand only on evidence:** introduce local world packages, recovery and UI after the movement foundation is dependable.

---

<div align="center">

**RIFT Taxi** · *Destination over waypoints. Motion over stop-and-go. Evidence over assumptions.*

[↑ Back to top](#)

<sub>Independent community research project. Not affiliated with the RIFT game publisher.</sub>

</div>
