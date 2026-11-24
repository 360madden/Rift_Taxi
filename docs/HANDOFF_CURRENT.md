# Current RIFT Taxi handoff — November 23, 2026

**Host:** LEGION · **Repository:** `C:\work\Rift_Taxi` · **Branch:** `main`
**Baseline:** `2109a3e55225b35952b8d7aaae7ecad59e2f865e`
**Remote:** https://github.com/360madden/Rift_Taxi.git
**State:** M1 in progress; production navigation disarmed. M0 complete. M2/M3 experiments are offline only; M4–M6 remain planned.

## Resume here

The detailed, chronological technical handoff is [M1_HANDOFF_2026-11-23.md](M1_HANDOFF_2026-11-23.md), especially sections 33–35. This short checkpoint does not replace its original evidence or older physical experiment records. Read [AGENTS.md](../AGENTS.md), [autonomy policy](AUTONOMY_POLICY.md), [roadmap](ROADMAP.md), and [validation](VALIDATION.md).

At this checkpoint, the original pasted 421-test transcript is an earlier result. The baseline's verified end-of-day handoff records 442/442 passing tests. A fresh independent LEGION full-suite rerun at this checkpoint also passed all 442 tests in 55.750 seconds (exit 0). Local HEAD and independently queried GitHub main both matched the baseline before this handoff. A new doctor check on LEGION confirmed Python 3.14.10, stdlib runtime and the following qualification gates:

- native read-only candidate capture, burst and series available;
- physical A/D, W and camera-only calibration commands available as separately bounded diagnostics;
- public zone/world instance and native movement qualification false;
- qualified native reader not implemented, production game input disabled;
- no sibling repository required at runtime.

## Preserve the latest evidence

The frozen V3 benchmark includes 72 scenarios and 432 runs. Ordered-policy geometric arrivals for zero/one/three delayed steps were 72/72/60; corresponding settled-in-tolerance results were 72/72/47. Arrival plus 95% modeled forward duty was 26/22/12. Twelve high-delay approach timeouts and thirteen terminal tolerance exits remain negative evidence. All outcomes and source reports must remain frozen. Model parameters are coupled and delays idealized; these figures cannot establish actual RIFT performance.

The latest baseline independently validated saved V3 report bytes, scenario hashes, coverage, aggregate counts and full frozen replay. See section 35 of the detailed handoff for hashes and local artifact locations. Artifacts are Git-ignored; a GitHub push backs up tracked code, tests and documentation, not those original local receipts.

## November 24 possible patch — recovery first

Follow [the prepared patch recovery runbook](PATCH_RECOVERY_2026-11-24.md) before making new live-client claims. A pinned LEGION game manifest is verified; the Taxi-owned `rift_taxi.patch_readiness` offline gate requires two consistent post-update manifests and always leaves production input unauthorized. Reuse the existing Update Helper; preserve the November 23 evidence as historical and keep all current M1 qualification gates intact.

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
