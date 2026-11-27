"""Offline launcher regression tests; GUI dispatch is separate from Tk smoke."""
import hashlib
import io
from contextlib import redirect_stderr
import unittest
from unittest.mock import patch
import test_world_route_graph as fixtures
from rift_taxi import app
from rift_taxi.contracts import TraceError


class AppTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.WorldGraphTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.add("zeta",[[0,0,0],[4,1,0]])
        self.fixture.add("alpha",[[4,1,0],[8,2,0]])
        self.fixture.load("zeta")
        self.path=self.fixture.catalog
        self.pin=hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_choices_sorted_and_pinned(self):
        rows=app.catalog_choices(self.path,self.pin)
        self.assertEqual([r["routeId"] for r in rows],["alpha","zeta"])
        self.assertEqual(rows[0]["destinationId"],"alpha-goal")
        with self.assertRaises(TraceError):
            app.catalog_choices(self.path,"0"*64)
        self.path.write_text("{}",encoding="utf-8")
        with self.assertRaises(TraceError):
            app.catalog_choices(self.path,self.pin)

    def test_catalog_inventory_does_not_authorize_corrupt_packages(self):
        # Listing the catalog does not load the package. Opening the selected
        # graph must independently refuse the corrupt matching source.
        (self.fixture.root/"zeta.json").write_text("{}",encoding="utf-8")
        self.assertEqual(len(app.catalog_choices(self.path,self.pin)),2)
        with self.assertRaises(TraceError):
            app.load_world_graph(self.path,catalog_sha256=self.pin,anchor_route="zeta")

    def test_dispatch_and_cancel_without_desktop(self):
        import sys
        from types import SimpleNamespace
        fake_tk=SimpleNamespace(TclError=type("TclError",(Exception,),{}))
        with patch.dict(sys.modules,{"tkinter":fake_tk}), patch.object(
                app,"launch_demo") as demo, patch.object(app,"launch_world") as world:
            self.assertEqual(app.main(["demo"]),0)
            self.assertEqual(demo.call_args.args[0].classification,"SYNTHETIC_MODEL_ONLY")
            self.assertEqual(app.main(["world",str(self.path),"--catalog-sha256",self.pin,
                                       "--anchor-route","zeta"]),0)
            self.assertEqual(world.call_args.args[0].graph.classification,"OFFLINE_REVIEW_ONLY")
            with patch.object(app,"choose",return_value=None):
                self.assertEqual(app.main([]),0)
            self.assertEqual(demo.call_count,1)
            self.assertEqual(world.call_count,1)
            with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as err:
                app.main(["world",str(self.path),"--catalog-sha256","0"*64,
                          "--anchor-route","zeta"])
            self.assertEqual(err.exception.code,2)
            self.assertEqual(world.call_count,1)
