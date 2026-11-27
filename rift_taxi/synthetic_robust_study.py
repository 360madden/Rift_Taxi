"""Fixed comparison of legacy and robust adaptive response estimation.

Compare three research controllers on identical deterministic sensor noise,
transport, and plant conditions. No controller is told the true latency,
gains, future response changes, or ground-truth pose. Ground truth is used
only for retrospective scoring. No live game, input, or physical claims.
"""
import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path
from statistics import mean

from .contracts import TraceError
from .simulation_holdout import _case_trace
from .synthetic_sampled_steering import run, DT
from .synthetic_sensor_noise import PROFILES as NOISE_PROFILES
from .synthetic_response_estimator import NOMINAL
from .synthetic_journey_batch import paired_metrics

GENERATOR = "taxi-robust-response-20261127-v1"
ROUTES = (
    ("sweep-and-bend", ((0,0,0),(5,0,3),(10,0,3),(14,0,7),(21,0,6))),
    ("sharp-offset", ((0,0,0),(7,0,1),(3,0,4),(11,0,8),(18,0,6),(23,0,9))),
)
# Keep the coupled movement/latency profiles fixed to limit the comparison.
MOTION = ((2.5,1),(3.4,7))
SWITCH_TICK = 64
RESPONSES = (("fixed-cross",.9,1.2,None),
             ("slow-to-fast",.8,.7,(SWITCH_TICK,1.2,1.3)))
TRANSPORT = ("steady-delay","jitter-in-order","long-dropout")
GAIN_TOLERANCE = .05
MODES = ("baseline","legacy","robust")


def cases():
    """96 matched cases; 64 usable transport and 32 deliberate dropouts."""
    for (name,points),(speed,delay),(gain,vg,yg,change),noise,transport in product(
            ROUTES,MOTION,RESPONSES,NOISE_PROFILES,TRANSPORT):
        trace=_case_trace({"routeId":name,"routeXYZ":[list(p) for p in points],
                           "initialXYZ":[0.,0.,.18],"initialYawDegrees":-10.},
                          generator=GENERATOR)
        yield trace,speed,delay,gain,vg,yg,change,noise,transport


def estimator_metrics(report,delay,vg,yg,change):
    """Keep coverage, accuracy, and response-change latency separate."""
    frames=report["frames"]
    qualified=[f for f in frames if f["responseEstimate"]["qualified"]]
    def correct(f):
        e=f["responseEstimate"]
        gv,gr=change[1:] if change is not None and f["tick"]>=change[0] else (vg,yg)
        return (e["delay"]==delay and abs(e["speedGain"]-gv)<=GAIN_TOLERANCE
                and abs(e["yawGain"]-gr)<=GAIN_TOLERANCE)
    accurate=[f for f in qualified if correct(f)]
    post=[f for f in accurate if change is not None and f["tick"]>=change[0]]
    return {"frames":len(frames),"qualifiedFrames":len(qualified),
            "accurateFrames":len(accurate),
            "correctDelayFrames":sum(f["responseEstimate"]["delay"]==delay for f in qualified),
            "firstAccurateTick":accurate[0]["tick"] if accurate else None,
            "reachedResponseChange":change is not None and report["stop"]["tick"]>change[0],
            "firstAccuratePostChangeTick":post[0]["tick"] if post else None,
            "changeResets":max((f["responseEstimate"].get("changeResets",0)
                                for f in frames),default=0)}


def row(case):
    trace,speed,delay,gain,vg,yg,change,noise,transport=case
    opts=dict(speed=speed,delay=delay,profile=transport,mode="predict-application",
              actual_speed_gain=vg,actual_yaw_gain=yg,response_change=change,
              sensor_noise=noise)
    results={}
    for mode in MODES:
        if mode=="baseline":
            report=run(trace,assumed_delay=NOMINAL[0],**opts)
        else:
            report=run(trace,adaptive=True,adaptive_policy=mode,**opts)
        result={"summary":report["summary"],"stop":report["stop"],
                "admittedSamples":len(report["admissions"])}
        if mode!="baseline":
            result["estimator"]=estimator_metrics(report,delay,vg,yg,change)
        results[mode]=result
    return {"route":trace.route_id,"scenarioSHA256":trace.trace_sha256,
            "speed":speed,"actualDelaySteps":delay,"gainProfile":gain,
            "actualGains":[vg,yg],"responseChange":list(change) if change else None,
            "sensorNoise":noise,"profile":transport,"results":results}


def estimator_summary(rows,mode):
    estimates=[r["results"][mode]["estimator"] for r in rows]
    q=sum(e["qualifiedFrames"] for e in estimates)
    total=sum(e["frames"] for e in estimates)
    accurate=sum(e["accurateFrames"] for e in estimates)
    learned=[e["firstAccurateTick"]*DT for e in estimates if e["firstAccurateTick"] is not None]
    changed=[e for e in estimates if e["reachedResponseChange"]]
    reacquired=[(e["firstAccuratePostChangeTick"]-SWITCH_TICK)*DT for e in changed
                if e["firstAccuratePostChangeTick"] is not None]
    return {"runsWithAccurateFit":len(learned),"frames":total,"qualifiedFrames":q,
            "accurateFrames":accurate,"coverage":q/total if total else None,
            "conditionalAccuracy":accurate/q if q else None,
            "correctDelayFrames":sum(e["correctDelayFrames"] for e in estimates),
            "meanFirstAccurateSeconds":mean(learned) if learned else None,
            "reachedChange":len(changed),"postChangeAccurateRuns":len(reacquired),
            "meanReacquisitionSeconds":mean(reacquired) if reacquired else None,
            "changeResets":sum(e["changeResets"] for e in estimates)}


def summarize(rows):
    usable=[r for r in rows if r["profile"]!="long-dropout"]
    faults=[r for r in rows if r["profile"]=="long-dropout"]
    legacy_views=[{"results":{"baseline":r["results"]["legacy"],"robust":r["results"]["robust"]}}
                  for r in usable]
    paired=paired_metrics(legacy_views,"robust")
    estimators={m:estimator_summary(usable,m) for m in MODES[1:]}
    expiries={m:sum(r["results"][m]["stop"]["reason"]=="observation-expired" for r in faults)
              for m in MODES}
    witness_failures={m:sum(r["results"][m]["summary"].get("truthSharpWitnessesValid") is False
                            for r in usable) for m in MODES}
    a=estimators["legacy"]["meanReacquisitionSeconds"]
    b=estimators["robust"]["meanReacquisitionSeconds"]
    screen={"noLegacySettledLosses":paired["settledLosses"]==0,
            "allRobustLongDropoutsExpired":expiries["robust"]==len(faults),
            "noLostReacquisitions":estimators["robust"]["postChangeAccurateRuns"]>=estimators["legacy"]["postChangeAccurateRuns"],
            "fasterMeanReacquisition":bool(a is not None and b is not None and b<a)}
    return {"conditions":len(rows),"usable":len(usable),
            "versusNominal":{m:paired_metrics(usable,m) for m in MODES[1:]},
            "robustVersusLegacy":paired,"estimators":estimators,
            "faultCases":len(faults),"faultExpiries":expiries,
            "truthWitnessFailures":witness_failures,
            "stopReasons":{m:dict(sorted(Counter(r["results"][m]["stop"]["reason"]
                                                 for r in rows).items())) for m in MODES},
            "researchScreen":{**screen,"passed":all(screen.values())}}


def evaluate():
    rows=[row(c) for c in cases()]
    return {"schema":"taxi.synthetic-robust-response-study/1","classification":"SYNTHETIC_ONLY",
            "design":GENERATOR,"dtSeconds":DT,"caseCount":len(rows),
            "executionCount":len(rows)*len(MODES),"gainAccuracyTolerance":GAIN_TOLERANCE,
            "switchTick":SWITCH_TICK,"overall":summarize(rows),
            "byNoise":{n:summarize([r for r in rows if r["sensorNoise"]==n])
                       for n in NOISE_PROFILES},
            "rows":rows,"gameInputSent":False,"physicalQualification":False,
            "limitations":["Deterministic bounded noise; no statistical or physical calibration.",
                           "Fixed whole-tick command latency, at most one gain change.",
                           "Truth checks are retrospective, not available to controllers.",
                           "No inertia, collision or physical release modeled."]}


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
            view={k:v for k,v in report.items() if k!="rows"} if args.summary else report
            print(json.dumps(view,sort_keys=True,indent=2,allow_nan=False))
        return 0
    except (TraceError,ValueError,OSError) as exc:
        parser.exit(2,f"Robust response study refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
