"""CI admission regressions use synthetic metadata and the checked-in workflow.

The workflow inventory check protects against drift that fixtures built from
REQUIRED cannot discover. Tests read source only, use the stdlib, and neither
contact GitHub nor access a game process; no metadata is physical evidence.
"""
from copy import deepcopy
from pathlib import Path
import re
import unittest

from scripts.ci_checkpoint import CIGateError, REPO, REQUIRED, WORKFLOW, decode, verify

HEAD = "a"*40
BRANCH = "research/fixture"
PIN = dict(head=HEAD, branch=BRANCH, run_id=123, attempt=1)


def stamp(second):
    return f"2026-11-27T04:00:{second:02d}Z"


def fixture():
    run = {"repository": {"full_name": REPO}, "id": 123, "run_attempt": 1,
           "head_sha": HEAD, "head_branch": BRANCH, "path": WORKFLOW,
           "name": "Offline regression", "event": "pull_request",
           "status": "completed", "conclusion": "success",
           "created_at": stamp(0), "run_started_at": stamp(1), "updated_at": stamp(59)}
    jobs = []
    for i, (name, labels) in enumerate(REQUIRED.items()):
        jobs.append({"name": name, "id": 1000+i, "run_id": 123, "run_attempt": 1,
                     "head_sha": HEAD, "status": "completed", "conclusion": "success",
                     "started_at": stamp(2), "completed_at": stamp(40-i*5),
                     "steps": [{"name": label, "number": n+1, "status": "completed",
                                "conclusion": "success", "started_at": stamp(3+n),
                                "completed_at": stamp(4+n)} for n,label in enumerate(labels)]})
    return run, {"total_count": len(jobs), "jobs": jobs}


class CICheckpointTests(unittest.TestCase):
    def test_complete_attempt_has_timing_not_physical_authority(self):
        run, jobs = fixture()
        r = verify(run, jobs, **PIN)
        self.assertEqual(r["status"], "passed")
        self.assertEqual(r["elapsedFromRunCreationSeconds"], 59)
        self.assertEqual(r["longestJobSeconds"], 38)
        self.assertEqual(r["sumJobElapsedSeconds"], 122)
        self.assertEqual(r["longestJob"], "Python 3.14 / windows-latest")
        self.assertFalse(r["physicalQualification"])
        self.assertFalse(r["testCountsIndependentlyVerified"])

    def test_checked_in_workflow_jobs_match_admission_contract(self):
        """An added workflow job must not escape a REQUIRED-derived fixture.

        This deliberately reads the workflow's current simple name/matrix
        declarations, not arbitrary YAML. A more complex matrix needs an
        explicit review of the verifier contract instead of silent inference.
        """
        source = (Path(__file__).resolve().parents[1] / WORKFLOW).read_text(
            encoding="utf-8")
        job_section = source.split("\njobs:\n", 1)[1]
        job_ids = re.findall(r"^  ([A-Za-z0-9_-]+):$", job_section, re.MULTILINE)
        names = re.findall(r"^    name: (.+)$", source, re.MULTILINE)
        self.assertEqual(len(job_ids), len(names), "each job needs an explicit name")
        os_rows = re.findall(r"^        os: \[([^\]]+)\]$", source, re.MULTILINE)
        self.assertEqual(len(os_rows), 1, "review changed workflow matrix")
        operating_systems = [item.strip() for item in os_rows[0].split(",")]
        expanded = []
        for name in names:
            if "${{ matrix.os }}" in name:
                expanded.extend(name.replace("${{ matrix.os }}", os_name)
                                for os_name in operating_systems)
            else:
                expanded.append(name)
        # Both uniqueness and exact equality matter: silently accepting a fifth
        # job or forgetting a new required job would revive the four-job bug.
        self.assertEqual(len(expanded), len(set(expanded)))
        self.assertEqual(set(expanded), set(REQUIRED))
        self.assertIn("Windows / installed desktop smoke", expanded)

    def test_desktop_job_and_each_stage_are_mandatory(self):
        """A green workflow/job summary cannot replace executed desktop stages."""
        run, jobs = fixture()
        desktop_name = "Windows / installed desktop smoke"
        # Spell out these independently of REQUIRED so deleting a stage from
        # the verifier does not also delete it from every regression fixture.
        desktop_steps = (
            "Build wheel and install into a fresh environment",
            "Exercise installed launcher and both desktop viewers",
            "Retain synthetic desktop receipts",
        )
        self.assertEqual(REQUIRED[desktop_name], desktop_steps)
        missing_job = deepcopy(jobs)
        missing_job["jobs"] = [row for row in missing_job["jobs"]
                               if row["name"] != desktop_name]
        missing_job["total_count"] = len(missing_job["jobs"])
        with self.assertRaises(CIGateError):
            verify(run, missing_job, **PIN)
        for label in desktop_steps:
            for mutation in ("missing", "skipped", "failure", "duplicate"):
                bad = deepcopy(jobs)
                row = next(row for row in bad["jobs"]
                           if row["name"] == desktop_name)
                step = next(step for step in row["steps"]
                            if step["name"] == label)
                if mutation == "missing":
                    row["steps"].remove(step)
                elif mutation == "duplicate":
                    row["steps"].append({**step, "number": 90})
                else:
                    step["conclusion"] = mutation
                with self.subTest(stage=label, mutation=mutation):
                    with self.assertRaises(CIGateError):
                        verify(run, bad, **PIN)

    def test_stale_wrong_branch_or_attempt_refused(self):
        run, jobs = fixture()
        for key,value in (("head", "b"*40), ("branch","main"), ("attempt",2),
                          ("run_id",124), ("attempt",True)):
            with self.subTest(key=key),self.assertRaises(CIGateError):
                verify(run,jobs,**{**PIN,key:value})

    def test_run_identity_and_failure_status(self):
        run,jobs = fixture()
        for key,value in (("status","in_progress"),("conclusion","failure"),
                          ("event","push"),("path","other.yml"),("id",123.0),
                          ("repository",{"full_name":"other/repo"})):
            with self.subTest(key=key),self.assertRaises(CIGateError):
                verify({**run,key:value},jobs,**PIN)

    def test_missing_duplicate_or_mixed_attempt_jobs(self):
        run,jobs = fixture()
        for mutation in ("missing","duplicate","attempt","id","head","count","failure"):
            bad=deepcopy(jobs)
            rows=bad["jobs"]
            if mutation=="missing": rows.pop()
            elif mutation=="duplicate": rows[0]=deepcopy(rows[1])
            elif mutation=="attempt": rows[0]["run_attempt"]=2
            elif mutation=="id": rows[0]["id"]=rows[1]["id"]
            elif mutation=="head": rows[0]["head_sha"]="b"*40
            elif mutation=="count": bad["total_count"]=3.
            else: rows[0]["conclusion"]="failure"
            with self.subTest(mutation=mutation),self.assertRaises(CIGateError):
                verify(run,bad,**PIN)

    def test_missing_skipped_duplicate_and_failed_steps(self):
        run,jobs=fixture()
        for mutation in ("missing","skipped","duplicate","failure"):
            bad=deepcopy(jobs)
            steps=bad["jobs"][0]["steps"]
            if mutation=="missing": steps.pop()
            elif mutation=="duplicate": steps.append({**steps[0],"number":90})
            else: steps[0]["conclusion"]=mutation
            with self.subTest(mutation=mutation),self.assertRaises(CIGateError):
                verify(run,bad,**PIN)

    def test_installed_constrained_acceptance_is_required(self):
        run,jobs=fixture()
        row=next(r for r in jobs["jobs"] if "wheel" in r["name"])
        # Neither installed product check can be replaced by a green job summary.
        for name in ("Run installed constrained journey and audit", "Run installed local Taxi prototype"):
            bad=deepcopy(jobs)
            row=next(r for r in bad["jobs"] if "wheel" in r["name"])
            step=next(s for s in row["steps"] if s["name"]==name)
            step["conclusion"]="skipped"
            with self.subTest(name=name),self.assertRaises(CIGateError):
                verify(run,bad,**PIN)

    def test_conditional_skipped_nonrequired_step_allowed(self):
        run,jobs=fixture()
        jobs["jobs"][0]["steps"].append({"name":"Other platform", "number":90,
                                         "status":"completed","conclusion":"skipped"})
        self.assertEqual(verify(run,jobs,**PIN)["status"],"passed")

    def test_reversed_or_invalid_time_refused(self):
        run,jobs=fixture()
        for field,value in (("updated_at",stamp(0)),("run_started_at","bad")):
            with self.assertRaises(CIGateError):
                verify({**run,field:value},jobs,**PIN)
        jobs["jobs"][0]["steps"][0]["completed_at"]=stamp(58)
        with self.assertRaises(CIGateError):
            verify(run,jobs,**PIN)

    def test_ambiguous_json_refused(self):
        for raw in (b'{"id":1,"id":2}',b'{"id":NaN}',b'\xff'):
            with self.assertRaises(CIGateError):
                decode(raw)
