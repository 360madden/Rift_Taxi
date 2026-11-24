"""Fresh authored synthetic evaluation, with frozen policies and delay profiles.

Entry point: evaluate_holdout_v3(). Invented geometry only; no imported
maps, physical devices, game state, input, or changes to the simulator.
All scenarios are defined before evaluation. Preserve this set after any
future tuning, rather than changing its geometry to improve results.
Reuse existing trace construction, trajectory checks and terminal audit.
"""
from collections import Counter
from itertools import product
import math
from statistics import mean

from .simulation import simulate_route
from .simulation_holdout import _case_trace
from .simulation_integrity import verify_synthetic_trajectory
from .simulation_settling import drain_after_arrival

# New geometric challenges: near-parallel return, varying bend angles,
# very short intermediate legs, multiple crossings, translated geometry,
# and a final leg much shorter than the nominal lookahead.
_ROUTES = (
    ("narrow-return", ((0.,0.),(5.,0.),(5.5,.6),(1.,.9),(1.,5.))),
    ("mixed-angle-fan", ((0.,0.),(4.,1.),(6.,4.),(3.,6.),(0.,4.),(-2.,7.))),
    ("short-leg-staircase", ((0.,0.),(2.,0.),(2.,.8),(3.,.8),(3.,2.),(5.,2.),(5.,5.))),
    ("double-crossing", ((0.,0.),(6.,4.),(1.,5.),(5.,0.),(2.,4.),(8.,5.))),
    ("translated-curve", ((-13.,7.),(-10.,8.),(-8.,11.),(-9.,14.),(-12.,16.))),
    ("short-terminal-leg", ((0.,0.),(5.,0.),(5.,5.),(9.,5.),(9.,5.7))),
)
# 6 shapes * 2 offsets * 3 headings * 2 profiles = 72 matched cases.
# Profiles are (synthetic speed units/s, yaw cap degrees/s, dt seconds).
_OFFSETS = (-.6,.4)
_HEADINGS = (-80.,40.,135.)
_PROFILES = ((2.2,65.,.07),(3.4,140.,.11))
_POLICIES = ("fixed","turn-limited","turn-limited-rejoin","turn-limited-ordered")
_DELAYS = (0,1,3)


def evaluate_holdout_v3():
    """Evaluate 72 scenarios under four unchanged zero-delay policies.

    Also evaluate the ordered policy at one and three delayed steps (144
    additional runs), and separately audit its ideal FIFO terminal drain
    for every delay. The 40-second approach budget and 0.30-unit endpoint
    tolerance remain unchanged. No policy is selected or tuned here.
    """
    rows = []
    for (name,xzs), offset, heading, (speed,rate,dt) in product(
            _ROUTES,_OFFSETS,_HEADINGS,_PROFILES):
        dx,dz = xzs[1][0]-xzs[0][0],xzs[1][1]-xzs[0][1]
        length = math.hypot(dx,dz)
        # Offset perpendicular to first leg; initial yaw relative to that
        # leg, not world axes. Keep canonical spec for future reproduction.
        spec = {"routeId":name,"routeXYZ":[[x,0.,z] for x,z in xzs],
                "initialXYZ":[xzs[0][0]-offset*dz/length,0.,xzs[0][1]+offset*dx/length],
                "initialYawDegrees":math.degrees(math.atan2(dz,dx))+heading,
                "lateralOffset":offset,"headingOffsetDegrees":heading,
                "speed":speed,"maxYawRate":rate,"dt":dt}
        trace = _case_trace(spec,generator="taxi-holdout-v3")
        row = {"case":len(rows)+1,"scenarioSHA256":trace.trace_sha256,**spec}
        outcomes = {}
        # Each non-ordered policy gets one run; the ordered policy gets
        # three delay levels. Reuse the zero-delay ordered run for both
        # comparisons rather than executing or counting it twice.
        for policy in _POLICIES:
            for delay in (_DELAYS if policy=="turn-limited-ordered" else (0,)):
                result = simulate_route(trace,speed=speed,max_yaw_rate=rate,dt=dt,
                                        max_seconds=40.,speed_policy=policy,delay_steps=delay)
                verify_synthetic_trajectory(result,trace)
                metrics = result["metrics"]
                outcome = {"speedPolicy":policy,"delaySteps":delay,
                           "nominalDelaySeconds":delay*dt,"status":result["status"],
                           "metrics":metrics,"arrivalAndDutyTarget":(
                               metrics["syntheticArrival"] and metrics["forwardDutyRatio"]>=.95)}
                if policy=="turn-limited-ordered":
                    # Existing terminal audit also verifies ordered corner
                    # witnesses. No extra feedback or settling correction.
                    outcome["terminalDrain"] = drain_after_arrival(result,trace)
                    outcome["syntheticRecovery"] = result["syntheticRecovery"]
                outcomes[f"{policy}:{delay}"] = outcome
        rows.append({**row,"outcomes":outcomes})

    def summarize(group, key):
        values = [r["outcomes"][key] for r in group]
        arrived = [o for o in values if o["metrics"]["syntheticArrival"]]
        drains = [o["terminalDrain"] for o in values if "terminalDrain" in o]
        summary = {"cases":len(values),"geometricArrivals":len(arrived),
                   "arrivalAndDutyTarget":sum(o["arrivalAndDutyTarget"] for o in values),
                   "statusCounts":dict(sorted(Counter(o["status"] for o in values).items())),
                   "meanArrivalSeconds":mean(o["metrics"]["elapsedSeconds"] for o in arrived) if arrived else None}
        if drains:
            summary.update({"settledWithinTolerance":sum(d["settledWithinTolerance"] for d in drains),
                            "sampledToleranceExits":sum(d.get("leftToleranceAtSample",False) for d in drains)})
        return summary

    keys = list(rows[0]["outcomes"])
    return {"schema":"taxi.synthetic-holdout-v3/1","classification":"SYNTHETIC_CLOSED_LOOP_ONLY",
            "scenarioSet":"route-shape-holdout-v3","scenarioCount":len(rows),
            "simulationCount":len(rows)*len(keys),
            "fixedModel":{"lookahead":1.5,"maxSeconds":40.,"maxCrossTrack":2.,
                          "arrivalToleranceXZ":.3,"dutyTarget":.95},
            "summary":{k:summarize(rows,k) for k in keys},
            "byRoute":[{"routeId":name,"summary":{k:summarize([r for r in rows if r["routeId"]==name],k)
                                                 for k in keys}} for name,_ in _ROUTES],
            "cases":rows,"gameInputSent":False,"liveArrivalVerified":False,"liveNavigabilityVerified":False,
            "limitations":["Fresh authored synthetic scenarios, not independently sourced or representative random samples.",
                           "All existing policies frozen; no tuning or promotion based on this report.",
                           "Delay is ideal whole-step command FIFO; settling is passive queue drain after first arrival.",
                           "Frame checks establish internal consistency, not physical ground truth or collision clearance.",
                           "Positive modeled velocity duty is not physical key-down duty."]}
