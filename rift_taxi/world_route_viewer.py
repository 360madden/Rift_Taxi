"""Offline graphical preview of a pinned imported-world route network.

Use existing local vertex A* for all selections. XZ is a projection only;
Y is retained in an elevation profile and endpoint receipts. Nothing in this
module transforms coordinates, joins paths, certifies clearance, or sends input.
Headless SVG export uses only the Python standard library; optional Tk desktop
preview reuses that same scene data. No network or game process access.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from .contracts import TraceError, _number
from .world_candidate_review import require
from .world_route_graph import CLASSIFICATION, load_world_graph, plan_world_route, review_position

COLORS = {"network": "#65788d", "blocked": "#ed7777", "route": "#54d6a1",
          "start": "#70b4ff", "goal": "#ffd477", "start-goal": "#ffd477"}


def search_destinations(world, query=""):
    """Return stable route IDs matching all case-insensitive search words.

    Match catalog destination labels and route IDs. Do not coalesce aliases
    or substitute a different snapped endpoint when filtering.
    """
    require(isinstance(query, str) and len(query) <= 256, "invalid destination search")
    terms = query.casefold().split()
    return [key for key in sorted(world.routes)
            if all(term in (key + " " + world.routes[key]["destinationId"]).casefold()
                   for term in terms)]


def review_scene(world, *, start, destination, blocked_edges=(), width=900, height=600):
    """Plan locally and build aspect-correct XZ and cumulative-distance/Y scenes.

    Projection does not merge coincident vertices. A vertical-only edge has
    zero projected XZ length but still exists in the plan/elevation profile.
    Full source XYZ remains in scene nodes; source units are not meters.
    """
    graph = world.graph
    require(graph.classification == CLASSIFICATION, "review graph required")
    w, h = _number(width, "width"), _number(height, "height")
    require(320 <= w <= 4000 and 280 <= h <= 4000, "invalid review canvas size")
    plan = plan_world_route(world, start=start, destination=destination,
                            blocked_edges=blocked_edges)
    require(plan["classification"] == CLASSIFICATION, "review plan required")
    positions = [n.xyz for n in graph.nodes.values()]
    require(bool(positions), "empty review graph")
    xs, zs = [p[0] for p in positions], [p[2] for p in positions]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    top, bottom = 76., h*.64
    span_x, span_z = x1-x0, z1-z0
    scale = min((w-80)/span_x if span_x else math.inf,
                (bottom-top-24)/span_z if span_z else math.inf)
    if not math.isfinite(scale):
        scale = 1.  # Entire graph may be vertical in source coordinates.

    def project(pos):
        return [w/2 + (pos[0]-(x0+x1)/2)*scale,
                (top+bottom)/2 - (pos[2]-(z0+z1)/2)*scale]

    selected, blocked = set(plan["edges"]), set(plan["blockedEdges"])
    edges = [{"id": edge.id, "from": project(graph.nodes[edge.source].xyz),
              "to": project(graph.nodes[edge.target].xyz),
              "role": "route" if edge.id in selected else "blocked" if edge.id in blocked else "network"}
             for edge in sorted(graph.edges.values(), key=lambda item: item.id)]
    edges.sort(key=lambda item: {"network":0,"blocked":1,"route":2}[item["role"]])
    nodes = []
    for node in sorted(graph.nodes.values(), key=lambda item: item.id):
        role = ("start-goal" if node.id == plan["startNode"] == plan["destinationNode"]
                else "start" if node.id == plan["startNode"]
                else "goal" if node.id == plan["destinationNode"] else "network")
        nodes.append({"id":node.id, "xyz":list(node.xyz), "screen":project(node.xyz), "role":role})
    profile = []
    travelled = 0.
    for point in plan["points"]:
        if profile:
            travelled += math.dist(profile[-1]["xyz"], point["xyz"])
        profile.append({"distance":travelled, "xyz":point["xyz"]})
    if profile:
        ymin, ymax = min(p["xyz"][1] for p in profile), max(p["xyz"][1] for p in profile)
        for p in profile:
            p["screen"] = [40+(w-80)*p["distance"]/travelled if travelled else w/2,
                           h-35-(h-bottom-65)*(p["xyz"][1]-ymin)/(ymax-ymin)
                           if ymax != ymin else (bottom+h)/2]
    return {"width":w,"height":h,"mapBottom":bottom,"plan":plan,"edges":edges,
            "nodes":nodes,"profile":profile,"classification":CLASSIFICATION}


def map_pick(scene, x, y, *, radius=7.):
    """Resolve a map click to a single existing graph node, never a new point.

    Coordinates and radius are canvas pixels, not world units. All distinct
    nodes inside the click radius are candidates; overlapping floors or
    nearby vertices remain ambiguous rather than selecting the nearest one.
    The elevation profile and header are not interactive map areas.
    """
    require(scene.get("classification") == CLASSIFICATION, "review scene required")
    x, y, radius = (_number(v, name) for v, name in
                    ((x, "click X"), (y, "click Y"), (radius, "pick radius")))
    require(1 <= radius <= 20, "invalid pick radius")
    if not (0 <= x <= scene["width"] and 76 <= y <= scene["mapBottom"]):
        return {"status":"outside-map", "nodeId":None, "candidates":[]}
    candidates = sorted(n["id"] for n in scene["nodes"]
                        if math.hypot(x-n["screen"][0],y-n["screen"][1]) <= radius)
    if len(candidates) == 1:
        return {"status":"selected", "nodeId":candidates[0], "candidates":candidates}
    return {"status":"ambiguous" if candidates else "no-node",
            "nodeId":None, "candidates":candidates}


def scene_svg(scene):
    """Render a self-contained SVG. XML serialization escapes all source text.

    No script, hyperlink, embedded asset or external resource is emitted.
    Each drawn route is a review projection, not a navigable map certificate.
    """
    w,h = scene["width"],scene["height"]
    svg = ET.Element("svg", {"xmlns":"http://www.w3.org/2000/svg","viewBox":f"0 0 {w} {h}"})
    def add(tag, **attrs):
        return ET.SubElement(svg,tag,{key.replace("_","-"):str(value) for key,value in attrs.items()})
    def label(x,y,value,size=13,color="#dce5f0"):
        add("text",x=x,y=y,fill=color,font_size=size,font_family="sans-serif").text=str(value)
    def line(a,b,color,width=1,dash=None):
        attrs=dict(x1=a[0],y1=a[1],x2=b[0],y2=b[1],stroke=color,stroke_width=width)
        if dash:
            attrs["stroke_dasharray"]=dash
        add("line",**attrs)
    add("rect",width=w,height=h,fill="#121b27")
    label(18,25,"RIFT Taxi | Imported world review",19)
    label(18,47,"OFFLINE REVIEW ONLY - no clearance or movement authority",12,"#ffd477")
    plan=scene["plan"]
    label(18,65,f"{plan['status']} | {plan['destinationLabel']} | distance: {plan['distance']}",12)
    for e in scene["edges"]:
        line(e["from"],e["to"],COLORS[e["role"]],3 if e["role"]=="route" else 1,
             "5 4" if e["role"]=="blocked" else None)
    for n in scene["nodes"]:
        x,y=n["screen"]
        add("circle",cx=x,cy=y,r=5 if n["role"]!="network" else 2,fill=COLORS[n["role"]])
        if n["role"]!="network":
            label(x+8,y-8,n["role"]+" "+n["id"],11)
    bottom=scene["mapBottom"]
    line([18,bottom],[w-18,bottom],"#344357")
    label(18,bottom+19,"Elevation profile | source Y vs. cumulative 3D distance",12)
    for a,b in zip(scene["profile"],scene["profile"][1:]):
        line(a["screen"],b["screen"],COLORS["route"],2)
    for p in scene["profile"]:
        add("circle",cx=p["screen"][0],cy=p["screen"][1],r=2,fill=COLORS["route"])
    label(18,h-12,"XZ projection (+Z up); source units; junctions and endpoint connectors unverified",11)
    return ET.tostring(svg,encoding="unicode")


def position_review_dialog(parent, world, initial_alias, on_select):
    """Inspect source XYZ and explicitly select an existing review vertex.

    Keep the supplied coordinate separate from the route start. Segment
    projections are informational only. Editing any field invalidates the
    result and prevents a stale candidate from being applied. No game access.
    """
    import tkinter as tk
    from tkinter import ttk
    dialog = tk.Toplevel(parent)
    dialog.title("RIFT Taxi | Source position review")
    dialog.geometry("740x540")
    dialog.minsize(570,450)
    dialog.transient(parent)
    panel = ttk.Frame(dialog,padding=12)
    panel.pack(fill="both",expand=True)
    panel.columnconfigure(0,weight=1)
    panel.columnconfigure(1,weight=1)
    panel.rowconfigure(4,weight=1)
    initial = world.graph.nodes[world.aliases[initial_alias]].xyz
    fields = [tk.StringVar(master=dialog,value=str(v)) for v in (*initial,.5,.5)]
    inputs = ttk.Frame(panel)
    inputs.grid(row=0,column=0,columnspan=2,sticky="ew")
    for i,(label,var) in enumerate(zip(("X","Y","Z","Max XZ","Max Y"),fields)):
        inputs.columnconfigure(i,weight=1)
        ttk.Label(inputs,text=label).grid(row=0,column=i,sticky="w",padx=3)
        ttk.Entry(inputs,textvariable=var,width=14).grid(row=1,column=i,sticky="ew",padx=3)
    ttk.Label(panel,text="Source coordinates only; review candidates are not verified movement connectors.",
              wraplength=680).grid(row=1,column=0,columnspan=2,sticky="w",pady=(8,4))
    status = tk.StringVar(master=dialog,value="Enter source coordinates and inspect nearby geometry.")
    ttk.Label(panel,textvariable=status,wraplength=680).grid(row=2,column=0,columnspan=2,sticky="w")
    ttk.Label(panel,text="Existing vertices (selectable)").grid(row=3,column=0,sticky="w")
    ttk.Label(panel,text="Segment projections (review only)").grid(row=3,column=1,sticky="w")
    vertices = tk.Listbox(panel,exportselection=False,height=10,width=35)
    segments = tk.Listbox(panel,exportselection=False,height=10,width=35)
    vertices.grid(row=4,column=0,sticky="nsew",padx=(0,4))
    segments.grid(row=4,column=1,sticky="nsew",padx=(4,0))
    result = None

    def invalidate(*_):
        nonlocal result
        result = None
        vertices.delete(0,"end")
        segments.delete(0,"end")
        apply.configure(state="disabled")
        status.set("Inputs changed; inspect again.")

    def inspect():
        nonlocal result
        invalidate()
        try:
            x,y,z,h,v = (float(field.get()) for field in fields)
            result = review_position(world,position=[x,y,z],max_xz=h,max_y=v)
        except (TraceError,ValueError,OverflowError) as exc:
            status.set("Invalid position or limits: " + str(exc))
            return
        for row in result["vertices"]:
            vertices.insert("end",f"{row['nodeId']} | XZ {row['distanceXZ']:.4g} | Y {row['distanceY']:.4g}")
        for row in result["segments"]:
            segments.insert("end",f"{row['edgeId']} | t {row['fraction']:.3f} | XZ {row['distanceXZ']:.4g} | Y {row['distanceY']:.4g}")
        status.set(f"Vertices: {len(result['vertices'])}/{result['vertexCount']} | "
                   f"Segments: {len(result['segments'])}/{result['segmentCount']} | "
                   f"Exact nodes: {len(result['exactNodeIds'])}. Choose a vertex explicitly.")

    def selection_changed(*_):
        apply.configure(state="normal" if result is not None and len(vertices.curselection())==1
                        else "disabled")

    def apply_vertex():
        selected = vertices.curselection()
        if result is None or len(selected)!=1:
            return
        node_id = result["vertices"][selected[0]]["nodeId"]
        if node_id not in world.aliases:
            status.set("Select a source from the main list.")
            return
        # Only select a graph vertex after deliberate confirmation; never
        # use a segment projection or the supplied XYZ as a start.
        on_select(node_id)
        dialog.destroy()

    controls = ttk.Frame(panel)
    controls.grid(row=5,column=0,columnspan=2,sticky="ew",pady=(8,0))
    ttk.Button(controls,text="Inspect position",command=inspect).pack(side="left")
    apply = ttk.Button(controls,text="Use selected vertex",command=apply_vertex,state="disabled")
    apply.pack(side="left",padx=8)
    ttk.Button(controls,text="Close",command=dialog.destroy).pack(side="right")
    vertices.bind("<<ListboxSelect>>",selection_changed)
    for field in fields:
        field.trace_add("write",invalidate)
    return dialog


def launch(world):
    """Optional local desktop preview; never opens a game process."""
    import tkinter as tk
    from tkinter import ttk
    root=tk.Tk()
    root.title("RIFT Taxi | Imported world review only")
    root.geometry("1080x720")
    root.minsize(720,440)
    root.columnconfigure(1,weight=1)
    root.rowconfigure(0,weight=1)
    panel=ttk.Frame(root,padding=12)
    panel.grid(row=0,column=0,sticky="ns")
    aliases=sorted(world.aliases)
    destinations=search_destinations(world)
    edge_ids=sorted(world.graph.edges)
    start=tk.StringVar(value=aliases[0])
    destination=tk.StringVar(value=destinations[0])
    status=tk.StringVar(value="Choose a route.")
    query=tk.StringVar()
    search_status=tk.StringVar(value=f"{len(destinations)} destinations")
    ttk.Label(panel,text="Source point").pack(anchor="w")
    source_box=ttk.Combobox(panel,textvariable=start,values=aliases,state="readonly",width=28)
    source_box.pack(fill="x",pady=(0,8))
    ttk.Label(panel,text="Find destination").pack(anchor="w")
    search_box=ttk.Entry(panel,textvariable=query,width=28)
    search_box.pack(fill="x",pady=(0,4))
    ttk.Label(panel,textvariable=search_status).pack(anchor="w")
    ttk.Label(panel,text="Route destination ID").pack(anchor="w")
    destination_box=ttk.Combobox(panel,textvariable=destination,values=destinations,state="readonly",width=28)
    destination_box.pack(fill="x",pady=(0,8))
    ttk.Label(panel,text="Exclude source edges").pack(anchor="w")
    excluded=tk.Listbox(panel,selectmode="multiple",exportselection=False,height=10,width=30)
    excluded.pack(fill="x")
    for edge_id in edge_ids:
        excluded.insert("end",edge_id)
    canvas=tk.Canvas(root,background="#121b27",highlightthickness=0)
    canvas.grid(row=0,column=1,sticky="nsew")
    current_scene = None
    pick_status = tk.StringVar(value="Click a map vertex to select the source.")
    ttk.Label(panel,textvariable=pick_status,wraplength=230).pack(anchor="w")

    def draw(*_):
        nonlocal current_scene
        # Invalidate the previous hit-test geometry before every redraw.
        current_scene = None
        canvas.delete("all")
        w,h=canvas.winfo_width(),canvas.winfo_height()
        if w<320 or h<280:
            return
        if not destination.get():
            status.set("Select a matching destination.")
            return
        try:
            scene=review_scene(world,start=start.get(),destination=destination.get(),
                               blocked_edges=[edge_ids[i] for i in excluded.curselection()],
                               width=w,height=h)
            plan=scene["plan"]
            offset=plan["destinationSource"]["endpointOffsets"]["goal"]
            status.set(f"{plan['status']}\nDistance: {plan['distance']} source units\nGoal snap XZ: {offset['horizontalXZ']:.4g}\nGoal snap Y: {offset['verticalY']:.4g}\nReview only")
            canvas.create_text(16,14,text="OFFLINE REVIEW ONLY",fill="#ffd477",anchor="nw",font=("Segoe UI",14,"bold"))
            canvas.create_text(16,46,text="XZ projection (+Z up)",fill="#dce5f0",anchor="nw")
            for e in scene["edges"]:
                canvas.create_line(*e["from"],*e["to"],fill=COLORS[e["role"]],
                                   width=3 if e["role"]=="route" else 1)
            for n in scene["nodes"]:
                x,y=n["screen"]
                r=5 if n["role"]!="network" else 2
                canvas.create_oval(x-r,y-r,x+r,y+r,fill=COLORS[n["role"]],outline="")
                if n["role"]!="network":
                    canvas.create_text(x+8,y-8,text=n["role"]+" "+n["id"],fill="#dce5f0",anchor="sw")
            bottom=scene["mapBottom"]
            canvas.create_line(16,bottom,w-16,bottom,fill="#344357")
            canvas.create_text(16,bottom+6,text="Elevation profile: source Y",fill="#dce5f0",anchor="nw")
            for a,b in zip(scene["profile"],scene["profile"][1:]):
                canvas.create_line(*a["screen"],*b["screen"],fill=COLORS["route"],width=2)
            current_scene = scene
        except (TraceError,ValueError,OverflowError) as exc:
            status.set(str(exc))
    def select_reviewed_vertex(alias):
        start.set(alias)
        pick_status.set("Explicit review source: " + alias)
        draw()

    ttk.Button(panel,text="Review XYZ position",command=lambda: position_review_dialog(
        root,world,start.get(),select_reviewed_vertex)).pack(fill="x",pady=(8,0))
    ttk.Button(panel,text="Preview route",command=draw).pack(fill="x",pady=10)
    ttk.Label(panel,textvariable=status,wraplength=230,justify="left").pack(anchor="w")
    def filter_destinations(*_):
        # Keep an existing selection only when it survives the filter.
        # Never silently choose a different destination or display a stale route.
        try:
            matches=search_destinations(world,query.get())
        except TraceError:
            matches=[]
        destination_box.configure(values=matches)
        search_status.set(f"{len(matches)} of {len(destinations)} destinations")
        if destination.get() not in matches:
            destination.set("")
        draw()

    # A new explicit selection or exclusion recomputes the route immediately.
    # The Preview button remains available as a deliberate repeat operation.
    query.trace_add("write",filter_destinations)
    source_box.bind("<<ComboboxSelected>>",draw)
    destination_box.bind("<<ComboboxSelected>>",draw)
    excluded.bind("<<ListboxSelect>>",draw)
    def pick_source(event):
        # A screen-space click only chooses an authored source vertex.
        # There is no continuous-position connector or physical admission.
        if current_scene is None:
            return
        result = map_pick(current_scene, event.x, event.y)
        if result["status"] == "selected":
            alias = result["nodeId"]
            if alias not in world.aliases:
                pick_status.set("Select an explicit source from the list.")
                return
            start.set(alias)
            pick_status.set("Selected source: " + alias)
            draw()
        elif result["status"] == "ambiguous":
            pick_status.set("Overlapping vertices; choose the exact source from the list.")
        else:
            pick_status.set("No source vertex selected.")

    canvas.bind("<Button-1>",pick_source)
    canvas.bind("<Configure>",draw)
    root.after_idle(draw)
    root.mainloop()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("catalog",type=Path)
    p.add_argument("--catalog-sha256",required=True)
    p.add_argument("--anchor-route",required=True)
    sub=p.add_subparsers(dest="operation",required=True)
    sub.add_parser("desktop")
    export=sub.add_parser("svg")
    export.add_argument("--start",required=True)
    export.add_argument("--destination",required=True)
    export.add_argument("--blocked-edge",action="append",default=[])
    export.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        world=load_world_graph(args.catalog,catalog_sha256=args.catalog_sha256,anchor_route=args.anchor_route)
        if args.operation=="desktop":
            try:
                import tkinter as tk
            except ImportError:
                p.exit(2,"Imported world viewer requires Tk for desktop mode.\n")
            try:
                launch(world)
            except tk.TclError as exc:
                p.exit(2,f"Desktop unavailable: {exc}\n")
            return 0
        scene=review_scene(world,start=args.start,destination=args.destination,blocked_edges=args.blocked_edge)
        with args.out.open("x",encoding="utf-8",newline="\n") as stream:
            stream.write(scene_svg(scene)+"\n")
        return 1 if scene["plan"]["status"]=="no-route" else 0
    except (TraceError,OSError,ValueError,OverflowError,RecursionError) as exc:
        p.exit(2,f"Imported world viewer refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
