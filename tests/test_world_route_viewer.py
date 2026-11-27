"""Headless review-viewer regressions using invented pinned world packages."""
import json
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr
import io
import test_world_route_graph as fixtures
from rift_taxi.contracts import TraceError
from rift_taxi.world_route_viewer import review_scene, scene_svg, main


class WorldViewerTests(unittest.TestCase):
    def setUp(self):
        # Reuse existing fixture producer without registering its tests twice.
        self.fixture = fixtures.WorldGraphTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.add("first", [[0,0,0],[4,1,0]])
        self.fixture.add("direct", [[4,1,0],[8,2,0]])
        self.fixture.add("detour", [[4,1,0],[6,3,3],[8,2,0]])
        self.world = self.fixture.load("first")

    def test_scene_reuses_planner_and_retains_elevation(self):
        scene = review_scene(self.world,start="first:0",destination="direct")
        self.assertEqual(scene["classification"],"OFFLINE_REVIEW_ONLY")
        self.assertEqual(scene["plan"]["edges"],["first:edge:0","direct:edge:0"])
        self.assertEqual([p["xyz"][1] for p in scene["profile"]],[0,1,2])
        self.assertAlmostEqual(scene["profile"][-1]["distance"],scene["plan"]["distance"])
        self.assertFalse(scene["plan"]["physicalQualification"])
        self.assertFalse(scene["plan"]["gameInputSent"])
        self.assertEqual({e["id"] for e in scene["edges"] if e["role"]=="route"},
                         set(scene["plan"]["edges"]))

    def test_detour_and_unreachable_state(self):
        a = review_scene(self.world,start="first:0",destination="direct")
        b = review_scene(self.world,start="first:0",destination="direct",
                         blocked_edges=["direct:edge:0"])
        self.assertGreater(b["plan"]["distance"],a["plan"]["distance"])
        self.assertEqual([n["screen"] for n in a["nodes"]],[n["screen"] for n in b["nodes"]])
        self.assertEqual([e["id"] for e in b["edges"] if e["role"]=="blocked"],["direct:edge:0"])
        c = review_scene(self.world,start="first:0",destination="direct",
                         blocked_edges=["first:edge:0"])
        self.assertEqual(c["plan"]["status"],"no-route")
        self.assertEqual(c["profile"],[])
        self.assertFalse(any(e["role"]=="route" for e in c["edges"]))

    def test_svg_has_no_active_content_and_escapes_labels(self):
        scene = review_scene(self.world,start="first:0",destination="direct")
        scene["plan"]["destinationLabel"] = '<script>alert("x")</script>'
        root = ET.fromstring(scene_svg(scene))
        self.assertEqual(root.tag,"{http://www.w3.org/2000/svg}svg")
        self.assertFalse(any(e.tag.endswith("script") for e in root.iter()))
        self.assertTrue(any("<script>" in (e.text or "") for e in root.iter()))
        self.assertIn("OFFLINE REVIEW ONLY",scene_svg(scene))

    def test_vertical_projection_keeps_3d_profile(self):
        self.fixture.rows.clear()
        self.fixture.add("vertical", [[1,0,1],[1,3,1]])
        world = self.fixture.load("vertical")
        scene = review_scene(world,start="vertical:0",destination="vertical")
        self.assertEqual(scene["edges"][0]["from"],scene["edges"][0]["to"])
        self.assertEqual(scene["plan"]["distance"],3.)
        self.assertNotEqual(scene["profile"][0]["screen"],scene["profile"][1]["screen"])

    def test_invalid_canvas_and_exclusive_export(self):
        for w in (0, True, float("nan"), 4001):
            with self.subTest(w=w), self.assertRaises(TraceError):
                review_scene(self.world,start="first:0",destination="direct",width=w)
        from hashlib import sha256
        catalog = self.fixture.catalog
        output = self.fixture.root/"review.svg"
        args=[str(catalog),"--catalog-sha256",sha256(catalog.read_bytes()).hexdigest(),
              "--anchor-route","first","svg","--start","first:0","--destination","direct",
              "--out",str(output)]
        self.assertEqual(main(args),0)
        before=output.read_bytes()
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as err:
            main(args)
        self.assertEqual(err.exception.code,2)
        self.assertEqual(output.read_bytes(),before)
