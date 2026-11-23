"""Untuned synthetic route-shape/initial-condition holdout for both speed policies.

Fixed scenarios authored after the original development-grid tuning; neither
policy is changed by this evaluation. Not physical game acceptance evidence.

Entry point: evaluate_holdout() (also exposed by the offline CLI).
Inputs: immutable built-in route shapes, initial offsets and model profiles.
Output: per-case paired outcomes, scenario hashes, group summaries and limitations.
No file I/O, process inspection, game input, randomness, or external dependencies.
Keep v1 scenarios unchanged when fixing a failure: use this as a regression
baseline and introduce a separate version for genuinely new holdouts.
"""
from __future__ import annotations

from collections import Counter
import hashlib
from itertools import product
import json
import math
from statistics import mean

from .contracts import MovementTrace, Point, PoseSample
from .simulation import simulate_route

# All geometry is invented, flat, and unconstrained. No imported game map.
# Each shape stresses a distinct geometric condition: no turns, unequal turn
# angles, close parallel legs, closely spaced turns, destination near start,
# and short/long segment transitions. The short-zigzag is particularly useful
# for exposing a locally valid lookahead that becomes coincident with the pose.
# Do not remove failed cases or adapt these definitions after observing outcomes.
_ROUTES = (
    ("straight", ((0.,0.), (14.,0.))),
    ("oblique-dogleg", ((0.,0.), (5.,3.), (10.,3.), (13.,7.))),
    ("hairpin", ((0.,0.), (6.,0.), (6.,2.5), (1.,2.5), (1.,6.))),
    ("short-zigzag", ((0.,0.), (2.,0.), (3.,2.), (5.,0.), (7.,2.), (9.,0.))),
    ("return-near-start", ((0.,0.), (6.,0.), (6.,5.), (0.,5.), (0.,.5))),
    ("uneven-bends", ((0.,0.), (1.2,0.), (2.,1.5), (8.,1.5), (9.,4.5), (12.,5.))),
)
# These values are deliberately outside the prior development grid. Profiles
# are (nominal units/s, maximum degrees/s, integration timestep in seconds);
# they are coupled profiles rather than an independent Cartesian sweep of
# every speed, yaw rate and timestep. 6*3*3*3 = 162 paired cases.
_OFFSETS = (-.75, 0., .75)
_HEADINGS = (-120., 25., 110.)
_PROFILES = ((2.6,90.,.075), (3.6,45.,.125), (1.7,150.,.04))


def _case_trace(spec: dict) -> MovementTrace:
    """Build an in-memory synthetic trace without inventing recorded poses.

    The simulator consumes route geometry and one initial pose only. The
    canonical digest covers the complete scenario specification including
    its initial conditions; it is not a hash of an external trace file.
    """
    # Canonical scenario hash identifies the generated input, not a source file.
    digest = hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",",":"),
                                      allow_nan=False).encode("utf-8")).hexdigest()
    xyzs = [tuple(p) for p in spec["routeXYZ"]]
    points = tuple(Point(f"p{i}", "destination" if i == len(xyzs)-1 else "guide", p)
                   for i,p in enumerate(xyzs))
    return MovementTrace(
        source_type="synthetic", source={"generator":"taxi-holdout-v1"},
        frame={"frameId":"synthetic-local-xyz","axisOrder":["x","y","z"],
               "upAxis":"y","units":"synthetic-units"},
        route_id=spec["routeId"], points=points, arrival_tolerance_xz=.3,
        window_start=0., window_end=1.,
        poses=(PoseSample(0., tuple(spec["initialXYZ"]), spec["initialYawDegrees"]),),
        events=(), trace_sha256=digest, verified_source_sha256=None,
    )


def evaluate_holdout() -> dict:
    """Evaluate both unchanged policies on exactly the same 162 scenarios.

    Each simulation has the same 40-second timeout, 2-unit cross-track limit,
    1.5-unit lookahead and 0.30-unit arrival tolerance. A modeled arrival
    plus >=95% positive-velocity duty is counted separately from arrival.
    Retain every failure and every parameter override for future AI diagnosis.
    """
    cases = []
    for (name,xzs), offset, heading, (speed,rate,dt) in product(
            _ROUTES, _OFFSETS, _HEADINGS, _PROFILES):
        # Place initial offset along the left normal of the first XZ segment.
        # Heading offset is relative to its bearing, not global +X, which
        # matters for the oblique dogleg and any future rotated route.
        dx,dz = xzs[1][0]-xzs[0][0], xzs[1][1]-xzs[0][1]
        length = math.hypot(dx,dz)
        spec = {
            "routeId":name, "routeXYZ":[[x,0.,z] for x,z in xzs],
            "initialXYZ":[xzs[0][0]-offset*dz/length, 0., xzs[0][1]+offset*dx/length],
            "initialYawDegrees":math.degrees(math.atan2(dz,dx))+heading,
            "lateralOffset":offset, "headingOffsetDegrees":heading,
            "speed":speed, "maxYawRate":rate, "dt":dt,
        }
        trace = _case_trace(spec)
        row = {"case":len(cases)+1, "scenarioSHA256":trace.trace_sha256, **spec}
        # Both policies receive the identical immutable trace and model
        # bounds. Keep per-case metrics, not only aggregate success rates.
        for policy in ("fixed","turn-limited"):
            result = simulate_route(trace, speed=speed, max_yaw_rate=rate, dt=dt,
                                    max_seconds=40., speed_policy=policy)
            metrics = result["metrics"]
            row[policy] = {
                "status":result["status"], "metrics":metrics,
                "arrivalAndDutyTarget": metrics["syntheticArrival"] and
                                        metrics["forwardDutyRatio"] >= .95,
            }
        cases.append(row)

    def summarize(rows, policy):
        """Aggregate one policy without dropping timeout or refusal cases."""
        results = [r[policy] for r in rows]
        arrivals = [r for r in results if r["metrics"]["syntheticArrival"]]
        return {"cases":len(rows), "arrivals":len(arrivals),
                "arrivalAndDutyTarget":sum(r["arrivalAndDutyTarget"] for r in results),
                "statusCounts":dict(sorted(Counter(r["status"] for r in results).items())),
                "worstCrossTrackErrorXZ":max(r["metrics"]["maxCrossTrackErrorXZ"] for r in results)}

    # Compare timing only on cases both policies completed; comparing their
    # separate successful populations would confound timing with rescue/failure.
    common = [r for r in cases if all(r[p]["metrics"]["syntheticArrival"]
                                     for p in ("fixed","turn-limited"))]
    return {
        "schema":"taxi.synthetic-holdout/1",
        "classification":"SYNTHETIC_CLOSED_LOOP_ONLY",
        "scenarioSet":"route-shape-holdout-v1",
        "fixedModel":{"lookahead":1.5,"maxSeconds":40.,"maxCrossTrack":2.,
                      "arrivalToleranceXZ":.3,"dutyTarget":.95},
        "summary":{p:summarize(cases,p) for p in ("fixed","turn-limited")},
        "paired":{
            "newArrivals":sum(not r["fixed"]["metrics"]["syntheticArrival"] and
                              r["turn-limited"]["metrics"]["syntheticArrival"] for r in cases),
            "lostArrivals":sum(r["fixed"]["metrics"]["syntheticArrival"] and
                               not r["turn-limited"]["metrics"]["syntheticArrival"] for r in cases),
            "newCombinedSuccesses":sum(not r["fixed"]["arrivalAndDutyTarget"] and
                                       r["turn-limited"]["arrivalAndDutyTarget"] for r in cases),
            "lostCombinedSuccesses":sum(r["fixed"]["arrivalAndDutyTarget"] and
                                        not r["turn-limited"]["arrivalAndDutyTarget"] for r in cases),
            "commonArrivals":len(common),
            "meanCommonArrivalSeconds":{p:mean(r[p]["metrics"]["elapsedSeconds"] for r in common)
                                        if common else None for p in ("fixed","turn-limited")},
        },
        "byRoute":[{"routeId":name, **{p:summarize([r for r in cases if r["routeId"]==name],p)
                                     for p in ("fixed","turn-limited")}} for name,_ in _ROUTES],
        "cases":cases,
        "gameInputSent":False, "liveArrivalVerified":False,
        "liveNavigabilityVerified":False,
        "limitations":[
            "Fixed authored synthetic holdout, not an independently sourced or randomized sample.",
            "Both policies are unchanged from the preceding development grid.",
            "No physical game geometry, input, latency, collision or continuous speed capability is established.",
            "Combined target uses positive model velocity, not measured physical key duty.",
        ],
    }
