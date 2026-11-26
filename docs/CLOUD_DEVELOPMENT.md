# Cloud-first development — Rift_Taxi

Approved 2026-11-27. This policy is for **development**, not the deployed Taxi runtime.
GitHub is the source of truth; the standalone Python application must never depend
on GitHub, ChatGPT, Workbridge, cloud services, sibling repositories or network
access for local operation.

## Baseline and decision

At commit 9c44930, LEGION Python 3.14.10: 660/660 tests, 112.650 seconds.
Discovery found 660 unique IDs across 64 modules, no loader errors. The existing
GitHub Actions PR run 45886526464 succeeded on the same PR head in 86 seconds:
Linux Python 3.14 test step 42 s, Windows recovery rehearsal 62 s, Linux Python
3.11 full test step 49 s. The workflow already runs automatically on updates to
the open PR, though it has no independent push trigger. Do not assume four runners
will outperform this existing baseline; measure overhead and runner-seconds.

## Workflow

- Start with GitHub status, exact branch/commit, CI receipts and current handoff.
  Prefer cloud-accessible source, tests, simulation, evidence analysis, and package
  verification. Do not require a physical PC for ordinary development.
- Reserve LEGION/AMD-DESKTOP for real installed-build/session checks and explicitly
  admitted physical experiments. No cloud-hosted job attaches to RIFT, accesses
  local game files, or sends game input. Physical evidence stays separately scoped.
- Use branch-local commits, non-force pushes and actual remote verification.
  Prefer one coherent change per checkpoint; preserve main and existing required
  PR checks. Do not mistake a PR head SHA for a checked-out merge SHA.
- Use independent jobs where parallel execution reduces elapsed time or isolates
  failures. Never count CI jobs as AI subagents; do not invent background workers.
- Default zero additional paid infrastructure; standard hosted runners only.
  No paid/larger runners, self-hosted runners or persistent cloud services without
  a demonstrated requirement and separate approval.
- Keep raw physical captures, credentials, proprietary game data and private
  configuration out of the public repository and public CI artifacts. Use synthetic
  or explicitly approved portable fixtures; record origin, content digest, scope
  and evidence classification. Generated cloud test receipts retain only test IDs,
  counts, source identity and timing. Upload only explicit generated paths.

## First implementation: measured parallel validation pilot

`scripts/cloud_test_runner.py` discovers all unittest tests and deterministically
balances complete modules by test count, preserving class/module fixtures and
discovery order. Each shard derives its own inventory from the exact checkout.
The merger independently recomputes the plan and refuses missing/duplicate
shards, wrong commit/plan, lost test coverage, unexpected skips or unsuccessful
outcomes. Linux declared Windows-only skips are counted explicitly, not called
passes. Hosted clean checkout and workflow SHA are required. Local dirty checkout
runs are labeled as such and are not remote proof.

`docs/cloud-fast.yml.example` is an **inactive** template for a proposed opt-in measured pilot on research/cloud
branch pushes affecting source/test/runner/workflow/package paths. Four standard
Linux 3.14 jobs and one aggregate verifier, no game, read-only token permissions,
obsolete same-ref pilot cancellation, 14-day receipt retention. The existing
cross-platform PR workflow stays intact during the pilot; duplication is temporary
and deliberate to measure relative latency and preserve required checks.
GitHub rejected the original workflow-containing push because the current OAuth authorization lacks `workflow` scope. The complete original commit `a1322aa` is retained on local branch `cloud/pilot-workflow-local-20261127`. The regular research branch publishes the runner, tests and inactive template only. No workflow permission bypass, credential change, or pilot activation occurred. Existing PR CI can validate the new Python tooling independently of the physical PC. After explicitly granted workflow-write access, review and install the template as `.github/workflows/cloud-fast.yml` and measure a real run.

Do not enable branch protection on the pilot until successful real runs and
coverage/skip parity are established.

Commands from repository root (each output path must be new):
```sh
python -B -m scripts.cloud_test_runner plan --shards 4 --out cloud-results/plan.json
python -B -m scripts.cloud_test_runner run --shards 4 --index 0 --out cloud-results/shard-0.json
# Run indices 1, 2, 3 independently with their corresponding output paths.
python -B -m scripts.cloud_test_runner merge --shards 4 --dir cloud-results --out cloud-results/merged.json
```

## Acceptance and next roadmap

1. Verify deterministic inventory, module grouping and negative receipt tests.
2. Verify a real hosted run and aggregate, including all skips and exact checkout.
3. Compare end-to-end wall time, longest shard, total runner-seconds and setup
   overhead against the existing Linux test step/whole PR workflow. Count balance
   is a first approximation, not a speed guarantee. If the pilot loses, keep
   useful receipt tooling and consolidate instead of adding more jobs.
4. Introduce measured module-time balancing if skew dominates; keep Windows
   recovery and minimum-Python packaging authoritative.
5. Separate extended synthetic benchmark execution from ordinary validation
   when measured cost warrants it. Reuse existing simulation modules and pinned
   scenario designs; never promote synthetic results to physical qualification.
6. Build a small portable synthetic evidence library and artifact manifest,
   then demonstrate a full cloud-only change/test/commit with LEGION not required.
7. Continue physical M1 qualification in its separate lane; existing desktop
   deployment blocker and position/heading/release gates remain unchanged.

The proposed 85% cloud workload is a target, not a measured result. This first
slice deliberately avoids extra orchestration infrastructure until hosted
evidence establishes its value.

## Portable single-runner orchestration

`scripts/cloud_parallel.py` launches independently bounded unittest shard subprocesses
and a separate merge subprocess from an exact **clean Git checkout**. It works on a
standard cloud compute host, ordinary developer PC, or isolated CI fixture with Python
3.11+ and Git; no new workflow permission is required. Example (new ignored output
folder, or an output path outside the checkout):

```sh
python -B -m scripts.cloud_parallel --shards 4 --workers 4 --timeout-seconds 300 --out-dir cloud-results/NEW-batch
```

The batch generates a unique execution ID and carries it through each plan/shard/merge.
Hosted identities additionally include GitHub repository, run ID and retry attempt.
A receipt from another batch or attempt cannot satisfy the merger even at the same
commit. Each direct subprocess has a bounded timeout, a separate retained log and
an explicit outcome. Missing/failed/timed-out shards prevent a successful aggregate.
A timeout does not prove that all descendants have settled; no retry or live release
claim is implied. Batch wall time, shard wall time and summed process durations are
separate measures, not billing or CPU consumption. Do not upload arbitrary raw logs.

The first cloud-only source checkpoint uses GitHub's repository connector and existing
PR CI; no LEGION edit/build is needed. Disposable integration tests exercise real
Git checkouts, successful and failed subprocess shards, declared skips, dirty checkout
refusal, batch/attempt isolation and exclusive output. The new four-job Actions
workflow remains inactive pending workflow-write permission. Full-repository timing
comparisons require an actual full checkout run; miniature fixtures do not qualify
performance of the complete suite.

## Verified portable batch checkpoint

GitHub-only source commit `5e79dcd` passed hosted PR run 45888250727 in 69 s.
Windows 3.14: 672/672 (39.119 s); Linux 3.14: 656 passed, 16 Windows-only skips
(55.038 s); Linux 3.11: 656 passed, 16 skips (31.562 s). The six new integration
tests passed on all three environments. The underlying PR merge checkout is not the
head SHA (Windows receipt recorded c79d1089e82b1b1d9da853b45e0c6171e38a3d94).
These are real hosted full-regression results, not a full-suite parallel speedup
measurement. The miniature Git/subprocess tests establish the orchestration contract.

## Portable synthetic fixture library

`samples/cloud_fixtures.json` explicitly lists the two existing authored synthetic
motion traces. Each row pins its exact raw SHA-256, byte length, generator,
route/units and point/pose/event counts. `scripts/cloud_fixture_library.py` refuses
unknown, missing, malformed, historical or mismatched entries; verifies each exact
byte sequence; and reuses the existing Taxi trace parser on an isolated copy.
No local captures, proprietary game files, historical originals or raw player data
are imported. A committed fixture manifest is a content-integrity boundary, not
source authenticity or physical qualification.

```sh
python -B -m scripts.cloud_fixture_library
# Optional, with an existing output parent and a new filename:
python -B -m scripts.cloud_fixture_library --out cloud-results/NEW-fixtures.json
```

Ordinary hosted regression now verifies the actual repository samples plus negative
fixtures, without new Actions permission. The initial catalog is intentionally
small. Add only explicitly reviewed portable synthetic inputs; keep generated
reports ignored and never scan or publish physical capture directories automatically.

## Continuous integration as a development gate

Verified baseline: fixture-library PR head 005a8bc, run 45888651814, all three jobs
successful. Windows 680/680 in 70.702 s; both Linux lanes 664 passed + 16 platform
skips (3.14: 54.101 s; 3.11: 39.021 s). Total workflow 98 s from creation to last
update. Windows was the critical lane (95 s job elapsed, versus 64 s Linux 3.14
and 53 s Linux 3.11). These are individual observed runs, not a stable benchmark.

The normal development loop is focused checks -> coherent commit -> push ->
**exact-head hosted CI gate** -> review failures or accept checkpoint -> next
dependent change. Independent design/review can proceed while CI runs, but do
not claim validation of untested changes or merge a stale green head.

`scripts/ci_checkpoint.py` verifies a successful existing Offline regression PR
run and all three exact attempt-specific job receipts, including required tests,
patch rehearsal, packaging and artifact steps. It rejects stale head, wrong
branch/run/attempt, missing or duplicated jobs, skipped required steps and
invalid timestamps. It reports the longest job and summed job elapsed time
(not billing), and never treats metadata alone as a verified test count,
authenticated attestation, or physical qualification. Selective reruns lacking
the entire attempt inventory are refused rather than mixing attempts.

Example from a cloud checkout with a separately authenticated gh CLI:
```sh
python -B -m scripts.ci_checkpoint --head 005a8bcd8b2c1169b02420f3793a5a3f94e1e5af --branch research/journey-automation-reporting --run-id 45888651814 --attempt 1
```
Or supply both `--run-json` and `--jobs-json` (exact attempt response), with
optional exclusive `--out`. The coordinator must independently check that the
expected head is still the remote branch tip before and after collecting evidence.

`docs/offline-regression-optimized.yml.example` is an **inactive** minimal
optimization proposal for the existing workflow: cancel obsolete same-PR runs
and remove the duplicate 29 focused minimum-version test executions already
covered by its full suite. Keep all three required job names, Windows recovery,
full minimum-Python suite, packaging, and existing research artifacts. No active
workflow or branch protection is changed. Workflow-write authorization is still
required before installation; do not circumvent the earlier GitHub refusal.

Measure three comparable successful runs after activation before adopting further
changes. Prioritize the Windows critical path and a genuine full-checkout parallel
benchmark, not more unmeasured runners. Keep the four-job pilot optional until
it demonstrates improved end-to-end latency and exact coverage. Separate long
research benchmarks only after preserving required checks and artifact parity.

## November 27, 04:25 PHT — authorized CI activation

User completed GitHub CLI authorization. LEGION independently verified the active
360madden account and OAuth workflow scope; the clean research branch was
fast-forwarded from 4183046 to 5bd9be7. The exact-head CI checkpoint verifier
admitted prior run 45889172411, attempt 1, all three required jobs, 96 s from
creation, 92 s Windows critical job. The historical permission-blocked notes
above describe earlier checkpoints and are superseded by this authorization.

Activate the reviewed minimal optimized Offline regression workflow: cancel
obsolete runs on the same PR/ref, remove the 29 duplicate focused test executions
on the minimum-version lane, preserve required job names and existing regression,
recovery, installed-package and research artifact steps. Activate the separate
Cloud validation pilot using four hosted Linux shards and an independent merge.
The pilot's push filters are deliberately narrower than the initial template:
only cloud runner/test/workflow changes on research/cloud branches trigger it,
so ordinary development does not continually duplicate the comprehensive suite.
Artifacts are named by run attempt to prevent retry collisions and merge only
receipts from the current attempt. Full-suite parallel timing remains a measured
pilot, not a replacement gate. Keep main, branch protection and production game
input unchanged. The older local workflow branch remains a historical record.

Activation is not proof of CI success. Record fresh hosted outcomes and aggregate
coverage before accepting the pilot, then compare actual wall time and total job
seconds. No paid infrastructure, game input or sibling-service changes.

## First real parallel pilot and timing instrumentation

Activated CI head 20294ee passed both workflows. Pilot run 45890935749 (attempt 1)
completed in 46 seconds, with 688 discovered, 672 passed, 16 declared platform
skips and exact coverage confirmed by the independent merge. Four equal-count
shards ran 172 tests each: 9.844640, 5.142912, 18.108312 and 7.588015 seconds.
Sum 40.683879 s, maximum 18.108312 s. Same-head comprehensive PR run
45890943852 passed in 78 s from creation to update. Its Linux regression step
was 43 s (provider step timing, includes command overhead). The pilot has
comparable Linux coverage, but is not a substitute for Windows and Python 3.11.
Individual runs vary; this is not a stable speedup or billing claim.

The count-balanced plan is demonstrably skewed. Add complete-module wall
timings to the existing shard receipt and aggregate, including class and module
setup/teardown and all actual test executions. Use real discovered module
identity (rather than guessing nested TestCase dotted IDs); retain whole modules
and their discovery order. Validate exact module coverage and enclosing timing
bounds independently during merge. Each module uses an ordinary unittest
runner; successful coverage is still decided by the actual test IDs, skips and
failures. This additive receipt field changes the plan hash; old receipts are
replayed using their producing commit, not mixed with the new plan.
The next pilot will measure module cost. Only then choose weighted assignments.

## Measured weighting experiment

Timing pilot at 6c04452, run 45891235786, attempt 1, passed in 40 s: 691
discovered, 675 passed and 16 expected skips; 68 complete modules. The four
count-balanced shard durations were 5.391778, 13.873269, 14.325827 and 7.900759 s.
The independent aggregate produced plan SHA-256
e425d29cdfc8ff046a29cedfee4d10445bc4ae15a7c36c86a23930d8445439ae.
Using those observed module durations, greedy largest-cost-first allocation
predicts about 10.37 s per shard on that historical sample. This is a
prediction, not a measured speedup.

Commit the observed module cost catalog at cloud/test_module_costs.json
(source run, commit, plan hash, exact observed microseconds and test counts).
The planner uses it only on Linux Python 3.14, scales known costs by current
test counts, estimates unseen modules by median historical per-test cost and
retains count balancing on other platforms. It checks source metadata and
complete unique sorted cost rows; all actual discovered tests remain required.
Profile digest and estimated loads are bound into the plan and aggregate.
No raw logs or physical data are added. Verify the next hosted run and compare
actual longest shard and total workflow time before promoting this as faster.

## Windows exact-inventory and timing checkpoint

Weighted head acfd567 passed the comprehensive PR run 45891478942 in 101 s.
Windows executed all 694 tests in 69.124 s, with its recovery step taking 74 s
and the complete job 97 s. Both Linux jobs passed. Weighted pilot 45891470995
passed in 37 s, 694 discovered/678 passed/16 skips, longest shard 13.859407 s,
sum test time 41.088964 s. Compared with the preceding 40 s timing-enabled
pilot, the observed wall gain was modest and total job elapsed seconds rose
from 84 to 90; there is no controlled causal speedup claim.

The Windows rehearsal now derives an exact count from the existing clean
checkout discovery planner (single shard, no declared skips), requires at
least the historically verified 694 tests, and binds the producer and
independent verifier count and Git HEAD to that inventory. The old workflow
CLI floor of 556 no longer silently permits an unexpectedly reduced suite.
The actual patch-check and verifier commands, original bundle format and
unskipped serial regression requirement are unchanged. The rehearsal summary
adds discovery, recovery and independent verification wall durations, plan
digest, module count and exact test count. This is a stricter coverage gate
and phase measurement, not a demonstrated Windows latency reduction. The
inventory preflight adds some overhead. Exact count is not equivalent to
exact executed-ID verification; the parallel pilot retains the latter.
Next use measured Windows module costs in an isolated hosted experiment
rather than prematurely replacing the required serial patch rehearsal.

## Opt-in Windows parallel profiling experiment

Use .github/workflows/cloud-windows-profile.yml to measure the full Windows
suite with four independent standard hosted machines and a fifth independent
coverage merger. Unlike a single Windows host with concurrent test processes,
separate runners avoid cross-shard collision of named kernel mutex fixtures
and other process-global resources. The existing Windows serial patch recovery
and its original receipt verifier remain mandatory. The first experiment
uses count balancing (the Linux cost profile is platform-specific); it records
complete Windows module costs, requires zero skips and at least 694 actual
passes, and checks exact discovered test IDs using the existing merge contract.
Artifacts are attempt-specific and retained for 14 days. Trigger only when the
experiment workflow changes on research/cloud branches or via explicit dispatch
where GitHub exposes it; ordinary source changes do not repeat the experiment.
Do not use self-hosted or larger paid runners. Compare actual Windows shard and
merge overhead against the same-head comprehensive rehearsal; do not equate
pure regression wall time to full patch recovery qualification. A passing
experiment is not authorization to substitute sharded execution inside the
existing patch-check receipt contract. Preserve main and physical M1 gates.

## Windows profiling result and platform-specific catalog

Opt-in Windows parallel run 45901611083 at 3ca0c35, attempt 1, passed all
699/699 tests, zero skips, 69 modules, exact coverage and independent merge.
Plan SHA-256 b794c2faf6381a65349ea0f62f8a713e303cabb00ae392e7beebc6d892cdd405.
Shard test wall durations: 10.822307, 16.367226, 12.214634, 9.290328 s;
sum 48.694495 s; workflow 62 s; summed five job durations 145 s. The prior
serial rehearsal at 33f8ab4 passed 699/699 in 67.824 s, complete workflow 98 s;
phase durations discovery 1.519791, recovery 69.397399, verification 0.194522 s.
The parallel pilot is a different contract and separate checkout; it does not
replace serial patch recovery. Same-head comprehensive run 45901619301 passed
as well. These individual timings are not a controlled speedup claim.

Retain the observed Windows module costs in cloud/windows_test_module_costs.json.
The existing planner selects one fixed catalog by platform and uses weights only
for a matching Python minor, with count fallback if absent/inapplicable.
The separate Windows pilot remains opt-in; do not automatically duplicate
routine comprehensive CI merely to refresh a profile.

Before publishing any planner/shard/merge receipt, recheck observed checkout
identity. A disposable fixture leaving an untracked change during a shard must
fail instead of yielding a passing aggregate. This boundary check does not
detect transient changes reverted between observations or authenticate runners.
No physical M1 promotion or runtime dependency is introduced.
