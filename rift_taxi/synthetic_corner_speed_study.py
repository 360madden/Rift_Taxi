"""Prespecified comparison of faster synthetic corner approach.

Historical baseline is a pinned, locally audited archive; its conditions
are regenerated and matched exactly before using any archived result.
The separate fresh cohort is authored before results and both policies
are executed. No measurement envelope, passage radius, arrival criterion,
plant model, or observation transport policy is relaxed. Offline only.
"""
import argparse
import hashlib
from itertools import product
import json
from pathlib import Path

from .contracts import TraceError
from .simulation_holdout import _case_trace
from .synthetic_sampled_steering import run, DT
from .synthetic_corner_study import prior_cases, new_cases as previous_new_cases
from .synthetic_robust_study import estimator_metrics
from .synthetic_journey_batch import paired_metrics
from .synthetic_corner_speed import BASE_GAIN, EXTRA_GAIN, KNEE_XZ

GENERATOR = "taxi-corner-speed-20261127-v1"
PRIOR_SHA256 = "45f72a4f4cfbfe96291bfc351137e3e93c8f174c2e25393539514d353db946e4"
ROUTES = (
    ("four-turn-ladder", ((0,0,0),(6,0,1),(3,0,4),(9,0,7),(6,0,10),(13,0,13))),
    ("rotated-tight-switchback", ((9,0,-4),(5,0,0),(8,0,-1),(4,0,5),(7,0,4),(1,0,11))),
)
MOTION = ((2.6,3),(3.3,8))
RESPONSE = (("mixed-fixed",.95,1.15,None),
            ("late-slow",1.1,1.2,(96,.8,.75)))
NOISE = ("moderate","impulse")
TRANSPORT = ("steady-delay","short-dropout","long-dropout")
IDENTITY_FIELDS = ("route","scenarioSHA256","speed","actualDelaySteps","gainProfile",
                   "actualGains","responseChange","sensorNoise","profile")


def fresh_cases():
    """48 matched conditions; different geometry, latency and response profiles."""
    for (name,points),(speed,delay),(gain,vg,yg,change),noise,profile in product(
            ROUTES,MOTION,RESPONSE,NOISE,TRANSPORT):
        seed=points[0]
        yaw=15. if name=="four-turn-ladder" else 132.
        trace=_case_trace({"routeId":name,"routeXYZ":[list(p) for p in points],
                           "initialXYZ":[seed[0],seed[1],seed[2]+.16],
                           "initialYawDegrees":yaw},generator=GENERATOR)
        yield trace,speed,delay,gain,vg,yg,change,noise,profile


def identity(case):
    t,s,d,g,v,y,ch,n,p=case
    return {"route":t.route_id,"scenarioSHA256":t.trace_sha256,
            "speed":s,"actualDelaySteps":d,"gainProfile":g,
            "actualGains":[v,y],"responseChange":list(ch) if ch else None,
            "sensorNoise":n,"profile":p}


def key(record):
    # JSON preserves array structure and distinguishes complete case identity.
    return json.dumps([record[k] for k in IDENTITY_FIELDS],separators=(",",":"),allow_nan=False)


def previous_design():
    for case in prior_cases():
        yield "prior-development",case
    for case in previous_new_cases():
        yield "new-fixed",case


def load_baseline(raw):
    """Verify the original bytes, schema, and one-to-one historical identities."""
    if hashlib.sha256(raw).hexdigest()!=PRIOR_SHA256:
        raise TraceError("prior corner study SHA-256 mismatch")
    data=json.loads(raw)
    if (data.get("schema")!="taxi.synthetic-bounded-corner-study/1"
            or data.get("gameInputSent") is not False
            or data.get("physicalQualification") is not False
            or data.get("caseCount")!=192 or data.get("executionCount")!=576
            or len(data["rows"])!=192):
        raise TraceError("unexpected historical study declaration")
    table={}
    for row in data["rows"]:
        k=key(row)
        if k in table:
            raise TraceError("duplicate historical condition")
        table[k]=row
    expected={key(identity(case)):cohort for cohort,case in previous_design()}
    if len(expected)!=192 or set(expected)!=set(table):
        raise TraceError("historical condition mismatch")
    if any(table[k]["cohort"]!=c for k,c in expected.items()):
        raise TraceError("historical cohort mismatch")
    return table


def simulate(case,policy):
    t,s,d,g,v,y,ch,n,p=case
    report=run(t,speed=s,delay=d,profile=p,mode="predict-application",
               actual_speed_gain=v,actual_yaw_gain=y,response_change=ch,
               sensor_noise=n,adaptive=True,adaptive_policy="robust",
               corner_policy=policy)
    return {"summary":report["summary"],"stop":report["stop"],
            "admittedSamples":len(report["admissions"]),
            "estimator":estimator_metrics(report,d,v,y,ch),
            "certificates":report["sharpWitnesses"]}


def paired_row(case,cohort,archived=None):
    return {**identity(case),"cohort":cohort,
            "baselineSource":"pinned-archive" if archived is not None else "current-execution",
            "results":{"baseline":archived if archived is not None else simulate(case,"bounded"),
                       "taper":simulate(case,"bounded-taper")}}


def summarize(rows):
    """Do not include intentional fault cases in the elapsed-time comparison."""
    usable=[r for r in rows if r["profile"]!="long-dropout"]
    faults=[r for r in rows if r["profile"]=="long-dropout"]
    paired=paired_metrics(usable,"taper")
    good=[r for r in usable if all(r["results"][m]["summary"]["finalModelSettled"]
                                    for m in ("baseline","taper"))]
    times=[r["results"]["taper"]["summary"]["totalElapsedSeconds"]-
           r["results"]["baseline"]["summary"]["totalElapsedSeconds"] for r in good]
    certificates=[w for r in rows for w in r["results"]["taper"]["certificates"]]
    bad=sum(r["results"]["taper"]["summary"]["truthSharpWitnessesValid"] is not True for r in rows)
    violations=sum(w["upperDistanceXZ"]>w["radiusXZ"] for w in certificates)
    expired=sum(r["results"]["taper"]["stop"]["reason"]=="observation-expired" for r in faults)
    # Prespecified gates: preserve every baseline success; improve mean
    # duration on common successes; preserve fault and certificate evidence.
    screen={"noSettledLosses":paired["settledLosses"]==0,
            "fasterCommonMean":bool(times) and sum(times)<0.,
            "allDropoutsExpired":expired==len(faults),
            "noTruthWitnessFailures":bad==0,
            "noCertificateViolations":violations==0}
    return {"conditions":len(rows),"usable":len(usable),"faultCases":len(faults),
            "faultExpiries":expired,"comparison":paired,
            "faster":sum(t<0 for t in times),"equal":sum(t==0 for t in times),
            "slower":sum(t>0 for t in times),"worstSlowdownSeconds":max([0.]+times),
            "certificates":len(certificates),"certificateViolations":violations,
            "truthWitnessFailures":bad,
            "researchScreen":{**screen,"passed":all(screen.values())}}


def evaluate(baseline):
    previous=[paired_row(c,"archived-"+cohort,baseline[key(identity(c))]["results"]["bounded"])
              for cohort,c in previous_design()]
    fresh=[paired_row(c,"fresh-fixed") for c in fresh_cases()]
    rows=previous+fresh
    if len({key(r) for r in rows})!=len(rows):
        raise TraceError("duplicate combined condition")
    groups={"archived":summarize(previous),"fresh":summarize(fresh)}
    return {"schema":"taxi.synthetic-corner-speed-study/1","classification":"SYNTHETIC_ONLY",
            "design":GENERATOR,"sourceArchiveSHA256":PRIOR_SHA256,"dtSeconds":DT,
            "candidate":{"baseGain":BASE_GAIN,"extraGain":EXTRA_GAIN,"kneeXZ":KNEE_XZ},
            "caseCount":len(rows),"archivedBaselineCount":len(previous),
            "newExecutionCount":len(previous)+2*len(fresh),
            "comparisonCount":2*len(rows),"cohorts":groups,
            "overall":summarize(rows),"allCohortScreensPassed":all(
                v["researchScreen"]["passed"] for v in groups.values()),
            "rows":rows,"gameInputSent":False,"physicalQualification":False,
            "limitations":["Pinned archived historical comparator, not a new execution.",
                           "Fresh cohort is authored synthetic geometry, not statistical validation.",
                           "Planar ideal plant and bounded deterministic measurement errors.",
                           "No collision, physical actuator, or live qualification."]}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prior",type=Path,required=True,help="original pinned 192-condition archive")
    p.add_argument("--out",type=Path,required=True,help="new JSON report; never overwrite")
    p.add_argument("--summary",action="store_true")
    args=p.parse_args(argv)
    try:
        if args.out.exists():
            raise FileExistsError(args.out)
        report=evaluate(load_baseline(args.prior.read_bytes()))
        with args.out.open("x",encoding="utf-8",newline="\n") as f:
            f.write(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
        if args.summary:
            print(json.dumps({k:v for k,v in report.items() if k!="rows"},
                             sort_keys=True,indent=2,allow_nan=False))
        return 0
    except (TraceError,ValueError,OSError) as exc:
        p.exit(2,f"Corner speed study refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
