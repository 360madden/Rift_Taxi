"""Compare a causal synthetic response estimator with a fixed nominal predictor.

The previous 144-condition combined study is a development replay, not a
fresh validation set. The separate authored design below varies actuator
response within a journey as well as between journeys, with no advance
notice to either controller. All outcomes are retained; no model is promoted
to live use. No game process, physical observations or input are used.
"""
import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path
from statistics import mean

from .contracts import TraceError
from .simulation_holdout import _case_trace
from .synthetic_combined_uncertainty import cases as prior_cases
from .synthetic_sampled_steering import run, DT
from .synthetic_response_estimator import NOMINAL
from .synthetic_journey_batch import paired_metrics

GENERATOR = "taxi-adaptive-response-20261126-v1"
# Fix the new comparison design and acceptance screen before evaluating it.
ROUTES = (
    ("slalom-offset", ((0,0,0),(5,0,2),(9,0,-1),(13,0,3),(19,0,2),(25,0,6))),
    ("reverse-dogleg", ((0,0,0),(7,0,2),(3,0,5),(10,0,8),(17,0,5),(25,0,7))),
)
SPEEDS = (2.4,3.4)
DELAYS = (0,4,8)
SWITCH_TICK = 64
RESPONSES = (
    ("unit",1.,1.,None),
    ("cross-gain",.9,1.2,None),
    ("slow-to-fast",.8,.7,(SWITCH_TICK,1.2,1.3)),
    ("fast-to-slow",1.2,1.3,(SWITCH_TICK,.8,.7)),
)
PROFILES = ("steady-delay","jitter-in-order","short-dropout","long-dropout")
GAIN_TOLERANCE = .05


def new_cases():
    """192 matched conditions, including 96 with one hidden response change."""
    for (name,points),speed,delay,(gain_name,vg,yg,change),profile in product(
            ROUTES,SPEEDS,DELAYS,RESPONSES,PROFILES):
        trace = _case_trace({"routeId":name,"routeXYZ":[list(p) for p in points],
                             "initialXYZ":[0.,0.,.18],"initialYawDegrees":20.},
                            generator=GENERATOR)
        yield trace,speed,delay,gain_name,vg,yg,change,profile


def _metrics(report, delay, vg, yg, change):
    """Measure model accuracy separately from successful route completion.

    An accurate decision-time model matches the actual current delay and
    both response gains within the declared tolerance. It does not imply
    prediction of a future change or independently qualified game pose.
    """
    qualified = [f for f in report["frames"] if f["responseEstimate"]["qualified"]]
    after_change = [] if change is None else [
        f for f in qualified if f["tick"] >= change[0]]
    def correct(f):
        estimate = f["responseEstimate"]
        gv,gr = change[1:] if change is not None and f["tick"]>=change[0] else (vg,yg)
        return (estimate["delay"]==delay
                and abs(estimate["speedGain"]-gv)<=GAIN_TOLERANCE
                and abs(estimate["yawGain"]-gr)<=GAIN_TOLERANCE)
    accurate = [f for f in qualified if correct(f)]
    accurate_after = [f for f in after_change if correct(f)]
    reached_change = change is not None and report["stop"]["tick"]>change[0]
    return {
        "frames":len(report["frames"]),
        "qualifiedFrames":len(qualified),
        "correctDelayFrames":sum(f["responseEstimate"]["delay"]==delay for f in qualified),
        "accurateModelFrames":len(accurate),
        "firstQualifiedTick":qualified[0]["tick"] if qualified else None,
        "firstAccurateTick":accurate[0]["tick"] if accurate else None,
        "reachedResponseChange":reached_change,
        "qualifiedAfterChange":len(after_change),
        "accurateAfterChange":len(accurate_after),
        "firstAccuratePostChangeTick":accurate_after[0]["tick"] if accurate_after else None,
    }


def _row(case, cohort):
    trace,speed,delay,gain_name,vg,yg,change,profile = case
    args = dict(speed=speed,delay=delay,profile=profile,
                actual_speed_gain=vg,actual_yaw_gain=yg,response_change=change)
    nominal = run(trace,mode="predict-application",assumed_delay=NOMINAL[0],**args)
    adaptive = run(trace,mode="predict-application",adaptive=True,**args)
    return {"cohort":cohort,"route":trace.route_id,"scenarioSHA256":trace.trace_sha256,
            "speed":speed,"actualDelaySteps":delay,"gainProfile":gain_name,
            "actualGains":[vg,yg],"responseChange":list(change) if change else None,
            "profile":profile,
            "results":{"baseline":{"summary":nominal["summary"],"stop":nominal["stop"],
                                   "admittedSamples":len(nominal["admissions"])},
                       "adaptive":{"summary":adaptive["summary"],"stop":adaptive["stop"],
                                   "admittedSamples":len(adaptive["admissions"]),
                                   "estimator":_metrics(adaptive,delay,vg,yg,change)}}}


def _group(rows):
    usable = [r for r in rows if r["profile"]!="long-dropout"]
    faults = [r for r in rows if r["profile"]=="long-dropout"]
    pairs = paired_metrics(usable,"adaptive")
    estimates = [r["results"]["adaptive"]["estimator"] for r in usable]
    qualified = sum(e["qualifiedFrames"] for e in estimates)
    correct = sum(e["accurateModelFrames"] for e in estimates)
    acquired = [e["firstAccurateTick"]*DT for e in estimates if e["firstAccurateTick"] is not None]
    changed = [e for e in estimates if e["reachedResponseChange"]]
    reacquired = [(e["firstAccuratePostChangeTick"]-SWITCH_TICK)*DT for e in changed
                  if e["firstAccuratePostChangeTick"] is not None]
    common = [r for r in usable if all(v["summary"]["finalModelSettled"]
                                     for v in r["results"].values())]
    slower = sum(r["results"]["adaptive"]["summary"]["totalElapsedSeconds"] >
                 r["results"]["baseline"]["summary"]["totalElapsedSeconds"] for r in common)
    fault_expiries = sum(r["results"]["adaptive"]["stop"]["reason"]=="observation-expired"
                         for r in faults)
    base_mean = pairs["baselineCommonSettledMeans"]
    cand_mean = pairs["candidateCommonSettledMeans"]
    screen = {
        "noSettledLosses":pairs["settledLosses"]==0,
        "allScheduledLongDropoutsExpired":fault_expiries==len(faults),
        "lowerMatchedMeanDuration":bool(base_mean and cand_mean and
            cand_mean["meanTotalElapsedSeconds"]<base_mean["meanTotalElapsedSeconds"]),
    }
    return {"conditions":len(rows),"usable":len(usable),"comparison":pairs,
            "commonSuccessesSlower":slower,"faultCases":len(faults),
            "faultExpiries":fault_expiries,
            "stopReasons":dict(sorted(Counter(r["results"]["adaptive"]["stop"]["reason"]
                                               for r in rows).items())),
            "estimator":{"runsWithAccurateFit":len(acquired),
                         "meanFirstAccurateSeconds":mean(acquired) if acquired else None,
                         "qualifiedFrames":qualified,"accurateQualifiedFrames":correct,
                         "qualifiedAccuracy":correct/qualified if qualified else None,
                         "reachedResponseChange":len(changed),
                         "postChangeAccurateRuns":len(reacquired),
                         "meanPostChangeReacquisitionSeconds":mean(reacquired) if reacquired else None},
            "researchScreen":{**screen,"passed":all(screen.values())}}


def evaluate(*, include_prior=True, include_new=True):
    """Replay prior cases and/or run the newly fixed design; retain every result."""
    if not include_prior and not include_new:
        raise TraceError("adaptive study requires at least one cohort")
    rows = []
    if include_prior:
        rows.extend(_row((t,s,d,n,v,y,None,p),"prior-fixed")
                    for t,s,d,n,v,y,p in prior_cases())
    if include_new:
        rows.extend(_row(c,"new-fixed-and-changing") for c in new_cases())
    cohorts = {name:_group([r for r in rows if r["cohort"]==name])
               for name in dict.fromkeys(r["cohort"] for r in rows)}
    return {"schema":"taxi.synthetic-adaptive-study/1","classification":"SYNTHETIC_ONLY",
            "design":GENERATOR,"dtSeconds":DT,"conditions":len(rows),"executionCount":2*len(rows),
            "gainAccuracyTolerance":GAIN_TOLERANCE,"switchTick":SWITCH_TICK,"cohorts":cohorts,
            "rows":rows,"gameInputSent":False,"physicalQualification":False,
            "limitations":["Authored routes, not statistical or physical validation.",
                           "Actual command latency remains fixed within each run.",
                           "Actuator response may change once; no inertia, noise or collision model.",
                           "Estimator accuracy uses plant truth only for evaluation."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort",choices=("all","prior","new"),default="all")
    parser.add_argument("--summary",action="store_true")
    parser.add_argument("--out",type=Path,help="new JSON output; never overwrite")
    args = parser.parse_args(argv)
    try:
        if args.out is not None and args.out.exists():
            raise FileExistsError(args.out)
        report = evaluate(include_prior=args.cohort!="new",include_new=args.cohort!="prior")
        if args.out is not None:
            with args.out.open("x",encoding="utf-8",newline="\n") as f:
                f.write(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
        if args.summary or args.out is None:
            view = {k:v for k,v in report.items() if k!="rows"} if args.summary else report
            print(json.dumps(view,sort_keys=True,indent=2,allow_nan=False))
        return 0
    except (TraceError,ValueError,OSError) as exc:
        parser.exit(2,f"Adaptive response study refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
