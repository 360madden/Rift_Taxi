"""CI gate regressions use synthetic GitHub metadata, never live game or network."""
from copy import deepcopy
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
        self.assertEqual(r["sumJobElapsedSeconds"], 99)
        self.assertEqual(r["longestJob"], "Python 3.14 / windows-latest")
        self.assertFalse(r["physicalQualification"])
        self.assertFalse(r["testCountsIndependentlyVerified"])

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
        step=next(s for s in row["steps"] if s["name"]=="Run installed constrained journey and audit")
        # A successful job summary cannot hide a skipped mandatory
        # installed-package acceptance test.
        step["conclusion"]="skipped"
        with self.assertRaises(CIGateError):
            verify(run,jobs,**PIN)

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
