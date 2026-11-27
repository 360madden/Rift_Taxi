"""Matched synthetic corner admission comparison; no live game or input.

The bounded candidate uses the same robust estimator as the V2 comparator.
It never learns the hidden noise profile or plant truth. Retrospective
scoring retains the original sharp-corner radius and arrival criteria.
The old cohort is explicitly development replay; new cases are declared
here independently before evaluation. No physical qualification.
"""
import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path

from .contracts import TraceError
from .simulation_holdout import _case_trace
from .synthetic_sampled_steering import run, DT
from .synthetic_corner_certificate import AXIS_ERROR_BOUND
from .synthetic_robust_study import cases as prior_cases, estimator_metrics
from .synthetic_sensor_noise import PROFILES as NOISE_PROFILES
from .synthetic_journey_batch import paired_metrics

GENERATOR = "taxi-bounded-corner-20261127-v1"
POLICIES = ("legacy","robust","bounded")
ROUTES = (
    ("translated-switchback",((-3,0,4),(3,0,5),(0,0,8),(7,0,12),(13,0,10),(18,0,14))),
    ("close-reversals",((0,0,0),(5,0,2),(2,0,3),(7,0,5),(4,0,7),(12,0,10))),
)
MOTION = ((2.7,2),(3.2,6))
RESPONSE = (("fixed-new",.92,1.18,None),
            ("fast-to-slow",1.15,1.25,(80,.85,.8)))
TRANSPORT = ("jitter-in-order","short-dropout","long-dropout")


def new_cases():
    """96 additional matched cases, including 32 deliberate fault cases."""
    for (name,points),(speed,delay),(gain,vg,yg,change),noise,profile in product(
            ROUTES,MOTION,RESPONSE,NOISE_PROFILES,TRANSPORT):
        seed=points[0]
        trace=_case_trace({"routeId":name,"routeXYZ":[list(p) for p in points],
                           "initialXYZ":[seed[0],seed[1],seed[2]+.16],
                           "initialYawDegrees":12.},generator=GENERATOR)
        yield trace,speed,delay,gain,vg,yg,change,noise,profile


def row(case,cohort):
    """Only the corner policy differs between robust and bounded variants."""
    trace,speed,delay,gain,vg,yg,change,noise,profile=case
    opts=dict(speed=speed,delay=delay,profile=profile,mode="predict-application",
              actual_speed_gain=vg,actual_yaw_gain=yg,response_change=change,
              sensor_noise=noise,adaptive=True)
    results={}
    for policy in POLICIES:
        report=run(trace,adaptive_policy="legacy" if policy=="legacy" else "robust",
                   corner_policy="bounded" if policy=="bounded" else "legacy",**opts)
        result={"summary":report["summary"],"stop":report["stop"],
                "admittedSamples":len(report["admissions"]),
                "estimator":estimator_metrics(report,delay,vg,yg,change)}
        if policy=="bounded":
            # The source witnesses have already been independently verified.
            result["certificates"]=report["sharpWitnesses"]
        results[policy]=result
    return {"cohort":cohort,"route":trace.route_id,"scenarioSHA256":trace.trace_sha256,
            "speed":speed,"actualDelaySteps":delay,"gainProfile":gain,
            "actualGains":[vg,yg],"responseChange":list(change) if change else None,
            "sensorNoise":noise,"profile":profile,"results":results}


def compare(rows):
    """Preserve all failures; match cases before calculating elapsed means."""
    usable=[r for r in rows if r["profile"]!="long-dropout"]
    faults=[r for r in rows if r["profile"]=="long-dropout"]
    paired={}
    for base in POLICIES[:2]:
        views=[{"results":{"baseline":r["results"][base],
                           "bounded":r["results"]["bounded"]}} for r in usable]
        paired[base]=paired_metrics(views,"bounded")
    counts={p:sum(r["results"][p]["summary"]["finalModelSettled"] for r in usable)
            for p in POLICIES}
    expiries={p:sum(r["results"][p]["stop"]["reason"]=="observation-expired" for r in faults)
              for p in POLICIES}
    bad={p:sum(r["results"][p]["summary"].get("truthSharpWitnessesValid") is False
               for r in usable) for p in POLICIES}
    certs=[w for r in rows for w in r["results"]["bounded"]["certificates"]]
    certificate_violations=sum(w["upperDistanceXZ"]>w["radiusXZ"] for w in certs)
    screen={"noLegacySettledLosses":paired["legacy"]["settledLosses"]==0,
            "noRobustSettledLosses":paired["robust"]["settledLosses"]==0,
            "allBoundedDropoutsExpired":expiries["bounded"]==len(faults),
            "noBoundedTruthWitnessFailures":bad["bounded"]==0,
            "noCertificateViolations":certificate_violations==0}
    return {"conditions":len(rows),"usable":len(usable),"faultCases":len(faults),
            "settled":counts,"faultExpiries":expiries,"truthWitnessFailures":bad,
            "boundedVersus":paired,"certificateCount":len(certs),
            "certificateViolations":certificate_violations,
            "stopReasons":{p:dict(sorted(Counter(r["results"][p]["stop"]["reason"]
                                                 for r in rows).items())) for p in POLICIES},
            "researchScreen":{**screen,"passed":all(screen.values())}}


def evaluate():
    rows=[row(c,"prior-development") for c in prior_cases()]
    rows.extend(row(c,"new-fixed") for c in new_cases())
    cohorts=("prior-development","new-fixed")
    return {"schema":"taxi.synthetic-bounded-corner-study/1","classification":"SYNTHETIC_ONLY",
            "design":GENERATOR,"dtSeconds":DT,"axisErrorBound":AXIS_ERROR_BOUND,
            "caseCount":len(rows),"executionCount":len(rows)*len(POLICIES),
            "byCohort":{c:compare([r for r in rows if r["cohort"]==c]) for c in cohorts},
            "byNoise":{c:{n:compare([r for r in rows if r["cohort"]==c and r["sensorNoise"]==n])
                          for n in NOISE_PROFILES} for c in cohorts},
            "overall":compare(rows),"rows":rows,"gameInputSent":False,"physicalQualification":False,
            "limitations":["Synthetic bounded measurement envelope; no measured RIFT calibration.",
                           "Fixed whole-step command delay and at most one gain change.",
                           "Retrospective truth is used only for verification and scoring.",
                           "No collision, terrain, inertia or physical release model."]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary",action="store_true")
    parser.add_argument("--out",type=Path,help="new JSON output; never overwrite")
    args=parser.parse_args(argv)
    try:
        if args.out is not None and args.out.exists():
            raise FileExistsError(args.out)
        report=evaluate()
        if args.out is not None:
            with args.out.open("x",encoding="utf-8",newline="\n") as f:
                f.write(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
        if args.summary or args.out is None:
            view={k:v for k,v in report.items() if k not in ("rows","byNoise")} if args.summary else report
            print(json.dumps(view,sort_keys=True,indent=2,allow_nan=False))
        return 0
    except (TraceError,ValueError,OSError) as exc:
        parser.exit(2,f"Bounded corner study refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
