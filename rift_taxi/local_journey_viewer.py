"""Desktop playback of completed *synthetic* journey receipts.

The model is executed by local_taxi, not the GUI. Playback shows the actual
recorded model samples (including terminal correction and stationary dwell),
not interpolation along a nominal route or a live controller. No game I/O.
"""
from __future__ import annotations

import math

from .local_taxi import coordinates, require, run_local_journey

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
    receipt = run_local_journey(graph, plan["startNode"], plan["destinationId"],
                                blocked_edges=plan["blockedEdges"])
    require(all(plan.get(key) == value for key,value in receipt["plan"].items()),
            "recomputed journey plan differs from preview")
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
    playing=False
    last=max(0,len(samples)-1)

    def draw(*_):
        canvas.delete("all")
        w,h=canvas.winfo_width(),canvas.winfo_height()
        if w<80 or h<80:
            return
        scene=build_scene(graph,plan,width=w,height=h)
        for edge in scene["edges"]:
            color={"route":"#5bd6a2","network":"#627387","blocked":"#ef7777"}[edge["role"]]
            canvas.create_line(*edge["from"],*edge["to"],fill=color,
                               width=3 if edge["role"]=="route" else 1)
        for node in scene["nodes"]:
            x,y=node["position"]
            canvas.create_oval(x-3,y-3,x+3,y+3,fill="#dce5f0",outline="")
        if not samples:
            status.set(receipt["status"]+" | No model samples")
            return
        i=min(last,max(0,index.get()))
        row=samples[i]
        # Use the existing map projection's scale and a known node anchor.
        # Model samples may lie off the nominal path; never snap the marker.
        anchor=scene["nodes"][0]
        xyz=graph.nodes[anchor["id"]].xyz
        ax,ay=anchor["position"]
        scale=scene["scale"]
        def project(pos):
            return ax+(pos[0]-xyz[0])*scale,ay-(pos[2]-xyz[2])*scale
        trail=[v for sample in samples[:i+1] for v in project(sample["xyz"])]
        if len(trail)>=4:
            canvas.create_line(*trail,fill="#70b4ff",width=2)
        x,y=project(row["xyz"])
        canvas.create_oval(x-6,y-6,x+6,y+6,fill="#70b4ff",outline="#ffffff",tags=("model-pose",))
        outcome=receipt["status"] if i==last else "replaying model"
        status.set(f"{outcome} | {row['t']:.2f}/{samples[-1]['t']:.2f} s | "
                   f"Leg {row['leg']} | {row['phase']} | Sample {i+1}/{len(samples)}")

    def pause():
        nonlocal playing,pending
        playing=False
        if pending is not None:
            dialog.after_cancel(pending)
            pending=None
        play.configure(text="Play")

    def tick():
        nonlocal pending
        pending=None
        if not playing:
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
        if index.get()>=last:
            index.set(0)
        playing=True
        play.configure(text="Pause")
        schedule()

    def close():
        pause()
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
    index.trace_add("write",draw)
    canvas.bind("<Configure>",draw)
    dialog.protocol("WM_DELETE_WINDOW",close)
    def destroyed(event):
        # Parent destruction can remove child controls before this callback.
        # Cancel only the timer here; do not configure a destroyed button.
        nonlocal pending,playing
        if event.widget is dialog:
            playing=False
            if pending is not None:
                try:
                    dialog.after_cancel(pending)
                except tk.TclError:
                    pass
                pending=None

    dialog.bind("<Destroy>",destroyed)
    dialog.after_idle(draw)
    return dialog
