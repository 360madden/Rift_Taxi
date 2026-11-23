"""Fresh synthetic validation set for the frozen three speed policies.

Entry point: evaluate_holdout_v2(); returns an in-memory JSON-compatible
report. All routes and model profiles are invented and fixed before running
the comparison. No external data, game process, input, or file writes.

Reuse the v1 trace constructor and the established phase-audit helper;
do not duplicate the simulation engine. The v1 case set and report remain
unchanged. Once these results inform a policy change, v2 becomes a
development/regression set rather than an untuned validation set.
"""
from __future__ import annotations

from collections import Counter
from itertools import product
import math
from statistics import mean

from .contracts import MovementTrace, TraceError
from .simulation import simulate_route
from .simulation_holdout import _case_trace
from .simulation_recovery_audit import measure_recovery_phases

# New, authored planar route shapes. Vertices are (X,Z) in synthetic units;
# all Y coordinates are zero. The crossing and closed-loop cases explicitly
# challenge progress/arrival logic when unrelated arc positions are nearby.
# No physical map, collision corridor, or game coordinate is represented.
_ROUTES = (
    ("gentle-arc", ((0.,0.), (3.,.4), (6.,1.5), (8.5,3.5), (10.,6.))),
    ("crossing-bow", ((0.,0.), (5.,5.), (0.,5.), (5.,0.), (9.,0.))),
    ("compact-switchbacks", ((0.,0.), (3.,0.), (3.,1.), (1.,1.), (1.,2.), (5.,2.), (5.,4.))),
    ("acute-return", ((0.,0.), (6.,0.), (2.,1.), (6.,3.), (9.,3.))),
    ("rotated-irregular", ((10.,-4.), (8.,-2.), (7.,2.), (4.,3.), (3.,7.))),
    ("closed-loop", ((0.,0.), (5.,0.), (5.,4.), (0.,4.), (0.,0.))),
)
# New offsets/headings and coupled (speed, yaw cap, timestep) profiles,
# disjoint from the original grids. 6*2*3*3 = 108 cases per policy.
_OFFSETS = (-.35, .95)
_HEADINGS = (-65., 0., 155.)
_PROFILES = ((1.2,55.,.06), (3.2,75.,.09), (4.2,200.,.12))
_POLICIES = ("fixed", "turn-limited", "turn-limited-rejoin")


def _verify_trajectory(result: dict, trace: MovementTrace) -> None:
    """Independently check frame invariants against the reported terminal result.

    This is consistency of a generated trajectory, not independent ground
    truth. No guide vertex is required to be visited precisely. The per-step
    arc advance is limited to twice the actual XZ displacement, and a
    closed-loop arrival cannot be accepted solely because its endpoint is
    already close to the initial position.
    """
    frames = result["frames"]
    metrics = result["metrics"]
    # Recompute the final endpoint distance and route arc from the source
    # geometry, not from the simulator's own arrival flag or summary.
    if not frames:
        raise TraceError("generated holdout trajectory is empty")
    total = sum(math.hypot(b.xyz[0]-a.xyz[0], b.xyz[2]-a.xyz[2])
                for a,b in zip(trace.points, trace.points[1:]))
    final = frames[-1]
    goal = trace.points[-1].xyz
    endpoint = math.hypot(final["xyz"][0]-goal[0], final["xyz"][2]-goal[2])
    if not all(math.isclose(a,b,abs_tol=1e-8,rel_tol=0.) for a,b in (
            (total,metrics["routeLengthXZ"]), (endpoint,metrics["finalXZError"]),
            (final["progress"],metrics["finalProgress"]),
            (final["t"],metrics["elapsedSeconds"]))):
        raise TraceError("generated holdout metrics disagree with trajectory/source geometry")
    for a,b in zip(frames, frames[1:]):
        displacement = math.hypot(b["xyz"][0]-a["xyz"][0], b["xyz"][2]-a["xyz"][2])
        advance = b["progress"]-a["progress"]
        if (advance < -1e-8 or advance > 2.*displacement+1e-8
                or b["t"] <= a["t"]):
            raise TraceError("generated holdout trajectory violates progress/time invariant")
    if frames[-1]["speed"] != 0. or frames[-1]["stepSeconds"] != 0.:
        raise TraceError("generated holdout terminal frame invalid")
    tolerance = trace.arrival_tolerance_xz
    if metrics["syntheticArrival"] and (
            endpoint > tolerance or final["progress"] < total-tolerance):
        raise TraceError("generated holdout arrival violates endpoint/progress requirement")


def _summary(rows: list[dict], policy: str) -> dict:
    """Keep every terminal status in the denominator, including failures."""
    outcomes = [r[policy] for r in rows]
    return {
        "cases":len(rows),
        "arrivals":sum(r["metrics"]["syntheticArrival"] for r in outcomes),
        "arrivalAndDutyTarget":sum(r["arrivalAndDutyTarget"] for r in outcomes),
        "statusCounts":dict(sorted(Counter(r["status"] for r in outcomes).items())),
        "worstCrossTrackErrorXZ":max(r["metrics"]["maxCrossTrackErrorXZ"] for r in outcomes),
    }


def evaluate_holdout_v2() -> dict:
    """Run all three unchanged policies on 108 new matched scenarios.

    Model parameters and tolerances are kept at their prior values except
    for the explicit new initial conditions and coupled motion profiles.
    For the recovery policy, also retain stationary-phase diagnostics using
    the existing audit helper. Store canonical scenario digests and every
    outcome to enable future source-level reproduction of a failure.
    """
    rows = []
    for (name,xzs), offset, heading, (speed,rate,dt) in product(
            _ROUTES, _OFFSETS, _HEADINGS, _PROFILES):
        # Initial offset is perpendicular to the first leg, and yaw offset
        # is relative to that leg. This makes rotated routes comparable.
        dx,dz = xzs[1][0]-xzs[0][0], xzs[1][1]-xzs[0][1]
        length = math.hypot(dx,dz)
        spec = {
            "routeId":name, "routeXYZ":[[x,0.,z] for x,z in xzs],
            "initialXYZ":[xzs[0][0]-offset*dz/length,0.,xzs[0][1]+offset*dx/length],
            "initialYawDegrees":math.degrees(math.atan2(dz,dx))+heading,
            "lateralOffset":offset,"headingOffsetDegrees":heading,
            "speed":speed,"maxYawRate":rate,"dt":dt,
        }
        trace = _case_trace(spec, generator="taxi-holdout-v2")
        row = {"case":len(rows)+1,"scenarioSHA256":trace.trace_sha256,**spec}
        for policy in _POLICIES:
            result = simulate_route(trace, speed=speed, max_yaw_rate=rate, dt=dt,
                                    max_seconds=40., speed_policy=policy)
            _verify_trajectory(result, trace)
            metrics = result["metrics"]
            row[policy] = {"status":result["status"],"metrics":metrics,
                           "arrivalAndDutyTarget":metrics["syntheticArrival"]
                           and metrics["forwardDutyRatio"] >= .95}
            if policy == "turn-limited-rejoin":
                row[policy]["syntheticRecovery"] = result["syntheticRecovery"]
                row[policy]["phaseAudit"] = measure_recovery_phases(result)
        rows.append(row)

    # Compare like with like: timing only for common arrivals. A candidate
    # with more successes must not be credited with faster journeys merely
    # because its successful case population differs from the baseline.
    prior, revised = "turn-limited", "turn-limited-rejoin"
    common = [r for r in rows if r[prior]["metrics"]["syntheticArrival"]
              and r[revised]["metrics"]["syntheticArrival"]]
    return {
        "schema":"taxi.synthetic-holdout-v2/1",
        "classification":"SYNTHETIC_CLOSED_LOOP_ONLY",
        "scenarioSet":"route-shape-holdout-v2",
        "fixedModel":{"lookahead":1.5,"maxSeconds":40.,"maxCrossTrack":2.,
                      "arrivalToleranceXZ":.3,"dutyTarget":.95},
        "summary":{p:_summary(rows,p) for p in _POLICIES},
        "byRoute":[{"routeId":name,**{p:_summary([r for r in rows if r["routeId"]==name],p)
                                     for p in _POLICIES}} for name,_ in _ROUTES],
        "pairedRejoin":{
            "newArrivals":sum(not r[prior]["metrics"]["syntheticArrival"]
                              and r[revised]["metrics"]["syntheticArrival"] for r in rows),
            "lostArrivals":sum(r[prior]["metrics"]["syntheticArrival"]
                               and not r[revised]["metrics"]["syntheticArrival"] for r in rows),
            "newCombinedSuccesses":sum(not r[prior]["arrivalAndDutyTarget"]
                                       and r[revised]["arrivalAndDutyTarget"] for r in rows),
            "lostCombinedSuccesses":sum(r[prior]["arrivalAndDutyTarget"]
                                        and not r[revised]["arrivalAndDutyTarget"] for r in rows),
            "commonArrivals":len(common),
            "meanCommonArrivalSeconds":{p:mean(r[p]["metrics"]["elapsedSeconds"] for r in common)
                                        if common else None for p in (prior,revised)},
        },
        "cases":rows,
        "gameInputSent":False,"liveArrivalVerified":False,"liveNavigabilityVerified":False,
        "limitations":[
            "Fresh authored scenarios, not independently sourced or representative random data.",
            "Frozen ideal model, no measured physical speed, latency, collision or game input.",
            "Frame invariant checks validate internal consistency, not physical ground truth.",
            "Positive modeled velocity duty is not physical key-down duty.",
        ],
    }
