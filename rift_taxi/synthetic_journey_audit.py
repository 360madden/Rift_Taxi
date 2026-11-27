"""Validate a saved complete synthetic journey against its original trace.

This offline audit independently checks approach trajectory consistency,
reproduces the existing deterministic drain/correction phases, and recomputes
the cross-phase summary. It does not prove controller optimality, authenticate
the source, or grant physical movement authority. V1 journey receipts did
not store the terminal budget; the caller must explicitly supply that policy.
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
from .simulation_integrity import verify_synthetic_trajectory
from .simulation_settling import drain_after_arrival
from .synthetic_terminal_finish import finish_after_drain

MAX_REPORT_BYTES = 32 * 1024 * 1024
EPS = 1e-8
SHA = re.compile(r"[a-fA-F0-9]{64}\Z")


def _require(condition, label):
    if not condition:
        raise TraceError("journey audit: " + label)


def _match(actual, expected, label):
    """Compare full shapes and types, allowing only absolute float roundoff.

    Reject boolean/numeric aliases, missing or extra fields and nonfinite
    values. Preserve exact discrete outcomes and ordered frame sequences.
    """
    _require(type(actual) is type(expected), label + " type mismatch")
    if isinstance(expected, dict):
        _require(actual.keys() == expected.keys(), label + " fields mismatch")
        for key in expected:
            _match(actual[key], expected[key], label + "." + key)
    elif isinstance(expected, list):
        _require(len(actual) == len(expected), label + " length mismatch")
        for i, (a,b) in enumerate(zip(actual,expected)):
            _match(a,b,f"{label}[{i}]")
    elif isinstance(expected,float):
        _require(math.isfinite(actual) and math.isfinite(expected)
                 and math.isclose(actual,expected,rel_tol=0.,abs_tol=EPS),
                 label + " numeric mismatch")
    else:
        _require(actual == expected, label + " value mismatch")


def verify_journey(report, trace, *, terminal_budget):
    """Audit a report without rerunning the approach controller.

    The established trajectory auditor checks the approach independently.
    The terminal phase algorithms are reused as deterministic reference
    implementations, not claimed as independent physical models. The
    aggregate is recalculated here from phase boundaries and applied motion.
    """
    try:
        return _verify(report,trace,terminal_budget)
    except TraceError:
        raise
    except (KeyError,TypeError,ValueError,AttributeError,IndexError,OverflowError,RecursionError) as exc:
        raise TraceError("journey audit: malformed report") from exc


def _verify(report,trace,terminal_budget):
    budget = _bounded_number(terminal_budget,"terminal budget",.01,30.)
    _require(isinstance(report,dict),"report must be an object")
    required = {"schema","classification","routeId","inputTraceSHA256","approach",
                "passiveDrain","terminalCorrection","summary","physicalQualification",
                "gameInputSent","limitations"}
    _require(set(report) in (required,required|{"experimentalApproachMode"}),
             "report fields mismatch")
    _require(report["schema"]=="taxi.synthetic-journey-demo/1"
             and report["classification"]=="SYNTHETIC_ONLY"
             and report["routeId"]==trace.route_id
             and report["inputTraceSHA256"]==trace.trace_sha256
             and trace.source_type=="synthetic"
             and report["physicalQualification"] is False
             and report["gameInputSent"] is False,"source or classification mismatch")
    _require(isinstance(report["limitations"],list) and
             all(isinstance(x,str) for x in report["limitations"]),"invalid limitations")
    approach = report["approach"]
    verify_synthetic_trajectory(approach,trace)
    model = approach["model"]
    _require(model["speedPolicy"]=="turn-limited-ordered"
             and model["maxCrossTrackSyntheticUnits"]==2.,"unexpected approach model")
    mode = report.get("experimentalApproachMode","baseline")
    _require(mode in ("baseline","predict-near-goal","predict-near-stall","zero-delay-rejoin")
             and ("experimentalApproachMode" in report)==(mode!="baseline"),
             "invalid approach mode")
    delay = approach.get("syntheticDelay",{}).get("steps",0)
    prediction = approach.get("syntheticCommandPrediction")
    recovery = approach.get("syntheticTerminalProgressRecovery")
    if mode in ("predict-near-goal","predict-near-stall"):
        _require(delay>0 and isinstance(prediction,dict) and recovery is None,
                 "prediction mode mismatch")
        if mode=="predict-near-stall":
            _require(prediction.get("terminalRejoinPolicy")=="near-stall"
                     and prediction.get("terminalRejoinFraction")==.1,
                     "near-stall declaration mismatch")
        else:
            _require("terminalRejoinPolicy" not in prediction
                     and "terminalRejoinFraction" not in prediction,
                     "near-goal declaration mismatch")
    elif mode=="zero-delay-rejoin":
        _require(delay==0 and prediction is None,"zero-delay mode mismatch")
        _match(recovery,{"policy":"zero-delay-near-stall/1",
                         "terminalRejoinFraction":.1,"observedProgressOnly":True},
               "terminal progress recovery")
    else:
        _require(prediction is None and recovery is None,"baseline mode mismatch")

    dt = model["dtSeconds"]
    drain = drain_after_arrival(approach,trace)
    _match(report["passiveDrain"],drain,"passive drain")
    m = approach["metrics"]
    arrived = m["syntheticArrival"]
    correction = None
    drain_seconds = drain_distance = drain_forward = 0.
    if arrived:
        last = drain["observations"][-1]
        correction = finish_after_drain(
            xyz=last["xyz"],yaw=last["yawDegrees"],goal=trace.points[-1].xyz,
            dt=dt,speed=model["speedSyntheticUnitsPerSecond"],
            yaw_rate=model["maxYawRateDegreesPerSecond"],delay_steps=delay,
            tolerance=trace.arrival_tolerance_xz,budget=budget)
        # Count actual disjoint model intervals, not requested commands.
        observations = drain["observations"]
        drain_seconds = observations[-1]["elapsedAfterArrivalSeconds"]
        drain_distance = sum(row["appliedSpeed"]*dt for row in observations[1:])
        drain_forward = dt*sum(row["appliedSpeed"]>0. for row in observations[1:])
    _match(report["terminalCorrection"],correction,"terminal correction")
    correction_seconds = correction_distance = correction_forward = 0.
    if correction is not None:
        frames = correction["frames"]
        correction_seconds = frames[-1]["elapsedSeconds"]
        correction_distance = sum(row["appliedSpeed"]*dt for row in frames[1:])
        correction_forward = dt*sum(row["appliedSpeed"]>0. for row in frames[1:])
    settled = bool(correction and correction["settled"])
    total_seconds = m["elapsedSeconds"]+drain_seconds+correction_seconds
    forward = m["forwardSeconds"]+drain_forward+correction_forward
    expected = {
        "geometricArrival":arrived,
        "passiveSettled":drain["settledWithinTolerance"],
        "finalModelSettled":settled,
        "approachSeconds":m["elapsedSeconds"],
        "passiveDrainSeconds":drain_seconds,
        "terminalCorrectionSeconds":correction_seconds,
        "totalElapsedSeconds":total_seconds,
        "approachForwardDutyRatio":m["forwardDutyRatio"],
        "totalForwardDutyRatio":forward/total_seconds if total_seconds else 0.,
        "totalDistanceXZ":m["simulatedDistanceXZ"]+drain_distance+correction_distance,
        "finalObservedErrorXZ":correction["finalErrorXZ"] if correction else m["finalXZError"],
        "status":"approach-failed" if not arrived else "model-settled" if settled else "terminal-unsettled",
    }
    _match(report["summary"],expected,"summary")
    return {"schema":"taxi.synthetic-journey-audit/1","status":"verified-offline",
            "classification":"SYNTHETIC_ONLY","routeId":trace.route_id,
            "inputTraceSHA256":trace.trace_sha256,"terminalBudgetSeconds":budget,
            "approachConsistencyVerified":True,"terminalPhasesReproduced":True,
            "summaryRecomputed":True,"finalModelSettled":settled,
            "physicalQualification":False,"gameInputSent":False,
            "sourceAuthenticityEstablished":False}


def audit_saved(trace_path,report_path,*,terminal_budget,expected_sha256=None):
    """Pin and parse one exact report snapshot; never modify either original."""
    raw = _read_bounded(Path(report_path),MAX_REPORT_BYTES,"journey report")
    actual = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None:
        _require(isinstance(expected_sha256,str) and SHA.fullmatch(expected_sha256)
                 and expected_sha256.lower()==actual,"report SHA-256 mismatch")
    receipt = verify_journey(_strict_json(raw,"journey report"),load_trace(trace_path),
                             terminal_budget=terminal_budget)
    return {**receipt,"reportSHA256":actual,
            "expectedSHA256Matched":True if expected_sha256 is not None else None}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("trace",type=Path)
    p.add_argument("report",type=Path)
    p.add_argument("--terminal-budget",required=True,type=float,
                   help="original terminal budget; v1 report does not store it")
    p.add_argument("--expected-sha256")
    p.add_argument("--out",type=Path,help="new audit receipt; never overwrite")
    args=p.parse_args(argv)
    try:
        if args.out is not None and args.out.exists():
            raise FileExistsError(args.out)
        receipt=audit_saved(args.trace,args.report,terminal_budget=args.terminal_budget,
                            expected_sha256=args.expected_sha256)
        encoded=json.dumps(receipt,indent=2,sort_keys=True,allow_nan=False)+"\n"
        if args.out is not None:
            with args.out.open("x",encoding="utf-8",newline="\n") as stream:
                stream.write(encoded)
        print(encoded,end="")
        return 0
    except (TraceError,OSError,ValueError) as exc:
        p.exit(2,f"Synthetic journey audit refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
