"""Standalone local desktop route preview for authored synthetic Taxi maps.

Tk is optional at launch; the pure scene builder is headless-testable. The
viewer uses the existing A* planner and optional synthetic journey replay.
It never accesses RIFT or sends game input.
All coordinates are graph-local XZ (Y is fixed by the synthetic graph schema).
No network, external assets, sibling tools, or third-party Python packages.
"""
from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
import re

from .contracts import TraceError, _read_bounded, _number
from .local_taxi import (MAX_GRAPH_BYTES, bind_edge_start, decode_graph,
                         demo_graph, plan_route, require)


def preview(graph, *, destination, start=None, edge_id=None, fraction=None,
            blocked_edges=()):
    """Return a pure plan and the exact graph used to produce it.

    Edge-start mode preserves the temporary suffix and original source binding.
    A fresh query always starts from the original graph, never a prior result.
    """
    require(graph.classification == "SYNTHETIC_MODEL_ONLY", "preview requires a synthetic graph")
    require((start is None) != (edge_id is None), "choose exactly one start mode")
    require((edge_id is None) == (fraction is None), "edge fraction requires an edge")
    binding = None
    if edge_id is not None:
        graph, start, binding = bind_edge_start(graph, edge_id, fraction,
                                                blocked_edges=blocked_edges)
    result = plan_route(graph, start, destination, blocked_edges=blocked_edges)
    if binding is not None:
        result = {**result, "startSelection": binding}
    return graph, result


def build_scene(graph, plan, *, width, height):
    """Project all authored XZ coordinates into a bounded aspect-correct canvas.

    The map is fit as a whole so route changes do not shift the coordinate
    frame. Positive Z is displayed upward; north is intentionally not asserted.
    Scene roles distinguish directed network edges, exclusions and the route.
    """
    require(graph.classification == "SYNTHETIC_MODEL_ONLY"
            and plan.get("classification") == graph.classification,
            "scene requires a synthetic graph and plan")
    w, h = _number(width, "canvas width"), _number(height, "canvas height")
    require(80 <= w <= 20000 and 80 <= h <= 20000, "invalid canvas dimensions")
    require(plan["graphSHA256"] == graph.sha256, "plan graph identity mismatch")
    xs = [node.xyz[0] for node in graph.nodes.values()]
    zs = [node.xyz[2] for node in graph.nodes.values()]
    cx = (min(xs) + max(xs)) / 2
    cz = (min(zs) + max(zs)) / 2
    span_x, span_z = max(xs)-min(xs), max(zs)-min(zs)
    pad = min(46., w/5, h/5)
    # Ignore an exactly constant axis rather than divide by zero. Graph
    # decoding requires nondegenerate edges, but handle both axes defensively.
    scale = min((w-2*pad)/span_x if span_x else math.inf,
                (h-2*pad)/span_z if span_z else math.inf)
    require(math.isfinite(scale) and scale > 0, "degenerate map extent")

    def screen(pos):
        return [w/2+(pos[0]-cx)*scale, h/2-(pos[2]-cz)*scale]

    blocked = set(plan["blockedEdges"])
    selected = set(plan["edges"])
    edges = [{"id": e.id, "from": screen(graph.nodes[e.source].xyz),
              "to": screen(graph.nodes[e.target].xyz),
              "role": "route" if e.id in selected else "blocked" if e.id in blocked else "network"}
             for e in sorted(graph.edges.values(), key=lambda e: e.id)]
    # Highlight the route last; opposing authored arrows remain distinct
    # in the data even where the small canvas makes their lines overlap.
    edges.sort(key=lambda e: {"network": 0, "blocked": 1, "route": 2}[e["role"]])
    nodes = []
    path_nodes = set(plan["nodes"])
    for node in sorted(graph.nodes.values(), key=lambda n: n.id):
        role = ("start-goal" if node.id == plan["startNode"] == plan["destinationNode"]
                else "start" if node.id == plan["startNode"]
                else "goal" if node.id == plan["destinationNode"]
                else "route" if node.id in path_nodes else "network")
        nodes.append({"id": node.id, "position": screen(node.xyz), "kind": node.kind,
                      "role": role})
    return {"width": w, "height": h, "scale": scale, "edges": edges, "nodes": nodes,
            "status": plan["status"], "classification": "SYNTHETIC_MODEL_ONLY"}


def load_local_map(path, expected_sha256=None):
    """Reuse the existing bounded map parser and optional exact external pin."""
    if path is None:
        require(expected_sha256 is None, "map pin requires an explicit file")
        return demo_graph()
    raw = _read_bounded(Path(path), MAX_GRAPH_BYTES, "local graph")
    if expected_sha256 is not None:
        require(isinstance(expected_sha256, str)
                and re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256)
                and hashlib.sha256(raw).hexdigest() == expected_sha256.lower(),
                "map SHA mismatch")
    return decode_graph(raw)


def launch(graph):
    """Create the local synthetic route preview and model playback UI."""
    require(graph.classification == "SYNTHETIC_MODEL_ONLY", "desktop preview requires a synthetic graph")
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("RIFT Taxi | Local synthetic route preview")
    root.geometry("1020x650")
    root.minsize(660, 440)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)
    panel = ttk.Frame(root, padding=12)
    panel.grid(row=0, column=0, sticky="ns")
    panel.columnconfigure(0, weight=1)
    ttk.Label(panel, text="RIFT Taxi", font=("Segoe UI", 16, "bold")).grid(sticky="w")
    ttk.Label(panel, text="Synthetic preview only").grid(sticky="w", pady=(0,12))

    node_ids = sorted(graph.nodes)
    dest_ids = sorted(graph.destinations)
    edge_ids = sorted(graph.edges)
    mode = tk.StringVar(value="node")
    node = tk.StringVar(value=node_ids[0])
    edge = tk.StringVar(value=edge_ids[0])
    fraction = tk.StringVar(value="0.5")
    destination = tk.StringVar(value=dest_ids[0])
    ttk.Label(panel, text="Start mode").grid(sticky="w")
    ttk.Combobox(panel, textvariable=mode, values=("node", "directed edge"),
                 state="readonly", width=23).grid(sticky="ew", pady=(0,6))
    ttk.Label(panel, text="Start node").grid(sticky="w")
    node_box = ttk.Combobox(panel, textvariable=node, values=node_ids, state="readonly", width=23)
    node_box.grid(sticky="ew", pady=(0,6))
    ttk.Label(panel, text="Directed edge").grid(sticky="w")
    edge_box = ttk.Combobox(panel, textvariable=edge, values=edge_ids, state="disabled", width=23)
    edge_box.grid(sticky="ew", pady=(0,6))
    ttk.Label(panel, text="Interior fraction (0–1)").grid(sticky="w")
    fraction_box = ttk.Entry(panel, textvariable=fraction, state="disabled", width=23)
    fraction_box.grid(sticky="ew", pady=(0,6))
    ttk.Label(panel, text="Destination ID").grid(sticky="w")
    ttk.Combobox(panel, textvariable=destination, values=dest_ids,
                 state="readonly", width=23).grid(sticky="ew", pady=(0,8))
    ttk.Label(panel, text="Exclude directed edges").grid(sticky="w")
    blocked = tk.Listbox(panel, selectmode="multiple", exportselection=False,
                         height=6, width=27)
    blocked.grid(sticky="ew")
    for edge_id in edge_ids:
        blocked.insert("end", edge_id)
    status = tk.StringVar(value="Choose a start and destination.")
    canvas = tk.Canvas(root, background="#121b27", highlightthickness=0)
    canvas.grid(row=0, column=1, sticky="nsew")
    current = None

    def draw():
        canvas.delete("all")
        if current is None or canvas.winfo_width() < 80 or canvas.winfo_height() < 80:
            return
        g, plan = current
        scene = build_scene(g, plan, width=canvas.winfo_width(), height=canvas.winfo_height())
        edge_colors = {"network": "#627387", "blocked": "#ef7777", "route": "#5bd6a2"}
        for item in scene["edges"]:
            role = item["role"]
            canvas.create_line(*item["from"], *item["to"], arrow=tk.LAST,
                               fill=edge_colors[role], width=3 if role == "route" else 1,
                               dash=(5,4) if role == "blocked" else ())
        node_colors = {"network": "#91a4bb", "route": "#5bd6a2", "start": "#70b4ff",
                       "goal": "#ffd477", "start-goal": "#ffd477"}
        for item in scene["nodes"]:
            x, y = item["position"]
            radius = 5 if item["role"] != "network" else 3
            color = node_colors[item["role"]]
            if item["kind"] == "hard_stop":
                canvas.create_rectangle(x-radius,y-radius,x+radius,y+radius,fill=color,outline="")
            else:
                canvas.create_oval(x-radius,y-radius,x+radius,y+radius,fill=color,outline="")
            canvas.create_text(x+7,y-9,text=item["id"],anchor="sw",fill="#e5ecf5",
                               font=("Segoe UI",8))
        canvas.create_text(12,12,anchor="nw",fill="#dce5f0",
                           text="XZ plan • +Z up • green: route • red: excluded")
        canvas.create_text(12,canvas.winfo_height()-12,anchor="sw",fill="#dce5f0",
                           text="Synthetic graph only • no game movement")

    def refresh(*_):
        nonlocal current
        edge_mode = mode.get() == "directed edge"
        node_box.configure(state="disabled" if edge_mode else "readonly")
        edge_box.configure(state="readonly" if edge_mode else "disabled")
        fraction_box.configure(state="normal" if edge_mode else "disabled")
        try:
            excluded = [edge_ids[i] for i in blocked.curselection()]
            current = preview(graph, destination=destination.get(),
                              start=None if edge_mode else node.get(),
                              edge_id=edge.get() if edge_mode else None,
                              fraction=float(fraction.get()) if edge_mode else None,
                              blocked_edges=excluded)
            plan = current[1]
            distance = plan["distance"]
            detail = "No route" if distance is None else f"{distance:.3f} synthetic units"
            status.set(f"{plan['destinationLabel']}\n{plan['status']}\n{detail}")
        except (TraceError, ValueError, OverflowError) as exc:
            current = None
            status.set(str(exc))
        draw()

    def model_journey():
        # Refresh from all current inputs, not a previously displayed plan.
        refresh()
        if current is None:
            return
        g, plan = current
        from .local_journey_viewer import journey_samples, launch_playback
        try:
            receipt, samples = journey_samples(g, plan)
            launch_playback(root,g,plan,receipt=receipt,samples=samples)
        except (TraceError,ValueError,OverflowError) as exc:
            status.set("Model journey refused: "+str(exc))

    ttk.Button(panel, text="Preview route", command=refresh).grid(sticky="ew", pady=(10,4))
    ttk.Button(panel, text="Replay model journey", command=model_journey).grid(sticky="ew", pady=(0,8))
    ttk.Label(panel, textvariable=status, wraplength=225, justify="left").grid(sticky="w")
    canvas.bind("<Configure>", lambda _: draw())
    mode.trace_add("write", refresh)
    root.after_idle(refresh)
    root.mainloop()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--map", type=Path)
    p.add_argument("--map-sha256")
    a = p.parse_args(argv)
    try:
        graph = load_local_map(a.map, a.map_sha256)
        try:
            import tkinter as tk
        except ImportError:
            p.exit(2, "Local Taxi viewer requires Python with Tk support.\n")
        try:
            launch(graph)
        except tk.TclError as exc:
            p.exit(2, f"Local Taxi viewer could not open a desktop: {exc}\n")
        return 0
    except (TraceError, OSError, ValueError, OverflowError, RecursionError) as exc:
        p.exit(2, f"Local Taxi viewer refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
