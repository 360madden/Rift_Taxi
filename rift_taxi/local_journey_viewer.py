"""Desktop playback of completed *synthetic* journey receipts.

The model is executed by local_taxi, not the GUI. Playback shows the actual
recorded model samples (including terminal correction and stationary dwell),
not interpolation along a nominal route or a live controller. No game I/O.
"""
from __future__ import annotations

import math

from .local_taxi import coordinates, plan_route, require, run_local_journey

CLASSIFICATION = "SYNTHETIC_MODEL_ONLY"


def journey_samples(graph, plan):
    """Execute the selected synthetic plan and return its actual model samples.

    A preview can carry extra start-selection provenance, but all fields of
    the recomputed route must match. Never pass imported-world graphs to the
    ideal plant. Shared leg/phase boundary samples are not counted twice.
    """
    require(graph.classification == plan.get("classification") == CLASSIFICATION,
            "journey playback requires synthetic graph and plan")
    require(plan.get("graphSHA256") == graph.sha256, "plan graph identity mismatch")
    # Reject a stale or altered preview before spending model execution time.
    # The synthetic runner also independently plans; compare its output as a
    # second boundary, since it owns the actual model input.
    fresh = plan_route(graph,plan["startNode"],plan["destinationId"],
                       blocked_edges=plan["blockedEdges"])
    require(all(plan.get(key)==value for key,value in fresh.items()),
            "recomputed journey plan differs from preview")
    receipt = run_local_journey(graph, plan["startNode"], plan["destinationId"],
                                blocked_edges=plan["blockedEdges"])
    require(receipt["plan"]==fresh,"model route differs from validated preview")
    samples = []

    def append(t, xyz, phase, leg):
        pos = list(coordinates(xyz))
        t = float(t)
        require(math.isfinite(t) and t >= 0., "invalid playback time")
        if samples:
            prev = samples[-1]
            if abs(t-prev["t"]) <= 1e-9:
                require(pos == prev["xyz"], "discontinuous phase or leg boundary")
                return
            require(t > prev["t"], "nonadvancing playback time")
        samples.append({"t":t,"xyz":pos,"phase":phase,"leg":leg})

    journey = receipt["journey"]
    if journey is None:
        # Distinguish already-at-destination from no route. Neither executes
        # a synthetic model, so neither can supply a fabricated trajectory.
        if receipt["status"] == "already-at-destination":
            append(0.,plan["points"][0]["xyz"],"already-at-destination",0)
        return receipt, samples

    for leg in journey["legs"]:
        start, number = leg["startSeconds"], leg["legNumber"]
        report = leg["journey"]
        frames = report["approach"]["frames"]
        require(bool(frames), "missing approach frames")
        for row in frames:
            append(start+row["t"],row["xyz"],"approach",number)
        # Match the evidence builder's leg-local clock arithmetic exactly:
        # first accumulate phase offsets, then add the absolute leg start.
        # Floating-point addition is not associative.
        offset = frames[-1]["t"]
        drain = report["passiveDrain"].get("observations",[])
        for row in drain[1:]:
            append(start+(offset+row["elapsedAfterArrivalSeconds"]),row["xyz"],"settling",number)
        if drain:
            offset += drain[-1]["elapsedAfterArrivalSeconds"]
        correction = report["terminalCorrection"]
        if correction:
            for row in correction["frames"][1:]:
                append(start+(offset+row["elapsedSeconds"]),row["xyz"],"correction",number)
        for row in leg["dwellFrames"]:
            append(start+row["t"],row["xyz"],"dwell",number)
        require(abs(samples[-1]["t"]-leg["endSeconds"]) <= 1e-9
                and samples[-1]["xyz"] == leg["finalXYZ"], "playback leg endpoint mismatch")
    require(bool(samples) and abs(samples[-1]["t"]-journey["totalElapsedSeconds"]) <= 1e-9,
            "playback duration mismatch")
    return receipt,samples


def launch_playback(parent, graph, plan, *, receipt, samples):
    """Show a bounded replay of recorded samples in a separate Tk window.

    Playback time is display-only: stopping it does not interrupt a game or
    controller. No sample interpolation is used. Only the final receipt's
    actual status is shown as the outcome, never inferred from marker position.
    """
    import tkinter as tk
    from tkinter import ttk
    from .local_taxi_gui import build_scene
    require(graph.classification == plan.get("classification") == CLASSIFICATION
            and receipt.get("classification") == CLASSIFICATION
            and receipt["plan"]["graphSHA256"] == graph.sha256, "synthetic playback required")
    dialog = tk.Toplevel(parent)
    dialog.title("RIFT Taxi | Synthetic journey replay")
    dialog.geometry("850x580")
    dialog.minsize(520,360)
    dialog.transient(parent)
    dialog.rowconfigure(1,weight=1)
    dialog.columnconfigure(0,weight=1)
    ttk.Label(dialog,text="Recorded synthetic model samples — no game movement",
              padding=8).grid(row=0,column=0,sticky="w")
    canvas=tk.Canvas(dialog,background="#121b27",highlightthickness=0)
    canvas.grid(row=1,column=0,sticky="nsew")
    controls=ttk.Frame(dialog,padding=8)
    controls.grid(row=2,column=0,sticky="ew")
    controls.columnconfigure(2,weight=1)
    index=tk.IntVar(master=dialog,value=0)
    status=tk.StringVar(master=dialog)
    pending=None
    initial_draw=None
    playing=False
    closed=False
    last=max(0,len(samples)-1)
    cached_size=None
    projected=[]
    trail_id=pose_id=None

    def draw(*_):
        nonlocal cached_size,projected,trail_id,pose_id
        if closed:
            return
        w,h=canvas.winfo_width(),canvas.winfo_height()
        if w<80 or h<80:
            return
        # Build the immutable network and transform only when the viewport
        # changes. Each replay frame otherwise updates two existing items.
        # Preproject recorded positions once per resize, with no snapping.
        if cached_size!=(w,h):
            scene=build_scene(graph,plan,width=w,height=h)
            canvas.delete("all")
            for edge in scene["edges"]:
                color={"route":"#5bd6a2","network":"#627387","blocked":"#ef7777"}[edge["role"]]
                canvas.create_line(*edge["from"],*edge["to"],fill=color,
                                   width=3 if edge["role"]=="route" else 1,tags=("network",))
            for node in scene["nodes"]:
                x,y=node["position"]
                canvas.create_oval(x-3,y-3,x+3,y+3,fill="#dce5f0",outline="",tags=("network",))
            anchor=scene["nodes"][0]
            xyz=graph.nodes[anchor["id"]].xyz
            ax,ay=anchor["position"]
            scale=scene["scale"]
            projected=[(ax+(row["xyz"][0]-xyz[0])*scale,
                        ay-(row["xyz"][2]-xyz[2])*scale) for row in samples]
            trail_id=canvas.create_line(0,0,0,0,fill="#70b4ff",width=2,
                                        state="hidden",tags=("model-trail",))
            pose_id=canvas.create_oval(0,0,0,0,fill="#70b4ff",outline="#ffffff",
                                       state="hidden",tags=("model-pose",))
            cached_size=(w,h)
        if not samples:
            status.set(receipt["status"]+" | No model samples")
            return
        i=min(last,max(0,index.get()))
        row=samples[i]
        if i:
            canvas.coords(trail_id,*[v for point in projected[:i+1] for v in point])
            canvas.itemconfigure(trail_id,state="normal")
        else:
            canvas.itemconfigure(trail_id,state="hidden")
        x,y=projected[i]
        canvas.coords(pose_id,x-6,y-6,x+6,y+6)
        canvas.itemconfigure(pose_id,state="normal")
        outcome=receipt["status"] if i==last else ("replaying model" if playing else "model paused")
        status.set(f"{outcome} | {row['t']:.2f}/{samples[-1]['t']:.2f} s | "
                   f"Leg {row['leg']} | {row['phase']} | Sample {i+1}/{len(samples)}")

    def pause():
        nonlocal playing,pending
        playing=False
        if pending is not None:
            dialog.after_cancel(pending)
            pending=None
        if not closed:
            play.configure(text="Play")
            draw()

    def tick():
        nonlocal pending
        pending=None
        if closed or not playing:
            return
        i=index.get()
        if i>=last:
            pause()
            return
        index.set(i+1)
        schedule()

    def schedule():
        nonlocal pending
        i=index.get()
        if i>=last:
            pause()
            return
        delta=samples[i+1]["t"]-samples[i]["t"]
        pending=dialog.after(max(1,round(delta*1000)),tick)

    def toggle():
        nonlocal playing
        if playing:
            pause()
            return
        if len(samples)<2:
            return
        playing=True
        if index.get()>=last:
            index.set(0)
        play.configure(text="Pause")
        draw()
        schedule()

    def close():
        # Destroy handling owns cancellation of both scheduled callbacks.
        # Avoid a final expensive redraw of a window about to disappear.
        dialog.destroy()

    play=ttk.Button(controls,text="Play",command=toggle,
                    state="normal" if len(samples)>1 else "disabled")
    play.grid(row=0,column=0,padx=(0,4))
    ttk.Button(controls,text="Close",command=close).grid(row=0,column=1,padx=4)
    scale_widget=tk.Scale(controls,from_=0,to=last,orient="horizontal",showvalue=False,
                          variable=index,resolution=1,state="normal" if last else "disabled")
    scale_widget.grid(row=0,column=2,sticky="ew")
    ttk.Label(controls,textvariable=status,wraplength=800).grid(row=1,column=0,columnspan=3,sticky="w")
    # Manual scrubbing pauses playback; programmatic sample advances don't
    # enter this event path. Cancel scheduled work when the dialog is closed.
    scale_widget.bind("<ButtonPress-1>",lambda _:pause())
    scale_widget.bind("<KeyPress>",lambda _:pause())
    trace_id=index.trace_add("write",draw)
    canvas.bind("<Configure>",draw)
    dialog.protocol("WM_DELETE_WINDOW",close)
    def destroyed(event):
        # Parent destruction can remove child controls before this callback.
        # Cancel both timers and remove the variable trace; never render or
        # configure widgets from a callback once teardown has begun.
        nonlocal pending,playing,closed,initial_draw
        if event.widget is dialog:
            closed=True
            playing=False
            for handle in (pending,initial_draw):
                if handle is not None:
                    try:
                        dialog.after_cancel(handle)
                    except tk.TclError:
                        pass
            pending=initial_draw=None
            try:
                index.trace_remove("write",trace_id)
            except tk.TclError:
                pass

    def first_draw():
        nonlocal initial_draw
        initial_draw=None
        draw()

    dialog.bind("<Destroy>",destroyed)
    initial_draw=dialog.after_idle(first_draw)
    return dialog
