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
