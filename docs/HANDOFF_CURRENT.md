# Current RIFT Taxi handoff — November 24, 2026

**Host:** LEGION · **Repository:** `C:\work\Rift_Taxi` · **Branch:** `main`
**Historical November 23 baseline:** `2109a3e55225b35952b8d7aaae7ecad59e2f865e`
**Remote:** https://github.com/360madden/Rift_Taxi.git
**State:** M1 in progress; production navigation disarmed. M0 complete. M2/M3 experiments are offline only; M4–M6 remain planned.

## Online review branch checkpoint — November 24, 2026

**Review branch only:** `research/factorial-archive-audit` · [draft PR #1](https://github.com/360madden/Rift_Taxi/pull/1). The LEGION/main checkpoint below remains the last accepted main checkpoint. GitHub-hosted regression run [45548072486](https://github.com/360madden/Rift_Taxi/actions/runs/45548072486) at review head `630959ceeb0018703c52fada498628827298361a`, base `2e0a8cf65ea6345bf1b82c8b76ecf367260f7b94`, verified Windows Python 3.14 523/523, Ubuntu Python 3.14 and 3.11 each 507 passed/16 skipped, and Python 3.11 wheel installation with five isolated installed research module imports. This is the online research branch baseline, not the main baseline or a packaged Windows executable.

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
