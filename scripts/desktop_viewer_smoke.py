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

from rift_taxi.app import choose
from rift_taxi.local_taxi import demo_graph
from rift_taxi.local_taxi_gui import launch as launch_synthetic
from rift_taxi.world_route_graph import load_world_graph
from rift_taxi.world_route_viewer import launch as launch_world
from rift_taxi.world_route_viewer import review_scene, map_pick


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
            model_replay_checked = False
            if world_route is None:
                # Run the actual local synthetic model through the production
                # button, then exercise replay, pause, scrub and close without
                # issuing OS input or replacing the renderer.
                import time
                buttons = [w for w in children if isinstance(w,ttk.Button)
                           and w.cget("text")=="Replay model journey"]
                if len(buttons)!=1:
                    raise RuntimeError("missing model journey control")
                buttons[0].invoke()
                root.update()
                dialogs = [w for w in root.winfo_children() if isinstance(w,tk.Toplevel)]
                if len(dialogs)!=1:
                    raise RuntimeError("missing model replay dialog")
                dialog=dialogs[0]
                widgets=list(descendants(dialog))
                sliders=[w for w in widgets if isinstance(w,tk.Scale)]
                replay_canvases=[w for w in widgets if isinstance(w,tk.Canvas)]
                actions={w.cget("text"):w for w in widgets if isinstance(w,ttk.Button)}
                if len(sliders)!=1 or len(replay_canvases)!=1:
                    raise RuntimeError("unexpected model replay controls")
                slider, replay_canvas=sliders[0],replay_canvases[0]
                if int(slider.cget("to"))<2 or not replay_canvas.find_withtag("model-pose"):
                    raise RuntimeError("model replay did not render")
                initial=replay_canvas.coords(replay_canvas.find_withtag("model-pose")[0])
                static_items=replay_canvas.find_withtag("network")
                if not static_items:
                    raise RuntimeError("missing cached network")
                actions["Play"].invoke()
                deadline=time.monotonic()+1.0
                while slider.get()==0 and time.monotonic()<deadline:
                    root.update()
                    time.sleep(.01)
                if slider.get()==0 or actions["Play"].cget("text")!="Pause":
                    raise RuntimeError("model replay timer did not advance")
                actions["Play"].invoke()
                stopped=slider.get()
                deadline=time.monotonic()+.2
                while time.monotonic()<deadline:
                    root.update()
                    time.sleep(.01)
                if slider.get()!=stopped or actions["Play"].cget("text")!="Play":
                    raise RuntimeError("paused replay advanced")
                slider.set(int(slider.cget("to")))
                root.update()
                marker=replay_canvas.coords(replay_canvas.find_withtag("model-pose")[0])
                if marker==initial or not any("model-arrived" in str(w.cget("text"))
                           for w in widgets if isinstance(w,ttk.Label)):
                    raise RuntimeError("model replay terminal state missing")
                if replay_canvas.find_withtag("network")!=static_items:
                    raise RuntimeError("timeline scrub rebuilt the static network")
                # Restart at the terminal state, then replace the running
                # dialog with a fresh receipt and ensure old timers are gone.
                actions["Play"].invoke()
                if slider.get()!=0 or actions["Play"].cget("text")!="Pause":
                    raise RuntimeError("terminal replay did not restart")
                buttons[0].invoke()
                root.update()
                if dialog.winfo_exists():
                    raise RuntimeError("repeated request retained old replay")
                dialogs=[w for w in root.winfo_children() if isinstance(w,tk.Toplevel)]
                if len(dialogs)!=1:
                    raise RuntimeError("repeated request created duplicate dialogs")
                dialog=dialogs[0]
                widgets=list(descendants(dialog))
                actions={w.cget("text"):w for w in widgets if isinstance(w,ttk.Button)}
                actions["Play"].invoke()
                actions["Close"].invoke()
                # Pump the loop beyond the scheduled interval to detect
                # callbacks targeting destroyed widgets.
                deadline=time.monotonic()+.25
                while time.monotonic()<deadline:
                    root.update()
                    time.sleep(.01)
                if dialog.winfo_exists() or errors:
                    raise RuntimeError("active model replay failed to close cleanly")
                # No-route and already-at-destination must not start a timer
                # or display an invented arrival trajectory.
                exclusions=next(w for w in children if isinstance(w,tk.Listbox))
                exclusions.selection_set(0,"end")
                buttons[0].invoke()
                root.update()
                dialog=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
                widgets=list(descendants(dialog))
                actions={w.cget("text"):w for w in widgets if isinstance(w,ttk.Button)}
                if not actions["Play"].instate(["disabled"]) or not any(
                        "no-route" in str(w.cget("text")) for w in widgets if isinstance(w,ttk.Label)):
                    raise RuntimeError("no-route replay incorrectly enabled")
                actions["Close"].invoke()
                exclusions.selection_clear(0,"end")
                combos[1].set("bank")
                buttons[0].invoke()
                root.update()
                dialog=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
                widgets=list(descendants(dialog))
                actions={w.cget("text"):w for w in widgets if isinstance(w,ttk.Button)}
                if not actions["Play"].instate(["disabled"]) or not any(
                        "already-at-destination" in str(w.cget("text")) for w in widgets if isinstance(w,ttk.Label)):
                    raise RuntimeError("already-at-destination replay incorrectly enabled")
                actions["Close"].invoke()
                combos[1].set("entrance")
                # Immediately destroy a new dialog, even before its first
                # idle draw. This exercises the separate idle cancellation.
                buttons[0].invoke()
                dialog=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
                dialog.destroy()
                root.update()
                if errors:
                    raise RuntimeError("replay lifecycle callbacks failed: "+"; ".join(errors))
                model_replay_checked=True
            search_checked = False
            reachability_checked = False
            map_pick_checked = False
            position_review_checked = False
            if world_route is not None:
                entries = [w for w in children if isinstance(w, ttk.Entry)
                           and not isinstance(w, ttk.Combobox)]
                if len(entries) != 1:
                    raise RuntimeError("expected one destination search field")
                entry = entries[0]
                entry.insert(0, "__no_matching_route__")
                root.update()
                if combos[1].get() or canvas.find_all():
                    raise RuntimeError("unmatched search retained a stale route")
                entry.delete(0, "end")
                entry.insert(0, world_route.upper())
                root.update()
                if world_route not in combos[1].cget("values") or combos[1].get():
                    raise RuntimeError("search failed or silently selected a destination")
                combos[1].set(world_route)
                combos[1].event_generate("<<ComboboxSelected>>")
                root.update()
                if not any("route-found" in str(w.cget("text")) for w in children
                           if isinstance(w, ttk.Label)):
                    raise RuntimeError("explicit selection did not replan")
                exclusions = [w for w in children if isinstance(w, tk.Listbox)]
                if len(exclusions) != 1:
                    raise RuntimeError("expected one edge exclusion list")
                exclusions[0].selection_set(0, "end")
                exclusions[0].event_generate("<<ListboxSelect>>")
                root.update()
                if not any("no-route" in str(w.cget("text")) for w in children
                           if isinstance(w, ttk.Label)):
                    raise RuntimeError("edge exclusion did not replan")
                # Reachable-only must clear the blocked destination, then
                # restore the option without silently changing the selection.
                filters=[w for w in children if isinstance(w,ttk.Checkbutton)
                         and w.cget("text")=="Reachable destinations only"]
                if len(filters)!=1:
                    raise RuntimeError("missing reachable destination filter")
                filters[0].invoke()
                root.update()
                if combos[1].get() or world_route in combos[1].cget("values") or canvas.find_all():
                    raise RuntimeError("reachable filter retained blocked destination")
                exclusions[0].selection_clear(0, "end")
                exclusions[0].event_generate("<<ListboxSelect>>")
                root.update()
                if world_route not in combos[1].cget("values") or combos[1].get():
                    raise RuntimeError("reachability did not refresh or silently selected a destination")
                combos[1].set(world_route)
                combos[1].event_generate("<<ComboboxSelected>>")
                root.update()
                if not any("route-found" in str(w.cget("text")) for w in children
                           if isinstance(w, ttk.Label)):
                    raise RuntimeError("clearing exclusions did not restore route")
                filters[0].invoke()
                root.update()
                reachability_checked = True
                if errors:
                    raise RuntimeError("Tk callbacks failed: " + "; ".join(errors))
                search_checked = True
                # Exercise an actual canvas click in this application's Tk
                # event loop. Select a uniquely projected interior vertex on
                # the current route, then verify the existing source control.
                scene = review_scene(graph,start=world_route+":0",destination=world_route,
                                     width=canvas.winfo_width(),height=canvas.winfo_height())
                interior = set(scene["plan"]["nodes"][1:-1])
                target = next((n for n in scene["nodes"] if n["id"] in interior
                               and map_pick(scene,*[round(v) for v in n["screen"]])["nodeId"]==n["id"]),None)
                if target is None:
                    raise RuntimeError("no unique interior vertex for map smoke")
                x,y = [round(v) for v in target["screen"]]
                canvas.event_generate("<Button-1>",x=x,y=y)
                root.update()
                if combos[0].get()!=target["id"] or errors:
                    raise RuntimeError("map source selection failed")
                if not any("route-found" in str(w.cget("text")) for w in children
                           if isinstance(w,ttk.Label)):
                    raise RuntimeError("map selection did not replan")
                # Restore the original selection before recording the receipt.
                combos[0].set(world_route+":0")
                combos[0].event_generate("<<ComboboxSelected>>")
                root.update()
                if errors:
                    raise RuntimeError("Tk callbacks failed: " + "; ".join(errors))
                map_pick_checked = True
                # Open the production XYZ dialog and inspect a different
                # existing vertex. Nothing may select a source implicitly.
                review_buttons = [w for w in children if isinstance(w,ttk.Button)
                                  and w.cget("text")=="Review XYZ position"]
                if len(review_buttons)!=1:
                    raise RuntimeError("expected one position review button")
                review_buttons[0].invoke()
                root.update()
                dialogs = [w for w in root.winfo_children() if isinstance(w,tk.Toplevel)]
                if len(dialogs)!=1:
                    raise RuntimeError("expected one position review dialog")
                dialog = dialogs[0]
                widgets = list(descendants(dialog))
                fields = [w for w in widgets if isinstance(w,ttk.Entry)]
                lists = [w for w in widgets if isinstance(w,tk.Listbox)]
                actions = {w.cget("text"):w for w in widgets if isinstance(w,ttk.Button)}
                if len(fields)!=5 or len(lists)!=2:
                    raise RuntimeError("unexpected position review controls")
                def set_fields(values):
                    for field,value in zip(fields,values,strict=True):
                        field.delete(0,"end")
                        field.insert(0,str(value))
                set_fields([*target["xyz"],0,0])
                actions["Inspect position"].invoke()
                root.update()
                matches = [i for i in range(lists[0].size())
                           if lists[0].get(i).split(" | ")[0]==target["id"]]
                if len(matches)!=1 or combos[0].get()!=world_route+":0":
                    raise RuntimeError("position review missing candidate or changed source")
                lists[0].selection_set(matches[0])
                lists[0].event_generate("<<ListboxSelect>>")
                root.update()
                if actions["Use selected vertex"].instate(["disabled"]):
                    raise RuntimeError("explicit vertex selection unavailable")
                fields[0].insert("end","x")
                root.update()
                if not actions["Use selected vertex"].instate(["disabled"]) or lists[0].size():
                    raise RuntimeError("edited input retained stale review candidates")
                actions["Inspect position"].invoke()
                root.update()
                if lists[0].size() or not actions["Use selected vertex"].instate(["disabled"]):
                    raise RuntimeError("invalid position was accepted")
                set_fields([*target["xyz"],0,0])
                actions["Inspect position"].invoke()
                root.update()
                matches = [i for i in range(lists[0].size())
                           if lists[0].get(i).split(" | ")[0]==target["id"]]
                if len(matches)!=1:
                    raise RuntimeError("position review did not recover")
                lists[0].selection_set(matches[0])
                lists[0].event_generate("<<ListboxSelect>>")
                root.update()
                actions["Use selected vertex"].invoke()
                root.update()
                if combos[0].get()!=target["id"] or dialog.winfo_exists() or errors:
                    raise RuntimeError("explicit reviewed vertex did not apply")
                if not any("route-found" in str(w.cget("text")) for w in children
                           if isinstance(w,ttk.Label)):
                    raise RuntimeError("reviewed vertex did not replan")
                combos[0].set(world_route+":0")
                combos[0].event_generate("<<ComboboxSelected>>")
                root.update()
                if errors:
                    raise RuntimeError("Tk callbacks failed: " + "; ".join(errors))
                position_review_checked = True
            receipt.update(modelJourneyReplayChecked=model_replay_checked,
                           searchAndAutomaticReplanChecked=search_checked,
                           destinationReachabilityChecked=reachability_checked,
                           mapSourceSelectionChecked=map_pick_checked,
                           positionReviewChecked=position_review_checked,
                           title=root.title(), tkVersion=str(root.tk.call("info", "patchlevel")),
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


def exercise_launcher(*, catalog=None, pin=None, anchor=None):
    """Exercise real launcher widgets without replacing either viewer.

    The bounded mainloop interception invokes the application's own buttons,
    not global mouse/keyboard events. Validate explicit anchor selection and
    stale inventory invalidation before letting the production chooser load
    the actual world graph. A separate viewer smoke renders that graph.
    """
    import tkinter as tk
    from tkinter import ttk
    errors=[]
    def callback_error(self,exc_type,value,traceback):
        errors.append(f"{exc_type.__name__}: {value}")

    def smoke_loop(root,*args,**kwargs):
        try:
            root.update_idletasks()
            root.update()
            children=list(descendants(root))
            buttons={w.cget("text"):w for w in children if isinstance(w,ttk.Button)}
            entries=[w for w in children if isinstance(w,ttk.Entry)
                     and not isinstance(w,ttk.Combobox)]
            combos=[w for w in children if isinstance(w,ttk.Combobox)]
            if len(entries)!=2 or len(combos)!=1 or not root.winfo_ismapped():
                raise RuntimeError("unexpected launcher widgets")
            if catalog is None:
                buttons["Open synthetic demo"].invoke()
                return
            anchor_box=combos[0]
            open_button=buttons["Open world viewer"]
            def set_entry(entry,value):
                entry.delete(0,"end")
                entry.insert(0,str(value))
            set_entry(entries[0],catalog)
            set_entry(entries[1],"0"*64)
            buttons["Inspect catalog"].invoke()
            root.update()
            if not open_button.instate(["disabled"]) or anchor_box.cget("values"):
                raise RuntimeError("incorrect catalog pin was accepted")
            set_entry(entries[1],pin)
            buttons["Inspect catalog"].invoke()
            root.update()
            if anchor not in anchor_box.cget("values") or anchor_box.get():
                raise RuntimeError("catalog inventory missing or silently selected anchor")
            if not open_button.instate(["disabled"]):
                raise RuntimeError("world open enabled before explicit selection")
            anchor_box.set(anchor)
            anchor_box.event_generate("<<ComboboxSelected>>")
            root.update()
            if open_button.instate(["disabled"]):
                raise RuntimeError("explicit anchor did not enable opening")
            set_entry(entries[1],"0"*64)
            root.update()
            if anchor_box.get() or anchor_box.cget("values") or not open_button.instate(["disabled"]):
                raise RuntimeError("input edit retained stale launcher inventory")
            set_entry(entries[1],pin)
            buttons["Inspect catalog"].invoke()
            anchor_box.set(anchor)
            anchor_box.event_generate("<<ComboboxSelected>>")
            root.update()
            open_button.invoke()
        finally:
            # Production callbacks destroy the root on successful selection.
            try:
                if root.winfo_exists():
                    root.destroy()
            except tk.TclError:
                pass

    with patch.object(tk.Tk,"mainloop",smoke_loop),patch.object(
            tk.Tk,"report_callback_exception",callback_error):
        selection=choose()
    if errors or selection is None:
        raise RuntimeError("launcher failed: "+"; ".join(errors))
    mode,graph=selection
    expected="demo" if catalog is None else "world"
    if mode!=expected:
        raise RuntimeError("launcher selected wrong mode")
    if mode=="demo":
        if graph.classification!="SYNTHETIC_MODEL_ONLY":
            raise RuntimeError("launcher demo classification mismatch")
    elif graph.graph.classification!="OFFLINE_REVIEW_ONLY" or anchor not in graph.routes:
        raise RuntimeError("launcher world classification or anchor mismatch")
    return {"mode":mode,"mapped":True,"explicitAnchorChecked":mode=="world",
            "staleInputRefusalChecked":mode=="world","wrongPinRefusalChecked":mode=="world",
            "callbackErrors":[]}


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
               "launcherDemo":exercise_launcher(), "launcherWorld":None,
               "synthetic":exercise(launch_synthetic, demo_graph()),
               "importedWorld":None, "humanVisualInspection":False,
               "physicalQualification":False,"gameInputSent":False}
    if a.catalog is not None:
        world = load_world_graph(a.catalog,catalog_sha256=a.catalog_sha256,
                                 anchor_route=a.anchor_route)
        results["launcherWorld"]=exercise_launcher(catalog=a.catalog,pin=a.catalog_sha256,anchor=a.anchor_route)
        results["importedWorld"] = exercise(launch_world, world, world_route=a.anchor_route)
    raw = json.dumps(results,indent=2,allow_nan=False)+"\n"
    if a.out is not None:
        with a.out.open("x",encoding="utf-8",newline="\n") as f:
            f.write(raw)
    print(raw,end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
