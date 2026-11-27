"""Product-level local routing and modeled execution; no live RIFT dependency."""
import hashlib
import io
import json
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import tempfile
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.local_taxi import demo_graph, decode_graph, plan_route, run_local_journey, main, SCHEMA


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
