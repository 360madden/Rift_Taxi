"""Bounded Windows/Tk smoke of the actual Taxi desktop entry points.

Run with python -B -m scripts.desktop_viewer_smoke [--catalog ...].
This invokes the production launch functions and uses real Tk widgets, while
substituting only the blocking event-loop entry to exercise controls and close
the viewer deterministically. It does not interact with RIFT, take screenshots,
or prove what a human can see on a different desktop/session. No GUI input is
sent through the OS; widget methods operate exclusively on this process.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from rift_taxi.local_taxi import demo_graph
from rift_taxi.local_taxi_gui import launch as launch_synthetic
from rift_taxi.world_route_graph import load_world_graph
from rift_taxi.world_route_viewer import launch as launch_world


def descendants(widget):
    """Yield real descendant widgets in their creation order."""
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def exercise(launch, graph, *, world_route=None):
    """Run actual widget initialization, route selection, and rerender.

    Raise on any callback error, missing/multiple expected control, unmapped
    canvas or missing highlighted route. All windows are destroyed in finally.
    """
    import tkinter as tk
    from tkinter import ttk
    errors = []
    receipt = {}

    def callback_error(self, exc_type, value, traceback):
        errors.append(f"{exc_type.__name__}: {value}")

    def smoke_loop(root, *args, **kwargs):
        try:
            root.update_idletasks()
            root.update()
            children = list(descendants(root))
            canvases = [w for w in children if isinstance(w, tk.Canvas)]
            buttons = [w for w in children if isinstance(w, ttk.Button)
                       and w.cget("text") == "Preview route"]
            combos = [w for w in children if isinstance(w, ttk.Combobox)]
            if len(canvases) != 1 or len(buttons) != 1:
                raise RuntimeError("expected exactly one preview canvas and button")
            canvas = canvases[0]
            if world_route is None:
                # Select an actual journey, not the default bank-to-bank case.
                if len(combos) != 4:
                    raise RuntimeError("unexpected synthetic controls")
                combos[0].set("node")
                combos[1].set("entrance")
                combos[3].set("bank")
                green = "#5bd6a2"
            else:
                if len(combos) != 2:
                    raise RuntimeError("unexpected imported-world controls")
                combos[0].set(world_route + ":0")
                combos[1].set(world_route)
                green = "#54d6a1"
            buttons[0].invoke()
            root.update_idletasks()
            root.update()
            lines = [item for item in canvas.find_all() if canvas.type(item) == "line"]
            selected = [item for item in lines if canvas.itemcget(item, "fill") == green]
            labels = [str(w.cget("text")) for w in children if isinstance(w, ttk.Label)]
            text = [canvas.itemcget(item, "text") for item in canvas.find_all()
                    if canvas.type(item) == "text"]
            if errors:
                raise RuntimeError("Tk callbacks failed: " + "; ".join(errors))
            if not root.winfo_ismapped() or not canvas.winfo_ismapped() or not selected:
                raise RuntimeError("preview canvas not mapped or route not drawn")
            if not any("route-found" in label for label in labels):
                raise RuntimeError("preview did not report route-found")
            receipt.update(title=root.title(), tkVersion=str(root.tk.call("info", "patchlevel")),
                           mapped=True, canvasSize=[canvas.winfo_width(), canvas.winfo_height()],
                           canvasItems=len(canvas.find_all()), highlightedLines=len(selected),
                           statusLabels=[label for label in labels if "route-found" in label],
                           canvasTextCount=len(text), callbackErrors=[])
        finally:
            root.destroy()

    # This is test-only interception of the main loop, not a replacement
    # renderer. Production builds retain their normal blocking event loop.
    with patch.object(tk.Tk, "mainloop", smoke_loop), patch.object(
            tk.Tk, "report_callback_exception", callback_error):
        launch(graph)
    if not receipt:
        raise RuntimeError("viewer did not enter its Tk loop")
    return receipt


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", type=Path)
    p.add_argument("--catalog-sha256")
    p.add_argument("--anchor-route")
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    if (a.catalog is None and (a.catalog_sha256 or a.anchor_route)) or (
            a.catalog is not None and not (a.catalog_sha256 and a.anchor_route)):
        p.error("supply catalog, catalog SHA and anchor route together")
    results = {"schema":"taxi.desktop-widget-smoke/1",
               "synthetic":exercise(launch_synthetic, demo_graph()),
               "importedWorld":None, "humanVisualInspection":False,
               "physicalQualification":False,"gameInputSent":False}
    if a.catalog is not None:
        world = load_world_graph(a.catalog,catalog_sha256=a.catalog_sha256,
                                 anchor_route=a.anchor_route)
        results["importedWorld"] = exercise(launch_world, world, world_route=a.anchor_route)
    raw = json.dumps(results,indent=2,allow_nan=False)+"\n"
    if a.out is not None:
        with a.out.open("x",encoding="utf-8",newline="\n") as f:
            f.write(raw)
    print(raw,end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
