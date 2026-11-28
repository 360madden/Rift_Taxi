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
from rift_taxi.world_route_graph import (load_world_graph, plan_world_route,
                                         review_position, destination_availability, main)
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


    def test_position_review_projects_full_3d_and_keeps_source_binding(self):
        self.add("slope", [[0,0,0],[4,2,0]])
        world = self.load("slope")
        r = review_position(world, position=[2,1,1], max_xz=1, max_y=.1)
        self.assertEqual(r["vertexCount"],0)
        self.assertEqual(r["segmentCount"],1)
        hit=r["segments"][0]
        self.assertAlmostEqual(hit["fraction"],.5)
        self.assertEqual(hit["projectedXYZ"],[2,1,0])
        self.assertEqual(hit["distanceXZ"],1.)
        self.assertEqual(hit["distanceY"],0.)
        self.assertEqual(hit["edgeSource"],world.edge_sources["slope:edge:0"])
        self.assertEqual(r["graphSHA256"],world.graph.sha256)
        for key in ("automaticStartBinding","transformQualified","endpointConnectorsVerified",
                    "physicalQualification","productionInputAuthorized","gameInputSent"):
            self.assertIs(r[key],False)
        # An interior projection is not an admitted start coordinate.
        with self.assertRaises(TraceError):
            plan_world_route(world,destination="slope",start_xyz=[2,1,0])

    def test_position_review_separates_floors_and_preserves_ambiguity(self):
        self.add("low", [[0,0,0],[4,0,0]])
        self.add("high", [[0,3,0],[4,3,0]])
        world=self.load("low")
        r=review_position(world,position=[2,0,0],max_xz=0,max_y=0)
        self.assertEqual([e["edgeId"] for e in r["segments"]],["low:edge:0"])
        r=review_position(world,position=[2,1.5,0],max_xz=0,max_y=2)
        self.assertEqual(r["segmentCount"],2)
        self.assertEqual([e["edgeId"] for e in r["segments"]],["high:edge:0","low:edge:0"])
        r=review_position(world,position=[2,1.5,0],max_xz=0,max_y=2,limit=1)
        self.assertEqual(r["segmentCount"],2)
        self.assertEqual(len(r["segments"]),1)
        self.assertFalse(r["automaticStartBinding"])

    def test_position_review_exact_vertices_and_clamped_projections(self):
        self.add("a", [[0,0,0],[4,0,0]])
        self.add("b", [[4,0,0],[8,0,0]])
        world=self.load("a")
        r=review_position(world,position=[4,0,0],max_xz=0,max_y=0)
        self.assertEqual(len(r["exactNodeIds"]),1)
        self.assertEqual(r["vertices"][0]["aliases"],["a:1","b:0"])
        self.assertEqual([e["fraction"] for e in r["segments"]],[1.,0.])
        r=review_position(world,position=[-1,0,0],max_xz=1,max_y=0)
        self.assertEqual(r["segments"][0]["fraction"],0.)
        self.assertEqual(r["segments"][0]["projectedXYZ"],[0,0,0])
        self.assertEqual(review_position(world,position=[0,20,0],max_xz=1,max_y=1)["status"],
                         "no-candidates")

    def test_position_review_rejects_invalid_limits_and_cli_writes_exclusively(self):
        self.add("a", [[0,0,0],[4,0,0]])
        world=self.load("a")
        for args in ({"max_xz":-1},{"max_y":101},{"max_y":True},
                     {"max_xz":float("nan")},{"limit":True},{"limit":65},
                     {"position":[0,float("inf"),0]}):
            params={"position":[0,0,0],"max_xz":1,"max_y":1}
            params.update(args)
            with self.subTest(args=args), self.assertRaises(TraceError):
                review_position(world,**params)
        import io
        from contextlib import redirect_stdout, redirect_stderr
        pin=hashlib.sha256(self.catalog.read_bytes()).hexdigest()
        out=self.root/"position.json"
        args=[str(self.catalog),"--catalog-sha256",pin,"--anchor-route","a",
              "locate","--xyz","2","0","0","--max-xz","0","--max-y","0","--out",str(out)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args),0)
        original=out.read_bytes()
        self.assertEqual(json.loads(original)["segmentCount"],1)
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as err:
            main(args)
        self.assertEqual(err.exception.code,2)
        self.assertEqual(out.read_bytes(),original)

    def test_destination_availability_matches_directed_a_star(self):
        # Shared exact endpoints, a directed cycle, a longer alternative,
        # a disconnected island and coincident interiors without a junction.
        self.add("first", [[0,0,0],[4,1,0]])
        self.add("direct", [[4,1,0],[8,2,0]])
        self.add("detour", [[4,1,0],[6,2,3],[8,2,0]])
        self.add("cycle", [[8,2,0],[0,0,0]])
        self.add("island", [[20,0,0],[24,0,0]])
        self.add("crossing", [[6,2,-3],[6,2,3],[6,2,6]])
        world = self.load("first")
        for alias in sorted(world.aliases):
            for blocked in ([], ["direct:edge:0"], ["first:edge:0"], sorted(world.graph.edges)):
                with self.subTest(alias=alias, blocked=blocked):
                    r=destination_availability(world,start=alias,blocked_edges=blocked)
                    self.assertEqual([row["routeId"] for row in r["destinations"]],sorted(world.routes))
                    for row in r["destinations"]:
                        plan=plan_world_route(world,start=alias,destination=row["routeId"],blocked_edges=blocked)
                        expected="reachable" if plan["status"]=="route-found" else plan["status"]
                        self.assertEqual(row["status"],expected)
                    self.assertEqual(r["reachableCount"],sum(row["status"]!="no-route" for row in r["destinations"]))
                    for key in ("physicalQualification","productionInputAuthorized","gameInputSent",
                                "transformQualified","endpointConnectorsVerified","corridorClearanceVerified"):
                        self.assertIs(r[key],False)

    def test_destination_availability_exact_source_and_refusals(self):
        self.add("first", [[0,0,0],[4,1,0],[8,2,0]])
        self.add("cross", [[4,1,-4],[4,1,0],[4,1,4]])
        world=self.load("first")
        a=destination_availability(world,start="first:0")
        b=destination_availability(world,start_xyz=[0,0,0])
        self.assertEqual(a["destinations"],b["destinations"])
        self.assertEqual(a["graphSHA256"],world.graph.sha256)
        self.assertEqual(a["reachableCount"],1)
        for kwargs in ({}, {"start":"missing"}, {"start":"first:0","start_xyz":[0,0,0]},
                       {"start_xyz":[4,1,0]}, {"start_xyz":[.1,0,0]},
                       {"start":"first:0","blocked_edges":["missing"]},
                       {"start":"first:0","blocked_edges":"first:edge:0"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TraceError):
                destination_availability(world,**kwargs)

    def test_destination_availability_cli_preserves_output(self):
        from contextlib import redirect_stdout, redirect_stderr
        import io
        self.add("first", [[0,0,0],[4,1,0]])
        self.load("first")
        out=self.root/"availability.json"
        args=[str(self.catalog),"--catalog-sha256",hashlib.sha256(self.catalog.read_bytes()).hexdigest(),
              "--anchor-route","first","reachable","--start","first:0",
              "--blocked-edge","first:edge:0","--out",str(out)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args),0)
        original=out.read_bytes()
        report=json.loads(original)
        self.assertEqual(report["reachableCount"],0)
        self.assertEqual(report["destinations"][0]["status"],"no-route")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as err:
            main(args)
        self.assertEqual(err.exception.code,2)
        self.assertEqual(out.read_bytes(),original)
