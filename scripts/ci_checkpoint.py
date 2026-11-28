"""Offline CI checkpoint admission and latency report for Rift_Taxi.

Development only. Accept saved GitHub REST run and attempt-specific job JSON,
or fetch those two public-repository metadata objects through an authenticated
gh CLI. Never starts a run, edits workflows, accesses credentials directly,
or grants physical game qualification. Explicit expected head and attempt
prevent an older successful PR run from approving a newer commit. The stdlib-only
verifier reads metadata, prints a receipt and optionally creates one new output;
it never imports game readers or controls input.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

REPO = "360madden/Rift_Taxi"
WORKFLOW = ".github/workflows/offline-regression.yml"
MAX_BYTES = 2 * 1024 * 1024
# Keep this explicit admission contract aligned with the checked-in workflow.
# An added job must be reviewed here; accepting arbitrary extra green summaries
# would omit its required stages and could silently weaken checkpoint evidence.
REQUIRED = {
    "Python 3.14 / windows-latest": (
        "Rehearse patch recovery with synthetic manifests",
        "Upload synthetic recovery rehearsal",
        "Archive V4 synthetic comparison",
        "Upload V4 comparison",
        "Archive observed V4 terminal queue diagnostic",
        "Upload V4 terminal observations",
    ),
    "Python 3.14 / ubuntu-latest": (
        "Run full offline regression suite",
        "Archive V4 synthetic comparison",
        "Upload V4 comparison",
        "Archive observed V4 terminal queue diagnostic",
        "Upload V4 terminal observations",
    ),
    "Python 3.11 / wheel and offline tests": (
        "Run full minimum-version regression suite",
        "Build and install wheel",
        "Check installed research modules and CLI help",
        "Run installed offline journey demonstration",
        "Run installed experimental journey modes",
        "Run installed constrained journey and audit",
        "Run installed local Taxi prototype",
        "Upload installed synthetic journey",
    ),
    "Windows / installed desktop smoke": (
        "Build wheel and install into a fresh environment",
        "Exercise installed launcher and both desktop viewers",
        "Retain synthetic desktop receipts",
    ),
}
SHA = re.compile(r"[0-9a-f]{40}\Z")
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


class CIGateError(ValueError):
    """Malformed, incomplete, stale, or unsuccessful CI evidence."""


def require(ok, reason):
    if not ok:
        raise CIGateError(reason)


def positive(value):
    return type(value) is int and 0 < value <= 2**63-1


def timestamp(value):
    require(isinstance(value, str) and STAMP.fullmatch(value), "invalid UTC timestamp")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise CIGateError("invalid UTC timestamp") from exc


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def decode(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BYTES, "metadata size outside bound")
    def reject(_):
        raise CIGateError("invalid JSON constant")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=reject)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CIGateError("invalid metadata JSON") from exc


def read(path):
    with Path(path).open("rb") as stream:
        return stream.read(MAX_BYTES+1)


def verify(run, jobs, *, head, branch, run_id, attempt):
    """Check all required job and step receipts for one explicit attempt.

    This verifies metadata consistency, not runner attestation or source
    behavior. A selective rerun that omits previously successful jobs is
    intentionally incomplete; do not mix attempts to manufacture a pass.
    PR head SHA identifies the proposed change, not the merge checkout SHA.
    """
    require(isinstance(head, str) and SHA.fullmatch(head), "invalid expected head")
    require(isinstance(branch, str) and 0 < len(branch) <= 200, "invalid expected branch")
    require(positive(run_id) and positive(attempt), "invalid expected run/attempt")
    require(isinstance(run, dict) and isinstance(jobs, dict), "metadata object required")
    repository = run.get("repository")
    require(isinstance(repository, dict) and repository.get("full_name") == REPO,
            "unexpected repository")
    require(positive(run.get("id")) and run["id"] == run_id
            and positive(run.get("run_attempt")) and run["run_attempt"] == attempt
            and run.get("head_sha") == head and run.get("head_branch") == branch
            and run.get("path") == WORKFLOW and run.get("name") == "Offline regression"
            and run.get("event") == "pull_request", "run identity mismatch")
    require(run.get("status") == "completed" and run.get("conclusion") == "success",
            "run has not passed")
    created = timestamp(run.get("created_at"))
    started = timestamp(run.get("run_started_at"))
    ended = timestamp(run.get("updated_at"))
    require(created <= started <= ended, "invalid run timing")
    rows = jobs.get("jobs")
    require(type(jobs.get("total_count")) is int and jobs["total_count"] == len(REQUIRED)
            and isinstance(rows, list) and len(rows) == len(REQUIRED),
            "required job inventory incomplete or changed")
    seen, ids, output = set(), set(), []
    for job in rows:
        require(isinstance(job, dict), "job metadata object")
        name = job.get("name")
        require(isinstance(name, str) and name in REQUIRED and name not in seen,
                "unknown or duplicate job")
        seen.add(name)
        job_id = job.get("id")
        require(positive(job_id) and job_id not in ids, "duplicate or invalid job ID")
        ids.add(job_id)
        require(positive(job.get("run_id")) and job["run_id"] == run_id
                and positive(job.get("run_attempt")) and job["run_attempt"] == attempt
                and job.get("head_sha") == head, "job identity mismatch")
        require(job.get("status") == "completed" and job.get("conclusion") == "success",
                "required job has not passed")
        left = timestamp(job.get("started_at"))
        right = timestamp(job.get("completed_at"))
        require(started <= left <= right <= ended, "invalid job timing")
        steps = job.get("steps")
        require(isinstance(steps, list) and 0 < len(steps) <= 100, "step inventory")
        named, numbers = {}, set()
        for step in steps:
            require(isinstance(step, dict) and isinstance(step.get("name"), str)
                    and positive(step.get("number")) and step["number"] not in numbers,
                    "malformed or duplicate step number")
            numbers.add(step["number"])
            named.setdefault(step["name"], []).append(step)
            # Existing conditional platform steps can legitimately be skipped.
            require(step.get("status") == "completed"
                    and step.get("conclusion") in ("success", "skipped"),
                    "nonpassing job step")
        required_steps = []
        for label in REQUIRED[name]:
            matches = named.get(label, [])
            require(len(matches) == 1 and matches[0]["conclusion"] == "success",
                    "required step missing, duplicated, or skipped: " + label)
            step = matches[0]
            a = timestamp(step.get("started_at"))
            b = timestamp(step.get("completed_at"))
            require(left <= a <= b <= right, "invalid required step timing")
            required_steps.append({"name": label, "seconds": (b-a).total_seconds()})
        output.append({"name": name, "jobId": job_id,
                       "elapsedSeconds": (right-left).total_seconds(),
                       "requiredSteps": required_steps})
    output.sort(key=lambda row: row["name"])
    slowest = max(output, key=lambda row: row["elapsedSeconds"])
    return {"schema": "taxi.ci-checkpoint/1", "status": "passed",
            "repository": REPO, "workflow": WORKFLOW, "headSHA": head,
            "branch": branch, "runId": run_id, "runAttempt": attempt,
            "elapsedFromRunStartSeconds": (ended-started).total_seconds(),
            "elapsedFromRunCreationSeconds": (ended-created).total_seconds(),
            "sumJobElapsedSeconds": sum(j["elapsedSeconds"] for j in output),
            "longestJob": slowest["name"], "longestJobSeconds": slowest["elapsedSeconds"],
            "jobs": output, "testCountsIndependentlyVerified": False,
            "physicalQualification": False, "productionInputAuthorized": False}


def _gh(endpoint):
    """Read exact API resources; never print or store the CLI credential."""
    try:
        result = subprocess.run(["gh", "api", endpoint], stdin=subprocess.DEVNULL,
                                capture_output=True, check=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise CIGateError("GitHub metadata request failed") from exc
    require(len(result.stdout) <= MAX_BYTES, "metadata response too large")
    return result.stdout


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--head", required=True)
    p.add_argument("--branch", required=True)
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--attempt", type=int, required=True)
    p.add_argument("--run-json", type=Path)
    p.add_argument("--jobs-json", type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    try:
        require(positive(a.run_id) and positive(a.attempt), "invalid run/attempt")
        require((a.run_json is None) == (a.jobs_json is None), "supply both saved metadata files")
        if a.out is not None:
            require(not a.out.exists(), "output already exists")
        if a.run_json is None:
            prefix = f"repos/{REPO}/actions/runs/{a.run_id}"
            raw_run = _gh(prefix)
            raw_jobs = _gh(f"{prefix}/attempts/{a.attempt}/jobs?per_page=100")
        else:
            raw_run, raw_jobs = read(a.run_json), read(a.jobs_json)
        receipt = verify(decode(raw_run), decode(raw_jobs), head=a.head, branch=a.branch,
                         run_id=a.run_id, attempt=a.attempt)
        receipt["runMetadataSHA256"] = hashlib.sha256(raw_run).hexdigest()
        receipt["jobMetadataSHA256"] = hashlib.sha256(raw_jobs).hexdigest()
        if a.out is not None:
            with a.out.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(receipt, stream, indent=2, sort_keys=True)
                stream.write("\n")
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except (CIGateError, OSError, ValueError, TypeError, KeyError) as exc:
        p.exit(2, f"CI checkpoint not admitted: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
