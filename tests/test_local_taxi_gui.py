"""Headless tests for the local route preview; Tk is not imported at test time."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rift_taxi.contracts import TraceError
from rift_taxi.local_taxi import SCHEMA, decode_graph, demo_graph
from rift_taxi.local_taxi_gui import build_scene, load_local_map, preview


class LocalViewerTests(unittest.TestCase):
    def test_route_preview_and_blocked_detour_use_existing_planner(self):
        graph = demo_graph()
        g, main = preview(graph, start="entrance", destination="bank")
        self.assertIs(g, graph)
        self.assertEqual(main["distance"], 16.)
        scene = build_scene(g, main, width=800, height=400)
        self.assertEqual({e["id"] for e in scene["edges"] if e["role"] == "route"},
                         set(main["edges"]))
        excluded = "main-west-to-main-east"
        g, detour = preview(graph, start="entrance", destination="bank",
                            blocked_edges=[excluded])
        scene2 = build_scene(g, detour, width=800, height=400)
        self.assertGreater(detour["distance"], main["distance"])
        self.assertEqual(next(e["role"] for e in scene2["edges"] if e["id"] == excluded),
                         "blocked")
        # The frame is independent of the selected route.
        self.assertEqual([n["position"] for n in scene["nodes"]],
                         [n["position"] for n in scene2["nodes"]])
        self.assertFalse(detour["gameInputSent"])

    def test_interior_start_visible_and_original_graph_unchanged(self):
        graph = demo_graph()
        g, plan = preview(graph, edge_id="main-west-to-main-east", fraction=.5,
                          destination="bank")
        scene = build_scene(g, plan, width=600, height=400)
        self.assertEqual(plan["distance"], 10.)
        start = next(n for n in scene["nodes"] if n["role"] == "start")
        self.assertEqual(start["id"], plan["startSelection"]["startNode"])
        self.assertNotIn(start["id"], graph.nodes)
        self.assertEqual(plan["startSelection"]["sourceGraphSHA256"], graph.sha256)
        self.assertEqual(next(e["role"] for e in scene["edges"]
                              if e["id"] == plan["startSelection"]["suffixEdgeId"]), "route")
        with self.assertRaisesRegex(TraceError, "identity"):
            build_scene(graph, plan, width=600, height=400)

    def test_projection_preserves_aspect_and_positive_z_up(self):
        graph = demo_graph()
        g, plan = preview(graph, start="entrance", destination="bank")
        for w,h in ((800,240),(240,800),(80,80)):
            scene = build_scene(g, plan, width=w, height=h)
            positions = {n["id"]: n["position"] for n in scene["nodes"]}
            a,b,c = (positions[n] for n in ("entrance","main-west","north-west"))
            self.assertAlmostEqual(b[0]-a[0], a[1]-c[1])
            self.assertGreater(b[0], a[0])
            self.assertLess(c[1], a[1])
            self.assertTrue(all(0 <= x <= w and 0 <= y <= h for x,y in positions.values()))

    def test_no_route_and_same_node_have_no_highlighted_edges(self):
        graph = demo_graph()
        for start, exclusions, expected in (
            ("entrance", ["entrance-to-main-west","entrance-to-north-west"], "no-route"),
            ("bank", [], "already-at-destination")):
            g, plan = preview(graph, start=start, destination="bank", blocked_edges=exclusions)
            scene = build_scene(g, plan, width=400, height=300)
            self.assertEqual(scene["status"], expected)
            self.assertFalse(any(e["role"] == "route" for e in scene["edges"]))
            if start == "bank":
                self.assertEqual(sum(n["role"] == "start-goal" for n in scene["nodes"]),1)

    def test_invalid_preview_and_canvas_inputs(self):
        graph = demo_graph()
        for options in ({}, {"start":"entrance","edge_id":"main-west-to-main-east","fraction":.5},
                        {"edge_id":"main-west-to-main-east"}, {"start":"entrance","fraction":.5}):
            with self.subTest(options=options), self.assertRaises(TraceError):
                preview(graph, destination="bank", **options)
        g, plan = preview(graph, start="entrance", destination="bank")
        for width in (0, True, float("nan"), 20001):
            with self.subTest(width=width), self.assertRaises(TraceError):
                build_scene(g, plan, width=width, height=400)

    def test_single_axis_map_and_external_pin(self):
        doc = {"schema":SCHEMA,"classification":"SYNTHETIC_MODEL_ONLY","mapId":"linear",
               "nodes":[{"id":"a","xyz":[0,0,0],"kind":"guide"},
                        {"id":"b","xyz":[0,0,8],"kind":"guide"}],
               "edges":[{"id":"ab","from":"a","to":"b"}],
               "destinations":[{"id":"b","label":"B","node":"b"}]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"map.json"
            raw = json.dumps(doc).encode()
            path.write_bytes(raw)
            graph = load_local_map(path, hashlib.sha256(raw).hexdigest())
            g, plan = preview(graph, start="a", destination="b")
            scene = build_scene(g, plan, width=400,height=300)
            a,b = [n["position"] for n in scene["nodes"]]
            self.assertEqual(a[0], b[0])
            self.assertGreater(a[1], b[1])
            with self.assertRaisesRegex(TraceError,"SHA mismatch"):
                load_local_map(path, "0"*64)
            with self.assertRaises(TraceError):
                load_local_map(None, "0"*64)
