"""Offline Windows rehearsal inventory contract; no actual patch or game access."""
from copy import deepcopy
import unittest

from scripts.cloud_test_runner import make_plan, digest
from scripts.ci_patch_recovery_rehearsal import admit_inventory, require_exact_result


HEAD = "a"*40
IDENTITY = {"commit": HEAD, "cleanCheckout": True, "platform": "Windows",
            "python": "3.14.10"}
IDS = ["test_a.C.test_one", "test_a.C.test_two", "test_b.C.test_one"]


def rehash(plan):
    plan["planSHA256"] = digest({k: v for k, v in plan.items() if k != "planSHA256"})
    return plan


class RehearsalInventoryTests(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan(IDS, [], 1, IDENTITY)

    def test_exact_complete_inventory_and_checkout(self):
        info = admit_inventory(self.plan, 3)
        self.assertEqual(info, {"testCount": 3, "moduleCount": 2,
                                "planSHA256": self.plan["planSHA256"], "commit": HEAD})
        result = {"test_count": 3, "git_head": HEAD}
        require_exact_result(info, result, result)

    def test_reduced_discovery_and_platform_skip_refused(self):
        with self.assertRaises(ValueError):
            admit_inventory(self.plan, 4)
        with self.assertRaises(ValueError):
            admit_inventory(make_plan(IDS, IDS[:1], 1, IDENTITY), 3)

    def test_wrong_or_dirty_checkout_refused(self):
        for identity in ({**IDENTITY, "cleanCheckout": False},
                         {**IDENTITY, "platform": "Linux"},
                         {**IDENTITY, "commit": "not-a-sha"}):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                admit_inventory(make_plan(IDS, [], 1, identity), 3)

    def test_digest_and_duplicate_or_missing_module_ids_refused(self):
        bad = deepcopy(self.plan)
        bad["testCount"] = 4
        with self.assertRaises(ValueError):
            admit_inventory(bad, 3)
        for ids in ([IDS[0]], [IDS[0], IDS[1], IDS[2]], [IDS[0], IDS[0]]):
            bad = deepcopy(self.plan)
            bad["assignment"][0]["moduleTestIds"]["test_a"] = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                admit_inventory(rehash(bad), 3)

    def test_exact_execution_rejects_reduced_increased_or_changed_head(self):
        info = admit_inventory(self.plan, 3)
        good = {"test_count": 3, "git_head": HEAD}
        for bad in ({"test_count": 2, "git_head": HEAD},
                    {"test_count": 4, "git_head": HEAD},
                    {"test_count": 3., "git_head": HEAD},
                    {"test_count": 3, "git_head": "b"*40}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    require_exact_result(info, bad, good)
                with self.assertRaises(ValueError):
                    require_exact_result(info, good, bad)
