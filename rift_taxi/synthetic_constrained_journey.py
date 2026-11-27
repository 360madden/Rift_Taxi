"""Bounded synthetic leg execution with ordered stop and passage witnesses.

Reuse the existing ideal plant and terminal settlement model. This first
slice splits at requested hard stops, never at ordinary guides or passage
regions. It does not implement a topology-aware region-constrained steering
controller: a missed region rejects the completed leg and prevents resume.
No physical routes, game input, corridor clearance, or key-release proof.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

from .contracts import PoseSample, TraceError, load_trace, _read_bounded, _strict_json
from .simulation import _bounded_number
from .synthetic_journey_demo import journey
from .synthetic_journey_audit import verify_journey
from .synthetic_route_constraints import (
    _policy, _audit_samples, MAX_POLICY_BYTES, SCHEMA as POLICY_SCHEMA, require,
)

MAX_LEGS = 8


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
                                     allow_nan=False).encode()).hexdigest()


def _leg_inputs(trace, first, last, initial, regions, policy):
    """Keep the original point order and exact carried-forward model pose.

    The existing simulator only accepts unconstrained guide/destination
    geometry. Make a distinct controller input, retaining nominal mandatory
    points as guides. The evidence input preserves each mandatory kind.
    Both derived identities bind the parent trace, slice and seed. The
    shared stop boundary is a guide on the next leg, not a second stop.
    """
    route=trace.points[first:last+1]
    evidence_points=tuple(
        replace(p,kind="guide" if i==0 else "destination" if i==len(route)-1 else p.kind)
        for i,p in enumerate(route))
    controller_points=tuple(
        replace(p,kind="guide" if p.kind=="mandatory_passage" else p.kind)
        for p in evidence_points)
    base={"parentSHA256":trace.trace_sha256,"first":first,"last":last,
          "seedXYZ":list(initial.xyz),"seedYawDegrees":initial.actor_yaw_deg,
          "arrivalToleranceXZ":trace.arrival_tolerance_xz}
    def make(points,basis):
        identity={**base,"basis":basis,
                  "points":[{"name":p.name,"kind":p.kind,"xyz":list(p.xyz)} for p in points]}
        return replace(trace,source={"generator":"taxi-constrained-leg/1"},
                       route_id=f"{trace.route_id}:leg:{first}-{last}",points=points,
                       poses=(replace(initial,t=0.),),events=(),
                       window_start=0.,window_end=1.,trace_sha256=_digest(identity),
                       verified_source_sha256=None)
    evidence=make(evidence_points,"constraint-evidence")
    controller=make(controller_points,"unconstrained-model")
    leg_policy={**policy,"schema":POLICY_SCHEMA,"traceSHA256":evidence.trace_sha256,
                "passageRegions":[{"pointIndex":i-first,"minXYZ":list(bounds[0]),
                                   "maxXYZ":list(bounds[1])}
                                  for i,bounds in regions.items() if first<i<last]}
    return controller,evidence,leg_policy


def _observations(report,dt,dwell):
    """Convert actual ideal applied-command phases into sampled evidence.

    Approach frames describe the interval *after* their pose; drain and
    correction describe the interval *ending* at their pose. Do not double
    count phase-boundary samples, substitute requested commands for applied
    commands, or synthesize keyboard input. Only a settled model is
    eligible for extra stationary observations.
    """
    frames=report["approach"]["frames"]
    poses=[PoseSample(row["t"],tuple(row["xyz"]),row["yawDegrees"]) for row in frames]
    quiet=[False]+[row["speed"]==0. and row["yawRateDegreesPerSecond"]==0.
                   for row in frames[:-1]]
    passage_limit=len(poses)
    offset=poses[-1].t
    for row in report["passiveDrain"].get("observations",[])[1:]:
        poses.append(PoseSample(offset+row["elapsedAfterArrivalSeconds"],
                                tuple(row["xyz"]),row["yawDegrees"]))
        quiet.append(row["appliedSpeed"]==0. and row["appliedYawRateDegreesPerSecond"]==0.)
    correction=report["terminalCorrection"]
    offset=poses[-1].t
    for row in correction["frames"][1:] if correction else ():
        poses.append(PoseSample(offset+row["elapsedSeconds"],
                                tuple(row["xyz"]),row["yawDegrees"]))
        quiet.append(row["appliedSpeed"]==0. and row["appliedYawRate"]==0.)
    dwell_rows=[]
    if report["summary"]["finalModelSettled"]:
        # The preceding drain/correction has independently verified the
        # ideal queue. Model zero commands for the full additional dwell,
        # including a fractional rounding margin from ceil, not a pose reset.
        initial=poses[-1]
        for i in range(1,math.ceil(dwell/dt)+1):
            t=initial.t+i*dt
            poses.append(replace(initial,t=t))
            quiet.append(True)
            dwell_rows.append({"t":t,"xyz":list(initial.xyz),"yawDegrees":initial.actor_yaw_deg,
                               "appliedSpeed":0.,"appliedYawRateDegreesPerSecond":0.})
    require(all(b.t>a.t for a,b in zip(poses,poses[1:])), "nonadvancing model sample")
    return poses,quiet,passage_limit,dwell_rows


def run_constrained_journey(trace,policy,*,dt=.1,speed=3.,yaw_rate=115.,
                            delay_steps=0,approach_budget=40.,terminal_budget=5.,
                            lookahead=1.5):
    """Execute bounded synthetic legs and admit resume only after evidence.

    Model budgets are per leg; at most eight legs, 40 s approach and 5 s
    terminal correction each, plus bounded FIFO drain and explicit dwell.
    No retry loop. A failed approach, missed passage, or unsettled stop
    keeps the failure and prevents subsequent legs from running.
    """
    gap,dwell,height,tolerance,regions=_policy(trace,policy)
    # The underlying simulator's narrower tolerance contract applies to
    # execution, even though the sampled-evidence checker permits .001.
    _bounded_number(tolerance,"model arrival tolerance",.01,5.)
    dt=_bounded_number(dt,"dt",.02,.2)
    require(dt<=gap,"model dt exceeds maximum sample gap")
    speed=_bounded_number(speed,"speed",.1,20.)
    yaw_rate=_bounded_number(yaw_rate,"yaw rate",10.,720.)
    approach_budget=_bounded_number(approach_budget,"leg approach budget",.2,40.)
    terminal_budget=_bounded_number(terminal_budget,"leg terminal budget",.01,5.)
    lookahead=_bounded_number(lookahead,"lookahead",.1,20.)
    require(type(delay_steps) is int and 0<=delay_steps<=10,"invalid model delay")
    require(2<=len(trace.points)<=500 and bool(trace.poses),"missing route or seed")
    require(trace.points[0].kind in ("guide","optional")
            and trace.points[-1].kind=="destination","unsupported route boundary kinds")
    require(all(p.kind!="destination" for p in trace.points[:-1]),"early destination")
    initial=trace.poses[0]
    _bounded_number(initial.actor_yaw_deg,"initial yaw",-1e6,1e6)
    for position in (initial.xyz,*(p.xyz for p in trace.points)):
        require(len(position)==3,"invalid model XYZ")
        for value in position:
            _bounded_number(value,"model coordinate",-1e6,1e6)
        require(abs(position[1]-initial.xyz[1])<=1e-9,"flat synthetic route required")
    ends=[i for i,p in enumerate(trace.points) if p.kind in ("hard_stop","destination")]
    require(1<=len(ends)<=MAX_LEGS,"too many stop legs")
    # Validate every leg's geometry before beginning any simulation. The
    # existing controller rejects zero-horizontal segments and total arc
    # length at or below the arrival tolerance; report invalid input early.
    first=0
    for last in ends:
        lengths=[math.hypot(b.xyz[0]-a.xyz[0],b.xyz[2]-a.xyz[2])
                 for a,b in zip(trace.points[first:last],trace.points[first+1:last+1])]
        require(bool(lengths) and all(x>1e-9 for x in lengths)
                and sum(lengths)>tolerance,"degenerate stop leg geometry")
        first=last
    obligations={i:{"pointIndex":i,"name":p.name,"kind":p.kind,"status":"not-attempted",
                    "witness":None}
                 for i,p in enumerate(trace.points)
                 if p.kind in ("mandatory_passage","hard_stop","destination")}
    first=0; elapsed=distance=forward=0.; completed=0; legs=[]
    status="model-obligations-observed"
    for number,last in enumerate(ends):
        controller,evidence,leg_policy=_leg_inputs(trace,first,last,initial,regions,policy)
        report=journey(controller,dt=dt,speed=speed,yaw_rate=yaw_rate,
                       delay_steps=delay_steps,approach_budget=approach_budget,
                       terminal_budget=terminal_budget,lookahead=lookahead)
        # Reuse the independent trajectory and saved-journey verifier. It
        # recomputes terminal phases but does not rerun the approach controller.
        verify_journey(report,controller,terminal_budget=terminal_budget)
        poses,quiet,limit,dwell_rows=_observations(report,dt,dwell)
        audit=_audit_samples(evidence,leg_policy,poses,quiet,
                             first_index=1 if number else 0,passage_limit=limit)
        audit["classification"]="SYNTHETIC_MODEL_SAMPLED_EVIDENCE_ONLY"
        audit["sampleEvidenceBasis"]="applied-ideal-model-commands"
        # Restore original point identities in the overall receipt. Each
        # witness is local to the leg; global time offset is explicit.
        for row in audit["obligations"]:
            idx=first+row["pointIndex"]
            obligations[idx]={**row,"pointIndex":idx,"kind":trace.points[idx].kind,
                              "legNumber":number+1,"legStartSeconds":elapsed}
        leg_ok=report["summary"]["finalModelSettled"] and audit["allObligationsObserved"]
        legs.append({"legNumber":number+1,"firstPointIndex":first,"lastPointIndex":last,
                     "startSeconds":elapsed,"endSeconds":elapsed+poses[-1].t,
                     "controllerTraceSHA256":controller.trace_sha256,
                     "initialXYZ":list(initial.xyz),"initialYawDegrees":initial.actor_yaw_deg,
                     "finalXYZ":list(poses[-1].xyz),"finalYawDegrees":poses[-1].actor_yaw_deg,
                     "journey":report,"dwellFrames":dwell_rows,"obligationAudit":audit,
                     "legAccepted":leg_ok})
        elapsed+=poses[-1].t
        metrics=report["summary"]
        distance+=metrics["totalDistanceXZ"]
        forward+=metrics["totalElapsedSeconds"]*metrics["totalForwardDutyRatio"]
        if not leg_ok:
            status=metrics["status"] if not metrics["finalModelSettled"] else "constraint-not-observed"
            break
        completed+=1
        # Carry the actual settled model pose, not a nominal target point.
        initial=poses[-1]
        first=last
    return {"schema":"taxi.synthetic-constrained-journey/1",
            "classification":"SYNTHETIC_MODEL_ONLY","routeId":trace.route_id,
            "inputTraceSHA256":trace.trace_sha256,"policyContentSHA256":_digest(policy),
            "model":{"dt":dt,"speed":speed,"yawRate":yaw_rate,"delaySteps":delay_steps,
                     "approachBudgetPerLeg":approach_budget,"terminalBudgetPerLeg":terminal_budget,
                     "lookahead":lookahead,"stopDwellSeconds":dwell},
            "status":status,"allObligationsObserved":completed==len(ends),
            "plannedLegs":len(ends),"completedLegs":completed,
            "totalElapsedSeconds":elapsed,"totalDistanceXZ":distance,
            "totalForwardDutyRatio":forward/elapsed if elapsed else 0.,
            "obligations":list(obligations.values()),"legs":legs,
            "physicalQualification":False,"gameInputSent":False,
            "corridorClearanceVerified":False,"continuousStationarityVerified":False,
            "limitations":[
                "Ideal synthetic plant only; no game key or physical release evidence.",
                "Mandatory region samples are checked during approach, not guaranteed by a region-aware controller.",
                "A missed region refuses the leg and prevents resume; the already generated model approach is retained.",
                "Hard stops are leg boundaries with modeled stationary dwell and exact pose carryover.",
                "Source trace later poses and key events are ignored; no physical or topology claim."]}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("trace",type=Path)
    p.add_argument("policy",type=Path)
    p.add_argument("--dt",type=float,default=.1)
    p.add_argument("--speed",type=float,default=3.)
    p.add_argument("--yaw-rate",type=float,default=115.)
    p.add_argument("--delay-steps",type=int,default=0)
    p.add_argument("--approach-budget",type=float,default=40.)
    p.add_argument("--terminal-budget",type=float,default=5.)
    p.add_argument("--lookahead",type=float,default=1.5)
    p.add_argument("--require-observed",action="store_true")
    p.add_argument("--out",type=Path)
    a=p.parse_args(argv)
    try:
        if a.out is not None and a.out.exists():
            raise FileExistsError(a.out)
        raw=_read_bounded(a.policy,MAX_POLICY_BYTES,"constraint policy")
        result=run_constrained_journey(load_trace(a.trace),_strict_json(raw,"constraint policy"),
            dt=a.dt,speed=a.speed,yaw_rate=a.yaw_rate,delay_steps=a.delay_steps,
            approach_budget=a.approach_budget,terminal_budget=a.terminal_budget,lookahead=a.lookahead)
        result["policySHA256"]=hashlib.sha256(raw).hexdigest()
        encoded=json.dumps(result,indent=2,allow_nan=False)+"\n"
        if a.out is not None:
            with a.out.open("x",encoding="utf-8",newline="\n") as stream:
                stream.write(encoded)
        print(encoded,end="")
        return 1 if a.require_observed and not result["allObligationsObserved"] else 0
    except (TraceError,OSError,ValueError) as exc:
        p.exit(2,f"Synthetic constrained journey refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
