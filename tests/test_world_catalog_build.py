"""Catalog builder integration and refusal tests using invented packages."""
from copy import deepcopy
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.world_candidate_review import IDENTITY_FIELDS, content_id
from rift_taxi.world_review_package import create_package
from rift_taxi.world_catalog_build import PLAN_SCHEMA, build_catalog, main
from rift_taxi.world_route_catalog import select_route
from test_world_candidate_review import fixture


class CatalogBuildTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.plan = self.root / "plan.json"
        self.out = self.root / "catalog.json"
        self.rows = [self.package("alpha", fixture())]

    def package(self, name, doc):
        # Recalculate the invented upstream candidate identity after deliberate
        # test edits. Never treat these fixtures as live RIFT evidence.
        ident = {k: doc[k] for k in IDENTITY_FIELDS}
        ident["plannerResult"] = doc["plannerResult"]
        doc["candidateId"] = content_id(ident)
        raw = json.dumps(doc, allow_nan=False).encode()
        src = self.root / "source.json"
        src.write_bytes(raw)
        package = create_package(src, expected_sha256=hashlib.sha256(raw).hexdigest(),
                                 source_commit="c"*40)
        filename = name + ".json"
        (self.root / filename).write_text(json.dumps(package), encoding="utf-8")
        return {"routeId": name, "destinationId": "destination",
                "packageFile": filename, "packageId": package["packageId"]}

    def plan_pin(self):
        raw = json.dumps({"schema": PLAN_SCHEMA, "entries": self.rows}).encode()
        self.plan.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def build(self):
        return build_catalog(self.plan, expected_plan_sha256=self.plan_pin())

    def test_deterministic_catalog_selects_verified_package(self):
        doc = fixture()
        doc["createdAtUtc"] = "distinct fixture bytes"
        self.rows.append(self.package("zeta", doc))
        encoded = self.build()
        self.rows.reverse()
        self.assertEqual(encoded, self.build())
        catalog = json.loads(encoded)
        row = catalog["entries"][0]
        self.assertEqual(row["routeId"], "alpha")
        self.assertEqual(row["destinationXYZ"], [4, 0, 0])
        self.assertEqual(row["sourceWorld"], "synthetic")
        self.out.write_bytes(encoded)
        report = select_route(
            self.out, catalog_sha256=hashlib.sha256(encoded).hexdigest(),
            destination_id=row["destinationId"], source_world=row["sourceWorld"],
            frame_sha256=row["frameSHA256"], patch_id=row["patchId"],
            start_xyz=[0, 0, 0], max_start_xz=.1, max_start_y=.1,
            max_snap_xz=.1, max_snap_y=.1)
        self.assertEqual(report["eligibleCount"], 2)
        self.assertEqual(report["selected"]["routeId"], "alpha")
        self.assertIs(report["physicalQualification"], False)
        self.assertIs(report["productionInputAuthorized"], False)

    def test_exact_plan_pin_and_package_pin(self):
        self.plan_pin()
        with self.assertRaisesRegex(TraceError, "plan SHA mismatch"):
            build_catalog(self.plan, expected_plan_sha256="0"*64)
        self.rows[0]["packageId"] = "0"*64
        with self.assertRaisesRegex(TraceError, "external package pin mismatch"):
            self.build()

    def test_corrupt_package_invalidates_entire_inventory(self):
        doc = fixture()
        doc["createdAtUtc"] = "corrupt alternate"
        self.rows.append(self.package("zeta", doc))
        (self.root / "zeta.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(TraceError):
            self.build()
        self.assertFalse(self.out.exists())

    def test_duplicate_identity_and_unsafe_names_refused(self):
        original = deepcopy(self.rows)
        self.rows.append(deepcopy(self.rows[0]))
        with self.assertRaisesRegex(TraceError, "duplicate"):
            self.build()
        for filename in ("../alpha.json", "A.json", "con.json", "C:alpha.json"):
            self.rows = deepcopy(original)
            self.rows[0]["packageFile"] = filename
            with self.subTest(filename=filename), self.assertRaisesRegex(TraceError, "filename"):
                self.build()

    def test_label_cannot_conflate_different_goal_in_same_scope(self):
        doc = fixture()
        for target in (doc["query"], doc["plannerResult"]):
            target["requestedGoalXYZ"] = [4, 1, 0]
        self.rows.append(self.package("other-goal", doc))
        with self.assertRaisesRegex(TraceError, "contradictory destination"):
            self.build()

    def test_redundant_caller_scope_cannot_override_verified_bytes(self):
        self.rows[0]["sourceWorld"] = "invented"
        with self.assertRaisesRegex(TraceError, "plan entry"):
            self.build()

    def test_cli_pin_and_exclusive_local_output(self):
        pin = self.plan_pin()
        args = [str(self.plan), "--expected-plan-sha256", pin, "--out"]
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main(args + [str(self.out)]), 0)
        receipt = json.loads(buf.getvalue())
        original = self.out.read_bytes()
        self.assertEqual(receipt["catalogSHA256"], hashlib.sha256(original).hexdigest())
        self.assertIs(receipt["physicalQualification"], False)
        self.assertIs(receipt["gameInputSent"], False)
        self.assertEqual(receipt["entryCount"], 1)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as err:
            main(args + [str(self.out)])
        self.assertEqual(err.exception.code, 2)
        self.assertEqual(self.out.read_bytes(), original)
        elsewhere = self.root / "other"
        elsewhere.mkdir()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as err:
            main(args + [str(elsewhere / "catalog.json")])
        self.assertEqual(err.exception.code, 2)
        self.assertFalse((elsewhere / "catalog.json").exists())
