"""User-facing offline Taxi launcher.

One desktop entry point opens either existing viewer. A world catalog must
be selected explicitly and accompanied by its expected byte SHA-256. The
launcher lists only validated catalog route IDs; the selected anchor is
reopened through the existing world-graph admission boundary before launch.
No network, live client access, input, or implicit coordinate conversion.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .contracts import TraceError
from .local_taxi import demo_graph
from .local_taxi_gui import launch as launch_demo
from .world_route_catalog import _catalog
from .world_route_graph import load_world_graph
from .world_route_viewer import launch as launch_world


def catalog_choices(path, expected_sha256):
    """Read a pinned catalog inventory, not the packages or their authority.

    The caller must still load the selected world graph, which independently
    verifies the original package pins and source scope. Never calculate a
    new expected pin from an unknown catalog merely to make it load.
    """
    _, rows = _catalog(Path(path), expected_sha256)
    return tuple({"routeId": row["routeId"], "destinationId": row["destinationId"],
                  "sourceWorld": row["sourceWorld"]}
                 for row in sorted(rows, key=lambda item: item["routeId"]))


def choose():
    """Return an explicitly selected (mode, graph) or None on window close."""
    import tkinter as tk
    from tkinter import ttk, filedialog

    root = tk.Tk()
    root.title("RIFT Taxi | Local application")
    root.geometry("680x440")
    root.minsize(570,420)
    panel = ttk.Frame(root,padding=20)
    panel.pack(fill="both",expand=True)
    panel.columnconfigure(0,weight=1)
    ttk.Label(panel,text="RIFT Taxi",font=("Segoe UI",20,"bold")).grid(row=0,column=0,sticky="w")
    ttk.Label(panel,text="Standalone offline route planning and review").grid(row=1,column=0,sticky="w")
    selected = None
    path = tk.StringVar()
    pin = tk.StringVar()
    anchor = tk.StringVar()
    status = tk.StringVar(value="Choose the synthetic demo or a pinned local world catalog.")
    choices = {}

    def open_demo():
        nonlocal selected
        selected = ("demo",demo_graph())
        root.destroy()

    ttk.Button(panel,text="Open synthetic demo",command=open_demo).grid(row=2,column=0,sticky="ew",pady=(12,10))
    ttk.Separator(panel).grid(row=3,column=0,sticky="ew",pady=4)
    ttk.Label(panel,text="Imported world catalog (review only)").grid(row=4,column=0,sticky="w")
    path_row=ttk.Frame(panel)
    path_row.grid(row=5,column=0,sticky="ew",pady=(3,7))
    path_row.columnconfigure(0,weight=1)
    ttk.Entry(path_row,textvariable=path).grid(row=0,column=0,sticky="ew")

    def browse():
        chosen = filedialog.askopenfilename(parent=root,title="Choose local world catalog",
                                           filetypes=[("JSON catalogs","*.json"),("All files","*")])
        if chosen:
            path.set(chosen)

    ttk.Button(path_row,text="Browse",command=browse).grid(row=0,column=1,padx=(6,0))
    ttk.Label(panel,text="Expected catalog SHA-256").grid(row=6,column=0,sticky="w")
    ttk.Entry(panel,textvariable=pin).grid(row=7,column=0,sticky="ew",pady=(3,8))
    ttk.Label(panel,text="Anchor route").grid(row=9,column=0,sticky="w")
    anchor_box=ttk.Combobox(panel,textvariable=anchor,state="readonly")
    anchor_box.grid(row=10,column=0,sticky="ew",pady=(3,5))

    def invalidate(*_):
        # Path or pin edits invalidate every earlier inventory selection.
        choices.clear()
        anchor.set("")
        anchor_box.configure(values=())
        world_button.configure(state="disabled")
        status.set("Catalog inputs changed; inspect the catalog again.")

    def inspect():
        invalidate()
        try:
            rows = catalog_choices(path.get(),pin.get().strip())
        except (TraceError,OSError,ValueError,RecursionError) as exc:
            status.set("Catalog refused: "+str(exc))
            return
        for row in rows:
            choices[row["routeId"]] = row
        anchor_box.configure(values=tuple(choices))
        status.set(f"{len(choices)} catalog routes. Select an anchor explicitly; packages will be checked on open.")

    def select_anchor(*_):
        if anchor.get() in choices:
            row=choices[anchor.get()]
            status.set(f"{row['sourceWorld']} | {row['destinationId']} | review only")
            world_button.configure(state="normal")
        else:
            world_button.configure(state="disabled")

    def open_world():
        nonlocal selected
        if anchor.get() not in choices:
            return
        try:
            world=load_world_graph(Path(path.get()),catalog_sha256=pin.get().strip(),
                                   anchor_route=anchor.get())
        except (TraceError,OSError,ValueError,OverflowError,RecursionError) as exc:
            status.set("World packages refused: "+str(exc))
            return
        selected=("world",world)
        root.destroy()

    ttk.Button(panel,text="Inspect catalog",command=inspect).grid(row=8,column=0,sticky="ew",pady=(0,7))
    world_button=ttk.Button(panel,text="Open world viewer",command=open_world,state="disabled")
    world_button.grid(row=11,column=0,sticky="ew",pady=(3,8))
    ttk.Label(panel,textvariable=status,wraplength=600).grid(row=12,column=0,sticky="w")
    path.trace_add("write",invalidate)
    pin.trace_add("write",invalidate)
    anchor_box.bind("<<ComboboxSelected>>",select_anchor)
    root.mainloop()
    return selected


def main(argv=None):
    parser=argparse.ArgumentParser(prog="rift-taxi-app",description=__doc__)
    commands=parser.add_subparsers(dest="mode")
    commands.add_parser("demo",help="open the bundled synthetic route viewer")
    world=commands.add_parser("world",help="open a pinned imported-world viewer")
    world.add_argument("catalog",type=Path)
    world.add_argument("--catalog-sha256",required=True)
    world.add_argument("--anchor-route",required=True)
    args=parser.parse_args(argv)
    try:
        import tkinter as tk
    except ImportError:
        parser.exit(2,"RIFT Taxi app requires Python with Tk support.\n")
    try:
        if args.mode == "demo":
            launch_demo(demo_graph())
        elif args.mode == "world":
            launch_world(load_world_graph(args.catalog,catalog_sha256=args.catalog_sha256,
                                          anchor_route=args.anchor_route))
        else:
            selection=choose()
            if selection is not None:
                mode,graph=selection
                (launch_demo if mode=="demo" else launch_world)(graph)
        return 0
    except (TraceError,OSError,ValueError,OverflowError,RecursionError,tk.TclError) as exc:
        parser.exit(2,f"RIFT Taxi app refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
