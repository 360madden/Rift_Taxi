"""Offline verification of a saved constrained synthetic journey.

Reconstruct the original per-leg inputs and ordered sampled obligations,
verify retained approach/drain/correction receipts, and recompute the
cross-leg totals. The approach controller is not rerun. Deterministic
witness extraction is shared with the producer; this is model consistency
evidence, not physical motion, source authentication or optimality proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from .contracts import TraceError, load_trace, _read_bounded, _strict_json
from .simulation import _bounded_number
from .synthetic_journey_audit import verify_journey, _match
from .synthetic_route_constraints import _policy, _audit_samples, MAX_POLICY_BYTES, require
from .synthetic_constrained_journey import MAX_LEGS, _digest, _leg_inputs, _observations

MAX_REPORT_BYTES = 32*1024*1024
SHA = re.compile(r"[0-9a-fA-F]{64}\Z")


def verify_constrained_report(report,trace,policy):
    """Validate saved model evidence and the exact intended leg sequence.

    Inputs are caller-owned synthetic trace and policy. Their semantic
    identifiers must match the report; the file entry point additionally
    checks exact source bytes. A completed first leg without its required
    continuation is not a complete receipt. A failure cannot resume.
    """
    try:
        return _verify(report,trace,policy)
    except TraceError:
        raise
    except (KeyError,TypeError,ValueError,AttributeError,IndexError,OverflowError,RecursionError) as exc:
        raise TraceError("constrained journey audit: malformed receipt") from exc


def _verify(report,trace,policy):
    gap,dwell,height,tolerance,regions=_policy(trace,policy)
    _bounded_number(tolerance,"model arrival tolerance",.01,5.)
    fields={"schema","classification","routeId","inputTraceSHA256","policyContentSHA256",
            "model","status","allObligationsObserved","plannedLegs","completedLegs",
            "totalElapsedSeconds","totalDistanceXZ","totalForwardDutyRatio","obligations","legs",
            "physicalQualification","gameInputSent","corridorClearanceVerified",
            "continuousStationarityVerified","limitations"}
    require(isinstance(report,dict) and set(report) in (fields,fields|{"policySHA256"}),
            "constrained receipt fields mismatch")
    for k,v in {"schema":"taxi.synthetic-constrained-journey/1",
                "classification":"SYNTHETIC_MODEL_ONLY","routeId":trace.route_id,
                "inputTraceSHA256":trace.trace_sha256,"policyContentSHA256":_digest(policy),
                "physicalQualification":False,"gameInputSent":False,
                "corridorClearanceVerified":False,"continuousStationarityVerified":False}.items():
        _match(report[k],v,"constrained "+k)
    require(isinstance(report["limitations"],list)
            and all(type(v) is str for v in report["limitations"]),"invalid receipt limitations")
    if "policySHA256" in report:
        require(isinstance(report["policySHA256"],str) and SHA.fullmatch(report["policySHA256"]),
                "invalid policy byte hash")
    model=report["model"]
    dt=_bounded_number(model["dt"],"dt",.02,.2)
    require(dt<=gap,"model dt exceeds maximum sample gap")
    speed=_bounded_number(model["speed"],"speed",.1,20.)
    yaw_rate=_bounded_number(model["yawRate"],"yaw rate",10.,720.)
    approach_budget=_bounded_number(model["approachBudgetPerLeg"],"leg approach budget",.2,40.)
    terminal_budget=_bounded_number(model["terminalBudgetPerLeg"],"leg terminal budget",.01,5.)
    lookahead=_bounded_number(model["lookahead"],"lookahead",.1,20.)
    delay=model["delaySteps"]
    require(type(delay) is int and 0<=delay<=10,"invalid model delay")
    _match(model,{"dt":dt,"speed":speed,"yawRate":yaw_rate,"delaySteps":delay,
                  "approachBudgetPerLeg":approach_budget,"terminalBudgetPerLeg":terminal_budget,
                  "lookahead":lookahead,"stopDwellSeconds":dwell},"constrained model")
    require(2<=len(trace.points)<=500 and bool(trace.poses),"missing route or seed")
    require(trace.points[0].kind in ("guide","optional") and trace.points[-1].kind=="destination"
            and all(p.kind!="destination" for p in trace.points[:-1]),"invalid route boundaries")
    initial=trace.poses[0]
    _bounded_number(initial.actor_yaw_deg,"initial yaw",-1e6,1e6)
    for position in (initial.xyz,*(p.xyz for p in trace.points)):
        require(len(position)==3,"invalid model XYZ")
        for value in position:
            _bounded_number(value,"model coordinate",-1e6,1e6)
        require(abs(position[1]-initial.xyz[1])<=1e-9,"flat synthetic route required")
    ends=[i for i,p in enumerate(trace.points) if p.kind in ("hard_stop","destination")]
    require(1<=len(ends)<=MAX_LEGS,"invalid stop leg count")
    start=0
    for end in ends:
        lengths=[math.hypot(b.xyz[0]-a.xyz[0],b.xyz[2]-a.xyz[2])
                 for a,b in zip(trace.points[start:end],trace.points[start+1:end+1])]
        require(bool(lengths) and all(n>1e-9 for n in lengths) and sum(lengths)>tolerance,
                "degenerate stop leg geometry")
        start=end
    _match(report["plannedLegs"],len(ends),"planned legs")
    legs=report["legs"]
    require(isinstance(legs,list) and 1<=len(legs)<=len(ends),"invalid receipt leg inventory")
    obligations={i:{"pointIndex":i,"name":p.name,"kind":p.kind,"status":"not-attempted",
                    "witness":None}
                 for i,p in enumerate(trace.points)
                 if p.kind in ("mandatory_passage","hard_stop","destination")}
    first=0; elapsed=distance=forward=0.; completed=0
    status="model-obligations-observed"
    for number,leg in enumerate(legs):
        require(completed==number,"receipt resumes after failed obligation")
        last=ends[number]
        controller,evidence,leg_policy=_leg_inputs(trace,first,last,initial,regions,policy)
        _match(leg["controllerTraceSHA256"],controller.trace_sha256,"leg controller identity")
        jr=leg["journey"]
        require(jr.get("experimentalApproachMode","baseline")=="baseline",
                "unexpected constrained approach mode")
        approach=jr["approach"]
        # Every leg must have the declared common model parameters; a
        # self-consistent report from a different speed/delay is not this run.
        _match(approach["model"],{
            "dtSeconds":dt,"speedSyntheticUnitsPerSecond":speed,
            "lookaheadSyntheticUnits":lookahead,"maxYawRateDegreesPerSecond":yaw_rate,
            "maxSeconds":approach_budget,"maxCrossTrackSyntheticUnits":2.,
            "headingGainPerSecond":5.,"projectionAdvanceBudgetFactor":2.,
            "speedPolicy":"turn-limited-ordered"},"leg approach model")
        _match(approach.get("syntheticDelay",{}).get("steps",0),delay,"leg delay")
        verify_journey(jr,controller,terminal_budget=terminal_budget)
        # Reconstruct witnesses from actual applied phases and the explicit
        # zero-command dwell policy. No report-supplied witness index or
        # initial/final pose is accepted as the source of another leg.
        poses,quiet,limit,dwell_rows=_observations(jr,dt,dwell)
        audit=_audit_samples(evidence,leg_policy,poses,quiet,
                             first_index=1 if number else 0,passage_limit=limit)
        audit["classification"]="SYNTHETIC_MODEL_SAMPLED_EVIDENCE_ONLY"
        audit["sampleEvidenceBasis"]="applied-ideal-model-commands"
        _match(leg["dwellFrames"],dwell_rows,"leg dwell frames")
        _match(leg["obligationAudit"],audit,"leg obligation evidence")
        for row in audit["obligations"]:
            idx=first+row["pointIndex"]
            obligations[idx]={**row,"pointIndex":idx,"kind":trace.points[idx].kind,
                              "legNumber":number+1,"legStartSeconds":elapsed}
        settled=jr["summary"]["finalModelSettled"]
        accepted=settled and audit["allObligationsObserved"]
        expected={"legNumber":number+1,"firstPointIndex":first,"lastPointIndex":last,
                  "startSeconds":elapsed,"endSeconds":elapsed+poses[-1].t,
                  "controllerTraceSHA256":controller.trace_sha256,
                  "initialXYZ":list(initial.xyz),"initialYawDegrees":initial.actor_yaw_deg,
                  "finalXYZ":list(poses[-1].xyz),"finalYawDegrees":poses[-1].actor_yaw_deg,
                  "legAccepted":accepted}
        require(set(leg)==set(expected)|{"journey","dwellFrames","obligationAudit"},
                "leg receipt fields mismatch")
        for k,v in expected.items():
            _match(leg[k],v,"leg "+k)
        elapsed+=poses[-1].t
        distance+=jr["summary"]["totalDistanceXZ"]
        # Independent recount from applied commands, rather than multiply
        # the producer's duty ratio back into seconds. Dwell adds no travel.
        forward+=approach["metrics"]["forwardSeconds"]
        forward+=dt*sum(f["appliedSpeed"]>0. for f in
                        jr["passiveDrain"].get("observations",[])[1:])
        correction=jr["terminalCorrection"]
        if correction:
            forward+=dt*sum(f["appliedSpeed"]>0. for f in correction["frames"][1:])
        if not accepted:
            status=jr["summary"]["status"] if not settled else "constraint-not-observed"
            require(number==len(legs)-1,"receipt resumes after failed obligation")
        else:
            completed+=1
            initial=poses[-1]
            first=last
    # A producer always proceeds after an accepted leg; a shortened
    # accepted prefix cannot be presented as either completion or failure.
    require(completed<len(legs) or completed==len(ends),"truncated successful leg sequence")
    for k,v in {"status":status,"completedLegs":completed,
                "allObligationsObserved":completed==len(ends),
                "totalElapsedSeconds":elapsed,"totalDistanceXZ":distance,
                "totalForwardDutyRatio":forward/elapsed if elapsed else 0.,
                "obligations":list(obligations.values())}.items():
        _match(report[k],v,"constrained "+k)
    return {"schema":"taxi.synthetic-constrained-audit/1","status":"verified-offline",
            "classification":"SYNTHETIC_MODEL_ONLY","routeId":trace.route_id,
            "inputTraceSHA256":trace.trace_sha256,"policyContentSHA256":_digest(policy),
            "journeyStatus":status,"completedLegs":completed,"plannedLegs":len(ends),
            "allObligationsObserved":completed==len(ends),
            "legPhaseConsistencyVerified":True,"orderedWitnessesRecomputed":True,
            "poseCarryoverVerified":True,"summaryRecomputed":True,
            "approachControllerReexecuted":False,"physicalQualification":False,
            "gameInputSent":False,"sourceAuthenticityEstablished":False}


def audit_saved(trace_path,policy_path,report_path,*,expected_sha256=None):
    raw=_read_bounded(Path(report_path),MAX_REPORT_BYTES,"constrained journey report")
    pin=hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None:
        require(isinstance(expected_sha256,str) and SHA.fullmatch(expected_sha256)
                and expected_sha256.lower()==pin,"report SHA mismatch")
    policy_bytes=_read_bounded(Path(policy_path),MAX_POLICY_BYTES,"constraint policy")
    policy_pin=hashlib.sha256(policy_bytes).hexdigest()
    report=_strict_json(raw,"constrained journey report")
    policy=_strict_json(policy_bytes,"constraint policy")
    receipt=verify_constrained_report(report,load_trace(trace_path),policy)
    declared=report.get("policySHA256")
    if declared is not None:
        require(declared.lower()==policy_pin,"policy byte SHA mismatch")
    return {**receipt,"reportSHA256":pin,"policySHA256":policy_pin,
            "expectedSHA256Matched":True if expected_sha256 is not None else None,
            "declaredPolicySHA256Matched":True if declared is not None else None}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for role in ("trace","policy","report"):
        p.add_argument(role,type=Path)
    p.add_argument("--expected-sha256")
    p.add_argument("--out",type=Path)
    a=p.parse_args(argv)
    try:
        if a.out is not None and a.out.exists():
            raise FileExistsError(a.out)
        result=audit_saved(a.trace,a.policy,a.report,expected_sha256=a.expected_sha256)
        encoded=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
        if a.out is not None:
            with a.out.open("x",encoding="utf-8",newline="\n") as stream:
                stream.write(encoded)
        print(encoded,end="")
        return 0
    except (TraceError,OSError,ValueError) as exc:
        p.exit(2,f"Constrained journey audit refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
