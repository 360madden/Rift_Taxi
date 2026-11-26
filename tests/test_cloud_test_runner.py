"""Deterministic development-only shard planner and receipt tests."""
from copy import deepcopy
import io
import unittest

from scripts.cloud_test_runner import (
    CloudValidationError, make_plan, merge, execute_shard,
)

IDENTITY={"commit":"a"*40,"cleanCheckout":True,"platform":"Linux","python":"3.14.10"}


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.ids=["test_a.C.test_"+str(i) for i in range(5)]
        self.ids+=["test_b.C.test_"+str(i) for i in range(3)]
        self.ids+=["test_c.C.test_one","test_d.C.test_one"]
        self.skips=[self.ids[0]]
        self.plan=make_plan(self.ids,self.skips,3,IDENTITY)

    def receipts(self):
        return [{"schema":"taxi.cloud-test-shard/1","identity":IDENTITY,
                 "planSHA256":self.plan["planSHA256"],"index":a["index"],
                 "status":"passed","startedTestIds":a["testIds"],
                 "skippedTestIds":a["declaredSkipIds"],"testsRun":len(a["testIds"]),
                 "failures":0,"errors":0,"unexpectedSuccesses":0,"expectedFailures":0,
                 "elapsedSeconds":1.5,"physicalQualification":False}
                for a in self.plan["assignment"]]

    def test_order_independent_exact_coverage(self):
        self.assertEqual(self.plan,make_plan(list(reversed(self.ids)),self.skips,3,IDENTITY))
        all_ids=[t for a in self.plan["assignment"] for t in a["testIds"]]
        self.assertEqual(sorted(all_ids),sorted(self.ids))
        modules=[m for a in self.plan["assignment"] for m in a["modules"]]
        self.assertEqual(len(modules),len(set(modules)))
        self.assertEqual(sorted(modules),["test_a","test_b","test_c","test_d"])

    def test_invalid_plan_refused(self):
        for ids,skips,n in [(self.ids+self.ids,self.skips,3),(self.ids,["other"],3),
                           (self.ids,self.skips,True),(self.ids,self.skips,8),([],[],1)]:
            with self.subTest(n=n),self.assertRaises(CloudValidationError):
                make_plan(ids,skips,n,IDENTITY)

    def test_merge_exact_counts_and_explicit_skips(self):
        r=merge(self.plan,list(reversed(self.receipts())))
        self.assertEqual(r["testsDiscovered"],10)
        self.assertEqual(r["testsPassed"],9)
        self.assertEqual(r["testsSkipped"],1)
        self.assertEqual(r["sumShardSeconds"],4.5)
        self.assertEqual(r["maxShardSeconds"],1.5)
        self.assertFalse(r["physicalQualification"])

    def test_missing_duplicate_and_mismatched_receipts_refused(self):
        base=self.receipts()
        for receipts in (base[:-1],[base[0],base[0],base[2]],base+[base[0]]):
            with self.assertRaises(CloudValidationError):
                merge(self.plan,receipts)
        for key,value in (("planSHA256","b"*64),("identity",{**IDENTITY,"commit":"b"*40}),
                          ("index",True),("status","failed"),("testsRun",1.0),
                          ("startedTestIds",[]),("skippedTestIds",["invented"]),
                          ("errors",1),("failures",False),("expectedFailures",1),
                          ("elapsedSeconds",float("nan")),("physicalQualification",True)):
            r=deepcopy(base);r[0][key]=value
            with self.subTest(key=key),self.assertRaises(CloudValidationError):
                merge(self.plan,r)

    def test_execution_records_pass_skip_and_actual_failure(self):
        class Fixture(unittest.TestCase):
            def test_ok(self): pass
            @unittest.skip("declared fixture skip")
            def test_skip(self): pass
            def test_bad(self): self.fail("intentional fixture failure")
        tests=[Fixture("test_ok"),Fixture("test_skip")]
        plan=make_plan([t.id() for t in tests],[tests[1].id()],1,IDENTITY)
        r=execute_shard(plan,tests,0,stream=io.StringIO())
        self.assertEqual(r["status"],"passed")
        self.assertEqual(merge(plan,[r])["testsSkipped"],1)
        tests=[Fixture("test_bad")]
        plan=make_plan([t.id() for t in tests],[],1,IDENTITY)
        r=execute_shard(plan,tests,0,stream=io.StringIO())
        self.assertEqual(r["status"],"failed")
        with self.assertRaises(CloudValidationError):
            merge(plan,[r])

    def test_dynamic_skip_cannot_silently_reduce_coverage(self):
        class Fixture(unittest.TestCase):
            def test_unplanned(self): self.skipTest("unexpected")
        tests=[Fixture("test_unplanned")]
        plan=make_plan([t.id() for t in tests],[],1,IDENTITY)
        self.assertEqual(execute_shard(plan,tests,0,stream=io.StringIO())["status"],"failed")
