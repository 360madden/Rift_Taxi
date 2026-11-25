# Current RIFT Taxi handoff — November 24, 2026

## November 25 morning — recovery and standalone automation

PR #8 accepted at 93199e2; hosted synthetic Windows recovery rehearsal and independent verifier succeeded (556/556, 29 files). LEGION synchronized to that main; current-main recovery replay using archived manifests passed 556/556 and 29-file verification. Current executable hash matches the baseline, but updater completion and full current inventory remain unverified. RIFT login unavailable. See [recovery runbook section 9](PATCH_RECOVERY_2026-11-24.md#9-november-25-morning-legion-validation).

New standalone CLI reporting supports --summary (compact JSON, with optional full receipt saved separately) and --require-settled (exit 1 for a completed but unsettled model run; invalid inputs and I/O refusals remain exit 2). Legacy defaults unchanged. Local focused suite 17/17; full 559/559 passed (66.049 s, exit 0). Keep all modes synthetic and production disarmed.


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
