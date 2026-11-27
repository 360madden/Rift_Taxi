"""Product tests for local pathfinding on pinned, non-flat source paths.

Fixtures use the existing RiftWorld candidate/package format. No actual
game, network, sibling import, or geometry qualification is needed.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.local_taxi import run_local_journey, bind_edge_start, locate_start, plan_route
from rift_taxi.local_taxi_gui import preview, build_scene
from rift_taxi.world_candidate_review import IDENTITY_FIELDS, content_id
from rift_taxi.world_review_package import create_package
from rift_taxi.world_route_catalog import SCHEMA, select_route
from rift_taxi.world_review_graph import load_graph
from rift_taxi.world_route_graph import load_world_graph, plan_world_route
from test_world_candidate_review import fixture


class WorldGraphTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.catalog = self.root / "catalog.json"
        self.rows = []

    def add(self, name, points, *, patch="a", build="b", flags=None, authority=None):
        doc = fixture()
        if authority is not None:
            doc["world"]["authority"] = authority
        doc["patchId"] = patch * 64
        doc["planner"]["buildId"] = build * 64
        doc["plannerResult"]["cacheKey"] = build * 64
        ends = {"requestedStartXYZ": points[0], "snappedStartXYZ": points[0],
                "requestedGoalXYZ": points[-1], "snappedGoalXYZ": points[-1]}
        doc["query"].update(ends)
        doc["plannerResult"].update(ends)
        if flags is None:
            flags = [1] + [0] * (len(points) - 2) + [2]
        doc["points"] = [{"id": str(i), "xyz": p, "flags": f}
                         for i, (p, f) in enumerate(zip(points, flags, strict=True))]
        doc["plannerResult"]["waypoints"] = [{"pos": p, "flags": f}
                                              for p, f in zip(points, flags, strict=True)]
        identity = {key: doc[key] for key in IDENTITY_FIELDS}
        identity["plannerResult"] = doc["plannerResult"]
        doc["candidateId"] = content_id(identity)
        raw = json.dumps(doc).encode()
        src = self.root / "original.json"
        src.write_bytes(raw)
        pkg = create_package(src, expected_sha256=hashlib.sha256(raw).hexdigest(),
                             source_commit="c"*40)
        file = self.root / (name+".json")
        file.write_text(json.dumps(pkg), encoding="utf-8")
        self.rows.append({"routeId": name, "destinationId": name+"-goal",
                          "packageFile": file.name, "packageId": pkg["packageId"],
                          "sourceWorld": doc["world"]["sourceWorld"],
                          "frameSHA256": content_id(doc["coordinates"]),
                          "patchId": doc["patchId"], "destinationXYZ": points[-1]})

    def load(self, anchor):
        raw = json.dumps({"schema": SCHEMA, "entries": self.rows}).encode()
        self.catalog.write_bytes(raw)
        return load_world_graph(self.catalog, catalog_sha256=hashlib.sha256(raw).hexdigest(),
                                anchor_route=anchor)

    def test_local_search_combines_exact_scoped_endpoints_and_detours(self):
        self.add("first", [[0,0,0],[4,1,0]])
        self.add("direct", [[4,1,0],[8,2,0]])
        self.add("detour", [[4,1,0],[6,2,3],[8,2,0]])
        world = self.load("first")
        result = plan_world_route(world, start="first:0", destination="direct")
        self.assertEqual(result["status"], "route-found")
        self.assertEqual(result["edges"], ["first:edge:0","direct:edge:0"])
        self.assertEqual(result["points"][-1]["xyz"], [8.,2.,0.])
        alternate = plan_world_route(world, start_xyz=[0,0,0], destination="direct",
                                     blocked_edges=["direct:edge:0"])
        self.assertEqual(alternate["edges"], ["first:edge:0","detour:edge:0","detour:edge:1"])
        self.assertGreater(alternate["distance"], result["distance"])
        self.assertEqual(len(alternate["edgeSources"]), 3)
        self.assertEqual(alternate["classification"], "OFFLINE_REVIEW_ONLY")
        self.assertFalse(alternate["physicalQualification"])
        self.assertFalse(alternate["productionInputAuthorized"])
        with self.assertRaises(TraceError):
            run_local_journey(world.graph, "first:0", "direct")

    def test_no_reverse_no_nearby_connector_no_cross_scope(self):
        self.add("first", [[0,0,0],[4,1,0]])
        self.add("gap", [[4,1.001,0],[8,2,0]])
        self.add("patch", [[4,1,0],[8,2,0]], patch="d")
        self.add("build", [[4,1,0],[8,2,0]], build="e")
        world = self.load("first")
        self.assertEqual(set(world.routes), {"first","gap"})
        self.assertEqual(plan_world_route(world,start="first:0",destination="gap")["status"], "no-route")
        self.assertEqual(plan_world_route(world,start="first:1",destination="first")["status"],
                         "already-at-destination")
        with self.assertRaisesRegex(TraceError, "absent or ambiguous"):
            plan_world_route(world,start_xyz=[.001,0,0],destination="first")

    def test_coincident_interiors_are_not_junctions(self):
        self.add("horizontal", [[0,0,0],[4,1,0],[8,2,0]])
        self.add("vertical", [[4,1,-4],[4,1,0],[4,1,4]])
        world = self.load("horizontal")
        self.assertEqual(plan_world_route(world,start="horizontal:0",destination="vertical")["status"],
                         "no-route")
        with self.assertRaisesRegex(TraceError,"ambiguous"):
            plan_world_route(world,start_xyz=[4,1,0],destination="vertical")

    def test_unsupported_flags_refused_instead_of_invented_traversal(self):
        self.add("unsupported", [[0,0,0],[4,1,0],[8,2,0]], flags=[1,4,2])
        with self.assertRaisesRegex(TraceError,"unsupported path flags"):
            self.load("unsupported")

    def test_package_mutation_fails_and_original_files_are_preserved(self):
        self.add("first", [[0,0,0],[4,1,0]])
        package = self.root/"first.json"
        before = package.read_bytes()
        world = self.load("first")
        plan_world_route(world,start="first:0",destination="first")
        self.assertEqual(package.read_bytes(),before)
        package.write_text("{}",encoding="utf-8")
        with self.assertRaises(TraceError):
            self.load("first")

    def test_same_world_name_with_conflicting_metadata_cannot_join(self):
        self.add("first", [[0,0,0],[4,1,0]])
        self.add("second", [[4,1,0],[8,2,0]], authority="different-source")
        with self.assertRaisesRegex(TraceError, "conflicting source world metadata"):
            self.load("first")

    def test_review_graph_cannot_enter_synthetic_start_or_viewer_paths(self):
        self.add("first", [[0,0,0],[4,1,0]])
        world = self.load("first")
        graph = world.graph
        plan = plan_route(graph, world.aliases["first:0"], "first")
        self.assertEqual(plan["classification"], "OFFLINE_REVIEW_ONLY")
        # Regression: a derived start must not silently inherit the default
        # synthetic classification and bypass the model execution boundary.
        for operation in (
            lambda: bind_edge_start(graph, "first:edge:0", .5),
            lambda: locate_start(graph, [0,0,0]),
            lambda: run_local_journey(graph, world.aliases["first:0"], "first"),
            lambda: preview(graph, start=world.aliases["first:0"], destination="first"),
            lambda: build_scene(graph, plan, width=600, height=400),
        ):
            with self.subTest(operation=operation), self.assertRaisesRegex(TraceError, "synthetic"):
                operation()


    def shared_queries(self):
        """Invoke all public intake paths against the same pinned catalog."""
        raw = json.dumps({"schema": SCHEMA, "entries": self.rows}).encode()
        self.catalog.write_bytes(raw)
        pin = hashlib.sha256(raw).hexdigest()
        scope = {"source_world": self.rows[0]["sourceWorld"],
                 "frame_sha256": self.rows[0]["frameSHA256"],
                 "patch_id": self.rows[0]["patchId"]}
        return (
            lambda: load_world_graph(self.catalog, catalog_sha256=pin, anchor_route="first"),
            lambda: load_graph(self.catalog, catalog_sha256=pin, build_id="b"*64, **scope),
            lambda: select_route(self.catalog, catalog_sha256=pin,
                                 destination_id="first-goal", start_xyz=[0,0,0],
                                 max_start_xz=0, max_start_y=0,
                                 max_snap_xz=0, max_snap_y=0, **scope),
        )

    def test_all_intake_paths_refuse_same_forged_destination_binding(self):
        self.add("first", [[0,0,0],[4,1,0]])
        for operation in self.shared_queries():
            self.assertIsNotNone(operation())
        # Re-pinning a changed catalog does not change the original package.
        self.rows[0]["destinationXYZ"] = [4,2,0]
        for operation in self.shared_queries():
            with self.subTest(operation=operation), self.assertRaisesRegex(
                    TraceError, "package requested destination mismatch"):
                operation()

    def test_both_graphs_verify_excluded_build_before_filtering(self):
        self.add("first", [[0,0,0],[4,1,0]])
        self.add("different", [[4,1,0],[8,2,0]], build="d")
        vertex, package, _ = self.shared_queries()
        self.assertEqual(set(vertex().routes), {"first"})
        self.assertEqual(package()["excluded"],
                         [{"routeId":"different", "reason":"different-planner-build"}])
        (self.root / "different.json").write_text("{}", encoding="utf-8")
        for operation in (vertex, package):
            with self.assertRaises(TraceError):
                operation()

    def test_both_graphs_ignore_unrelated_scope_but_refuse_world_conflict(self):
        self.add("first", [[0,0,0],[4,1,0]])
        self.add("unrelated", [[4,1,0],[8,2,0]], patch="d")
        (self.root / "unrelated.json").unlink()
        vertex, package, _ = self.shared_queries()
        self.assertEqual(set(vertex().routes), {"first"})
        self.assertEqual([e["routeId"] for e in package()["edges"]], ["first"])
        self.add("conflict", [[4,1,0],[8,2,0]], authority="different-source")
        for operation in self.shared_queries()[:2]:
            with self.assertRaisesRegex(TraceError, "conflicting source world metadata"):
                operation()
