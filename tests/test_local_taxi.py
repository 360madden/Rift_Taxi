"""Product-level local routing and modeled execution; no live RIFT dependency."""
import hashlib
import io
import json
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import tempfile
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.local_taxi import demo_graph, decode_graph, plan_route, run_local_journey, locate_start, bind_edge_start, main, SCHEMA


class LocalTaxiTests(unittest.TestCase):
    def test_shortest_path_and_blocked_edge_detour(self):
        graph = demo_graph()
        route = plan_route(graph, "entrance", "bank")
        self.assertEqual(route["nodes"], ["entrance", "main-west", "main-east", "junction", "bank"])
        self.assertEqual(route["distance"], 16.)
        detour = plan_route(graph, "entrance", "bank", blocked_edges=["main-west-to-main-east"])
        self.assertEqual(detour["nodes"], ["entrance", "north-west", "north-east", "junction", "bank"])
        self.assertGreater(detour["distance"], route["distance"])
        self.assertNotIn("main-west-to-main-east", detour["edges"])
        self.assertEqual(detour["points"][-2]["kind"], "hard_stop")

    def test_disconnected_and_already_there_are_distinct(self):
        graph = demo_graph()
        blocked = ["entrance-to-main-west", "entrance-to-north-west"]
        self.assertEqual(plan_route(graph, "entrance", "bank", blocked_edges=blocked)["status"], "no-route")
        self.assertEqual(run_local_journey(graph, "bank", "bank")["status"], "already-at-destination")
        self.assertIsNone(run_local_journey(graph, "entrance", "bank", blocked_edges=blocked)["journey"])

    def test_planned_route_flows_into_existing_controller(self):
        graph = demo_graph()
        result = run_local_journey(graph, "entrance", "bank")
        self.assertEqual(result["status"], "model-arrived")
        self.assertEqual(result["journey"]["completedLegs"], 2)
        self.assertTrue(result["journey"]["allObligationsObserved"])
        self.assertFalse(result["physicalQualification"])
        self.assertFalse(result["gameInputSent"])
        # Exercise the alternate path through the actual existing controller.
        detour = run_local_journey(graph, "entrance", "bank",
                                   blocked_edges=["main-west-to-main-east"], delay_steps=2)
        self.assertEqual(detour["status"], "model-arrived")
        self.assertEqual(detour["journey"]["completedLegs"], 2)
        self.assertNotIn("main-west-to-main-east", detour["plan"]["edges"])

    def test_directed_edges_no_implicit_reverse_and_mandatory_region(self):
        graph_doc = {"schema": SCHEMA, "classification": "SYNTHETIC_MODEL_ONLY", "mapId": "one-way",
                     "nodes": [{"id": "a", "xyz": [0,0,0], "kind": "guide"},
                               {"id": "b", "xyz": [4,0,0], "kind": "mandatory_passage",
                                "region": {"minXYZ": [3,-.1,-1], "maxXYZ": [5,.1,1]}},
                               {"id": "c", "xyz": [8,0,0], "kind": "guide"}],
                     "edges": [{"id": "ab", "from": "a", "to": "b"}, {"id": "bc", "from": "b", "to": "c"}],
                     "destinations": [{"id": "end", "label": "End", "node": "c"},
                                      {"id": "start", "label": "Start", "node": "a"}]}
        graph = decode_graph(json.dumps(graph_doc).encode())
        self.assertEqual(plan_route(graph, "c", "start")["status"], "no-route")
        self.assertEqual(plan_route(graph, "a", "end")["points"][1]["kind"], "mandatory_passage")
        result = run_local_journey(graph, "a", "end")
        self.assertEqual(result["status"], "model-arrived")
        self.assertEqual(result["journey"]["obligations"][0]["kind"], "mandatory_passage")
        graph_doc["edges"][0]["to"] = "missing"
        with self.assertRaises(TraceError):
            decode_graph(json.dumps(graph_doc).encode())

    def test_bad_inputs_and_unknown_edge_fail_closed(self):
        graph = demo_graph()
        for start, destination, blocked in (("unknown","bank",[]), ("entrance","unknown",[]),
                                             ("entrance","bank",["not-an-edge"])):
            with self.subTest(start=start,destination=destination), self.assertRaises(TraceError):
                plan_route(graph,start,destination,blocked_edges=blocked)
        for raw in (b'{"schema":1,"schema":2}', b'[]', b'{"schema":"wrong"}'):
            with self.assertRaises(TraceError):
                decode_graph(raw)

    def test_cli_reports_and_preserves_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/"plan.json"
            args = ["plan","--start","entrance","--destination","bank","--out",str(out)]
            with redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(args),0)
            self.assertEqual(json.loads(stdout.getvalue())["status"],"route-found")
            before = out.read_bytes()
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(error.exception.code,2)
            self.assertEqual(out.read_bytes(),before)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan","--start","entrance","--destination","bank",
                                       "--blocked-edge","entrance-to-main-west","--blocked-edge",
                                       "entrance-to-north-west"]),1)

    def test_location_exact_binding_and_ranked_nonbinding_suggestions(self):
        graph = demo_graph()
        exact = locate_start(graph, [4, 0, 0], limit=2)
        self.assertEqual(exact["startNode"], "main-west")
        self.assertEqual(exact["graphSHA256"], graph.sha256)
        self.assertEqual(exact["candidates"][0]["distance3D"], 0.)
        self.assertTrue(exact["candidates"][0]["exactMatch"])
        self.assertEqual(len(exact["candidates"]), 2)
        # The midpoint tie is stable by authored node ID. Even a point on
        # an existing edge is not silently snapped or made a new connector.
        midpoint = locate_start(graph, [2, 0, 0], limit=2)
        self.assertIsNone(midpoint["startNode"])
        self.assertEqual([c["node"] for c in midpoint["candidates"]],
                         ["entrance", "main-west"])
        self.assertFalse(midpoint["connectorVerified"])
        self.assertFalse(midpoint["productionInputAuthorized"])
        wrong_floor = locate_start(graph, [4, 1, 0], limit=1)
        self.assertIsNone(wrong_floor["startNode"])
        self.assertEqual(wrong_floor["candidates"][0]["distanceXZ"], 0.)
        self.assertEqual(wrong_floor["candidates"][0]["distanceY"], 1.)

    def test_locator_rejects_invalid_positions_and_limits(self):
        graph = demo_graph()
        for position in ([1, 2], [True, 0, 0], [float("nan"), 0, 0], [1e7, 0, 0]):
            with self.subTest(position=position), self.assertRaises(TraceError):
                locate_start(graph, position)
        for limit in (0, 21, True, 2.5):
            with self.subTest(limit=limit), self.assertRaises(TraceError):
                locate_start(graph, [0, 0, 0], limit=limit)

    def test_coordinate_cli_keeps_exact_origin_and_refuses_off_node(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "coordinate-plan.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["plan", "--start-xyz", "4", "0", "0",
                                       "--destination", "bank", "--out", str(path)]), 0)
            receipt = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["startNode"], "main-west")
            self.assertEqual(receipt["points"][0]["xyz"], [4, 0, 0])
            self.assertEqual(receipt["startSelection"]["queryXYZ"], [4, 0, 0])
            self.assertEqual(receipt["distance"], 12.)
            # Off-node input must not produce a route or output file.
            rejected = Path(temp) / "rejected.json"
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(["plan", "--start-xyz", "4.001", "0", "0",
                      "--destination", "bank", "--out", str(rejected)])
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(rejected.exists())
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["locate", "--xyz", "4.001", "0", "0"]), 1)
            self.assertEqual(json.loads(output.getvalue())["status"], "no-exact-node")

    def test_coordinate_journey_uses_existing_model(self):
        with redirect_stdout(io.StringIO()) as output:
            code = main(["journey", "--start-xyz", "0", "0", "0",
                         "--destination", "bank", "--delay-steps", "2"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "model-arrived")
        # The CLI must never allow two competing start authorities.
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(["plan", "--start", "entrance", "--start-xyz", "4", "0", "0",
                  "--destination", "bank"])
        self.assertEqual(error.exception.code, 2)

    def test_directed_interior_start_preserves_graph_and_route_identity(self):
        graph = demo_graph()
        derived, start, selection = bind_edge_start(graph, "main-west-to-main-east", .5)
        self.assertEqual(selection["startXYZ"], [6., 0., 0.])
        self.assertEqual(selection["remainingDistance"], 2.)
        self.assertEqual(selection["sourceGraphSHA256"], graph.sha256)
        self.assertEqual(selection["derivedGraphSHA256"], derived.sha256)
        self.assertNotEqual(derived.sha256, graph.sha256)
        self.assertNotIn(start, graph.nodes)
        self.assertEqual(len(derived.edges), len(graph.edges)+1)
        plan = plan_route(derived, start, "bank")
        self.assertEqual(plan["distance"], 10.)
        self.assertEqual(plan["nodes"], [start, "main-east", "junction", "bank"])
        self.assertEqual(plan["edges"][0], selection["suffixEdgeId"])
        self.assertEqual(plan["points"][-2]["kind"], "hard_stop")
        again, _, _ = bind_edge_start(graph, "main-west-to-main-east", .5)
        self.assertEqual(again.sha256, derived.sha256)
        reverse, reverse_start, rev_selection = bind_edge_start(graph, "main-east-to-main-west", .5)
        self.assertNotEqual(reverse.sha256, derived.sha256)
        self.assertEqual(rev_selection["startXYZ"], selection["startXYZ"])
        self.assertEqual(plan_route(reverse, reverse_start, "entrance")["nodes"][1], "main-west")
        self.assertFalse(selection["physicalQualification"])

    def test_edge_binding_rejects_invalid_fraction_and_blocked_source(self):
        graph = demo_graph()
        for t in (0., 1., -.1, 1.1, True, float("nan"), float("inf"), 1e-15):
            with self.subTest(fraction=t), self.assertRaises(TraceError):
                bind_edge_start(graph, "main-west-to-main-east", t)
        for blocked in (["main-west-to-main-east"], ["missing"]):
            with self.subTest(blocked=blocked), self.assertRaises(TraceError):
                bind_edge_start(graph, "main-west-to-main-east", .5, blocked_edges=blocked)
        with self.assertRaises(TraceError):
            bind_edge_start(graph, "missing", .5)

    def test_edge_start_cannot_join_crossing_or_alias_authored_node(self):
        # Two crossing edges do not create a junction. A start on one edge
        # exposes only its directed suffix; proximity cannot switch routes.
        doc = {"schema": SCHEMA, "classification": "SYNTHETIC_MODEL_ONLY", "mapId": "crossing",
               "nodes": [{"id": n, "xyz": p, "kind": "guide"}
                         for n, p in (("a",[0,0,2]),("b",[4,0,2]),
                                      ("c",[2,0,0]),("d",[2,0,4]))],
               "edges": [{"id":"ab","from":"a","to":"b"},{"id":"cd","from":"c","to":"d"}],
               "destinations": [{"id":"b","label":"B","node":"b"},
                                {"id":"d","label":"D","node":"d"}]}
        graph = decode_graph(json.dumps(doc).encode())
        derived, start, _ = bind_edge_start(graph, "ab", .5)
        self.assertEqual(plan_route(derived, start, "d")["status"], "no-route")
        self.assertEqual(plan_route(derived, start, "b")["distance"], 2.)
        doc["nodes"].append({"id":"crossing","xyz":[2,0,2],"kind":"guide"})
        with self.assertRaisesRegex(TraceError, "coincides"):
            bind_edge_start(decode_graph(json.dumps(doc).encode()), "ab", .5)

    def test_edge_cli_receipt_and_model_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "edge-plan.json"
            args = ["--start-edge","main-west-to-main-east","--edge-fraction",".5",
                    "--destination","bank"]
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["plan", *args, "--out",str(path)]),0)
            self.assertEqual(json.loads(output.getvalue())["startSelection"]["startXYZ"], [6,0,0])
            receipt = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["graphSHA256"],receipt["startSelection"]["derivedGraphSHA256"])
            self.assertEqual(receipt["distance"],10.)
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["journey", *args]),0)
            self.assertEqual(json.loads(output.getvalue())["status"],"model-arrived")
            for invalid in (["--start-edge","main-west-to-main-east"],
                            ["--start","entrance","--edge-fraction",".5"]):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    main(["plan", *invalid, "--destination","bank"])
                self.assertEqual(error.exception.code,2)
