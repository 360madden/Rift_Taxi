"""Regression tests for the invented desktop CI catalog, no GUI required."""
import tempfile
import unittest
from pathlib import Path

from scripts.ci_desktop_smoke import digest, generate_plan
from rift_taxi.world_catalog_build import build_catalog
from rift_taxi.world_route_graph import load_world_graph, plan_world_route


class DesktopFixtureTests(unittest.TestCase):
    def test_fixture_is_deterministic_and_plannable(self):
        # A generated catalog must have identical bytes in separate roots.
        with tempfile.TemporaryDirectory() as temp:
            roots=[Path(temp)/name for name in ("a","b")]
            catalogs=[]
            for root in roots:
                root.mkdir()
                plan=generate_plan(root)
                encoded=build_catalog(plan,expected_plan_sha256=digest(plan))
                catalog=root/"catalog.json"
                catalog.write_bytes(encoded)
                catalogs.append(encoded)
                world=load_world_graph(catalog,catalog_sha256=digest(catalog),
                                       anchor_route="invented-main")
                result=plan_world_route(world,start="invented-main:0",destination="invented-main")
                self.assertEqual(world.scope["sourceWorld"],"synthetic-ci")
                self.assertEqual(result["status"],"route-found")
                self.assertFalse(result["physicalQualification"])
                self.assertFalse(result["gameInputSent"])
                self.assertEqual(len(result["edges"]),4)
                self.assertEqual(set(world.routes),{"invented-main","invented-side"})
            self.assertEqual(catalogs[0],catalogs[1])

    def test_fixture_never_overwrites_existing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            existing=root/"invented-main-candidate.json"
            existing.write_bytes(b"preserve")
            with self.assertRaises(FileExistsError):
                generate_plan(root)
            self.assertEqual(existing.read_bytes(),b"preserve")
