"""Invented source packages test review topology; no real terrain or input."""
import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.world_candidate_review import content_id, IDENTITY_FIELDS
from rift_taxi.world_review_package import create_package
from rift_taxi.world_route_catalog import SCHEMA
from rift_taxi.world_review_graph import load_graph, list_endpoints, list_destinations, plan_review_chain, plan_named_destination, main
from test_world_candidate_review import fixture


class ReviewGraphTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.catalog = self.root / "catalog.json"
        self.rows = []
        self.scope = {"source_world": "synthetic",
                      "frame_sha256": content_id(fixture()["coordinates"]),
                      "patch_id": "a"*64, "build_id": "b"*64}

    def add(self, name, points, *, requested_goal=None, build=None, authority=None):
        """Construct a complete consistent export and package from invented XYZ."""
        doc = fixture()
        start, end = list(points[0]), list(points[-1])
        ends = {"requestedStartXYZ": start, "snappedStartXYZ": start,
                "requestedGoalXYZ": requested_goal if requested_goal is not None else end,
                "snappedGoalXYZ": end}
        doc["query"] = ends
        doc["points"] = [{"id": str(i), "xyz": list(p), "flags": i+1}
                         for i, p in enumerate(points)]
        doc["plannerResult"].update(ends)
        doc["plannerResult"]["waypoints"] = [{"pos": p["xyz"], "flags": p["flags"]}
                                              for p in doc["points"]]
        if build is not None:
            doc["planner"]["buildId"] = build
            doc["plannerResult"]["cacheKey"] = build
        if authority is not None:
            doc["world"]["authority"] = authority
        identity = {k: doc[k] for k in IDENTITY_FIELDS}
        identity["plannerResult"] = doc["plannerResult"]
        doc["candidateId"] = content_id(identity)
        raw = json.dumps(doc).encode()
        src = self.root / "source.json"
        src.write_bytes(raw)
        pkg = create_package(src, expected_sha256=hashlib.sha256(raw).hexdigest(),
                             source_commit="c"*40)
        filename = name + ".json"
        (self.root / filename).write_text(json.dumps(pkg), encoding="utf-8")
        self.rows.append({"routeId": name, "destinationId": name,
                          "packageFile": filename, "packageId": pkg["packageId"],
                          "sourceWorld": doc["world"]["sourceWorld"],
                          "frameSHA256": content_id(doc["coordinates"]),
                          "patchId": doc["patchId"],
                          "destinationXYZ": ends["requestedGoalXYZ"]})

    def pin(self):
        raw = json.dumps({"schema": SCHEMA, "entries": self.rows}).encode()
        self.catalog.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def graph(self, **kw):
        return load_graph(self.catalog, **{**self.scope, "catalog_sha256": self.pin(), **kw})

    def plan(self, graph, start=(0, 0, 0), goal=(8, 0, 0), **kw):
        return plan_review_chain(graph, start_xyz=list(start), goal_xyz=list(goal), **kw)

    def test_shortest_chain_preserves_segments_and_unverified_junction(self):
        self.add("first", [(0,0,0), (4,0,0)])
        self.add("second", [(4,0,0), (8,0,0)])
        self.add("detour", [(0,0,0), (4,0,4), (8,0,0)])
        graph = self.graph()
        result = self.plan(graph)
        self.assertEqual(result["status"], "review-chain-found")
        self.assertEqual([e["routeId"] for e in result["segments"]], ["first", "second"])
        self.assertEqual(result["pathLength3D"], 8.)
        self.assertEqual(result["segments"][1]["points"][0]["flags"], 1)
        self.assertEqual(result["segments"][0]["packageId"], self.rows[0]["packageId"])
        self.assertEqual(result["junctions"][0]["xyz"], [4,0,0])
        self.assertTrue(result["junctions"][0]["exactSourceXYZMatch"])
        self.assertFalse(result["junctions"][0]["traversalVerified"])
        for flag in ("physicalQualification", "productionInputAuthorized", "gameInputSent",
                     "transformQualified", "junctionTraversalVerified", "endpointConnectorsVerified"):
            self.assertIs(result[flag], False)
        self.assertEqual([e["routeId"] for e in self.plan(graph, blocked_routes=["first"])["segments"]],
                         ["detour"])
        self.assertEqual(self.plan(graph, blocked_routes=["first", "detour"])["status"],
                         "no-review-chain")

    def test_exact_endpoints_only_no_reverse_or_near_join(self):
        self.add("first", [(0,0,0), (2,0,0), (4,0,0)])
        self.add("second", [(4.0001,0,0), (8,0,0)])
        graph = self.graph()
        self.assertEqual(self.plan(graph)["status"], "no-review-chain")
        self.assertEqual(self.plan(graph, start=(2,0,0))["status"], "unknown-endpoint")
        self.assertEqual(self.plan(graph, start=(4,0,0), goal=(0,0,0))["status"], "no-review-chain")
        self.assertEqual(self.plan(graph, goal=(0,0,0))["status"], "same-review-endpoint")
        self.assertEqual(len(list_endpoints(graph)), 4)

    def test_snapped_not_requested_coordinates_define_graph(self):
        self.add("snapped", [(0,0,0), (4,0,0)], requested_goal=[4,1,0])
        graph = self.graph()
        self.assertEqual(self.plan(graph, goal=(4,1,0))["status"], "unknown-endpoint")
        result = self.plan(graph, goal=(4,0,0))
        self.assertEqual(result["status"], "review-chain-found")
        self.assertEqual(result["segments"][0]["endpointOffsets"]["goal"]["verticalY"], 1.)
        self.assertFalse(result["endpointConnectorsVerified"])

    def test_different_build_cannot_join_and_corrupt_package_refused(self):
        self.add("first", [(0,0,0), (4,0,0)])
        self.add("second", [(4,0,0), (8,0,0)], build="d"*64)
        graph = self.graph()
        self.assertEqual(graph["excluded"], [{"routeId":"second","reason":"different-planner-build"}])
        self.assertEqual(self.plan(graph)["status"], "unknown-endpoint")
        (self.root / "second.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(TraceError):
            self.graph()

    def test_scope_conflict_and_catalog_pin_refused(self):
        self.add("first", [(0,0,0), (4,0,0)])
        self.add("second", [(4,0,0), (8,0,0)], authority="other")
        with self.assertRaisesRegex(TraceError, "conflicting source world"):
            self.graph()
        with self.assertRaisesRegex(TraceError, "catalog SHA mismatch"):
            self.graph(catalog_sha256="0"*64)

    def test_cli_and_stable_ties(self):
        self.add("zeta", [(0,0,0), (2,0,1), (4,0,0)])
        self.add("alpha", [(0,0,0), (2,0,-1), (4,0,0)])
        self.rows.reverse()
        graph = self.graph()
        self.assertEqual(self.plan(graph, goal=(4,0,0))["segments"][0]["routeId"], "alpha")
        with self.assertRaises(TraceError):
            self.plan(graph, blocked_routes=["missing"])
        args = [str(self.catalog), "--catalog-sha256", self.pin()]
        for key, value in self.scope.items():
            args += ["--" + key.replace("_", "-"), value]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args + ["endpoints"]), 0)
        self.assertEqual(len(json.loads(output.getvalue())["endpoints"]), 2)
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args + ["plan", "--start-xyz","0","0","0",
                                          "--goal-xyz","4","0","0"]), 0)
        self.assertEqual(json.loads(output.getvalue())["segments"][0]["routeId"], "alpha")

    def test_named_destination_resolves_exact_requested_goal_across_chain(self):
        self.add("first", [(0,0,0), (4,0,0)])
        self.add("bank", [(4,0,0), (8,0,0)])
        self.add("alternate", [(0,0,0), (4,0,4), (8,0,0)])
        graph = self.graph()
        self.assertEqual([d["destinationId"] for d in list_destinations(graph)],
                         ["alternate", "bank", "first"])
        result = plan_named_destination(graph, start_xyz=[0,0,0], destination_id="bank")
        self.assertEqual(result["status"], "review-chain-found")
        self.assertEqual(result["goalXYZ"], [8,0,0])
        self.assertEqual(result["destinationBinding"]["exactGoalRoutes"], ["bank"])
        self.assertEqual([e["routeId"] for e in result["segments"]], ["first", "bank"])
        # Blocking a route changes the search, not the coordinate identity.
        alt = plan_named_destination(graph, start_xyz=[0,0,0], destination_id="bank",
                                     blocked_routes=["bank"])
        self.assertEqual([e["routeId"] for e in alt["segments"]], ["alternate"])
        self.assertFalse(alt["physicalQualification"])

    def test_named_destination_refuses_snap_only_even_if_requested_xyz_is_other_endpoint(self):
        self.add("bank", [(0,0,0), (4,0,0)], requested_goal=[4,1,0])
        self.add("other", [(0,0,0), (4,1,0)])
        graph = self.graph()
        bank = list_destinations(graph)[0]
        self.assertFalse(bank["exactGoalBound"])
        self.assertEqual(bank["snappedAlternatives"][0]["endpointOffset"]["verticalY"], 1.)
        result = plan_named_destination(graph, start_xyz=[0,0,0], destination_id="bank")
        self.assertEqual(result["status"], "unbound-destination")
        self.assertEqual(result["segments"], [])
        self.assertEqual(result["goalXYZ"], [4,1,0])
        self.assertFalse(result["endpointConnectorsVerified"])
        self.assertEqual(plan_named_destination(graph, start_xyz=[0,0,0],
                         destination_id="missing")["status"], "unknown-destination")
        with self.assertRaises(TraceError):
            plan_named_destination(graph, start_xyz=[0,0,0], destination_id="missing",
                                   blocked_routes=["unknown-route"])

    def test_grouped_destination_keeps_exact_binding_and_snap_alternatives(self):
        self.add("exact", [(0,0,0), (8,0,0)])
        self.add("nearby", [(0,0,0), (8,1,0)], requested_goal=[8,0,0])
        for row in self.rows:
            row["destinationId"] = "bank"
        graph = self.graph()
        entries = list_destinations(graph)
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]["exactGoalBound"])
        self.assertEqual(entries[0]["exactGoalRoutes"], ["exact"])
        self.assertEqual(entries[0]["snappedAlternatives"][0]["routeId"], "nearby")
        result = plan_named_destination(graph, start_xyz=[0,0,0], destination_id="bank",
                                        blocked_routes=["exact"])
        self.assertEqual(result["status"], "no-review-chain")
        self.assertEqual(result["segments"], [])

    def test_named_destination_cli(self):
        self.add("bank", [(0,0,0), (8,0,0)])
        args = [str(self.catalog), "--catalog-sha256", self.pin()]
        for key, value in self.scope.items():
            args += ["--" + key.replace("_", "-"), value]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args + ["destinations"]), 0)
        self.assertEqual(json.loads(output.getvalue())["destinations"][0]["destinationId"], "bank")
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args + ["plan", "--start-xyz","0","0","0",
                                          "--destination","bank"]), 0)
        self.assertEqual(json.loads(output.getvalue())["goalXYZ"], [8,0,0])
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args + ["plan", "--start-xyz","0","0","0",
                                          "--destination","missing"]), 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "unknown-destination")
