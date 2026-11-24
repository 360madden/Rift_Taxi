"""Matched synthetic sensitivity study on previously observed V3 geometry.

Entry point: evaluate_delay_factorial(), via study-delay-factors. No I/O,
native observations, or game access. Reuse the unchanged ordered policy,
trace builder, trajectory verifier and terminal FIFO drain. This is a
development diagnostic, not a new holdout or calibrated actuator model.

V3 coupled speed, yaw cap and timestep into two profiles. Here cross the
two speeds and yaw caps with a halved timestep and matched nominal delay
in seconds. This separates factors within the ideal plant; changing dt
also changes integration and control sampling, so those effects are not
individually identified.
"""
from collections import Counter
from itertools import product
import math

from .contracts import TraceError
from .simulation import simulate_route
from .simulation_holdout import _case_trace
from .simulation_holdout_v3 import _ROUTES, _OFFSETS, _HEADINGS
from .simulation_integrity import verify_synthetic_trajectory
from .simulation_settling import drain_after_arrival

_SPEEDS = (2.2, 3.4)
_YAW_RATES = (65., 140.)
# .055 is exactly half of the original high-profile timestep. Whole-step
# delay is represented by integers so nominal time is matched at each dt.
_TIMESTEPS = (.055, .11)
_DELAY_SECONDS = (0., .11, .33)
_POLICY = "turn-limited-ordered"
_FACTOR_NAMES = ("speed", "maxYawRate", "dt")
_OUTCOMES = ("geometricArrival", "settledWithinTolerance", "arrivalAndDutyTarget")


def _summarize(rows):
    """Count every run, including failed approaches and unsettled arrivals."""
    return {
        "runs": len(rows),
        "geometricArrivals": sum(r["geometricArrival"] for r in rows),
        "settledWithinTolerance": sum(r["settledWithinTolerance"] for r in rows),
        "arrivalAndDutyTarget": sum(r["arrivalAndDutyTarget"] for r in rows),
        "settledOutside": sum(r["geometricArrival"] and not r["settledWithinTolerance"] for r in rows),
        "statusCounts": dict(sorted(Counter(r["status"] for r in rows).items())),
    }


def _matched_effects(rows):
    """Compare low->high factor values, holding every other factor fixed.

    Pair by geometry/initial condition and all other model factors; retain
    gains and losses separately, not just a potentially misleading net
    change. Nominal delay seconds are held constant, not delay step count.
    These are deterministic grid counts, not statistical estimates.
    """
    effects = []
    for factor in _FACTOR_NAMES:
        other = tuple(name for name in _FACTOR_NAMES if name != factor)
        low, high = sorted({row[factor] for row in rows})
        for delay in _DELAY_SECONDS:
            groups = {}
            for row in rows:
                if row["nominalDelaySeconds"] != delay:
                    continue
                key = (row["geometryCase"], *(row[name] for name in other))
                pair = groups.setdefault(key, {})
                if row[factor] in pair:
                    raise TraceError("duplicate matched factor outcome")
                pair[row[factor]] = row
            counts = {name: {"gained": 0, "lost": 0, "both": 0, "neither": 0}
                      for name in _OUTCOMES}
            for pair in groups.values():
                if set(pair) != {low, high}:
                    raise TraceError("incomplete matched factor pair")
                for name in _OUTCOMES:
                    a, b = pair[low][name], pair[high][name]
                    category = "both" if a and b else "lost" if a else "gained" if b else "neither"
                    counts[name][category] += 1
            effects.append({"factor": factor, "low": low, "high": high,
                            "nominalDelaySeconds": delay, "pairs": len(groups),
                            "outcomes": counts})
    return effects


def evaluate_delay_factorial():
    """Run 36 matched starts x 24 profiles = 864 deterministic simulations.

    Keep the original V3 geometry/initial offsets/headings and the ordered
    policy's 40-second approach budget, 1.5-unit lookahead, 2-unit deviation
    limit, .30-unit arrival tolerance and 95% modeled forward-duty target.
    Reuse the V3 trace generator ID: the original high-profile scenarios
    therefore retain the exact V3 source hashes. Each new row records
    original status, endpoint and drain metrics for subsequent audits.
    """
    rows = []
    geometry = []
    for case, ((name, xzs), offset, heading) in enumerate(
            product(_ROUTES, _OFFSETS, _HEADINGS), start=1):
        dx, dz = xzs[1][0] - xzs[0][0], xzs[1][1] - xzs[0][1]
        length = math.hypot(dx, dz)
        base = {"routeId": name, "routeXYZ": [[x, 0., z] for x, z in xzs],
                "initialXYZ": [xzs[0][0] - offset * dz / length, 0.,
                               xzs[0][1] + offset * dx / length],
                "initialYawDegrees": math.degrees(math.atan2(dz, dx)) + heading,
                "lateralOffset": offset, "headingOffsetDegrees": heading}
        geometry.append({"geometryCase": case, **base})
        for speed, rate, dt in product(_SPEEDS, _YAW_RATES, _TIMESTEPS):
            spec = {**base, "speed": speed, "maxYawRate": rate, "dt": dt}
            trace = _case_trace(spec, generator="taxi-holdout-v3")
            for delay in _DELAY_SECONDS:
                steps = round(delay / dt)
                # Verify that the chosen design is representable by the
                # simulator's bounded integer command queue. Never round an
                # arbitrary physical delay to fit this model silently.
                if not 0 <= steps <= 10 or not math.isclose(steps * dt, delay, abs_tol=1e-12, rel_tol=0.):
                    raise TraceError("factorial delay not representable")
                result = simulate_route(trace, speed=speed, max_yaw_rate=rate,
                                        dt=dt, max_seconds=40., speed_policy=_POLICY,
                                        delay_steps=steps)
                verify_synthetic_trajectory(result, trace)
                drain = drain_after_arrival(result, trace)
                metrics = result["metrics"]
                arrived = metrics["syntheticArrival"]
                rows.append({"geometryCase": case, "routeId": name,
                             "scenarioSHA256": trace.trace_sha256,
                             "speed": speed, "maxYawRate": rate, "dt": dt,
                             "nominalDelaySeconds": delay, "delaySteps": steps,
                             "status": result["status"], "geometricArrival": arrived,
                             "settledWithinTolerance": drain["settledWithinTolerance"],
                             "arrivalAndDutyTarget": arrived and metrics["forwardDutyRatio"] >= .95,
                             "elapsedSeconds": metrics["elapsedSeconds"],
                             "forwardDutyRatio": metrics["forwardDutyRatio"],
                             "finalProgress": metrics["finalProgress"],
                             "finalXZError": metrics["finalXZError"],
                             "settledErrorXZ": drain.get("settledErrorXZ"),
                             "postArrivalDistanceXZ": drain.get("postArrivalDistanceXZ"),
                             "orderedCornersPassed": result["syntheticRecovery"]["orderedSharpCornersPassed"]})
    profiles = []
    for speed, rate, dt, delay in product(_SPEEDS, _YAW_RATES, _TIMESTEPS, _DELAY_SECONDS):
        group = [r for r in rows if (r["speed"], r["maxYawRate"], r["dt"],
                                    r["nominalDelaySeconds"]) == (speed, rate, dt, delay)]
        if len(group) != len(geometry):
            raise TraceError("factorial profile coverage mismatch")
        profiles.append({"speed": speed, "maxYawRate": rate, "dt": dt,
                         "nominalDelaySeconds": delay, **_summarize(group)})
    return {"schema": "taxi.synthetic-delay-factorial/1",
            "classification": "SYNTHETIC_CLOSED_LOOP_ONLY",
            "scenarioSet": "observed-route-shape-holdout-v3-factorial",
            "geometryCount": len(geometry), "profileCount": len(profiles),
            "simulationCount": len(rows), "speedPolicy": _POLICY,
            "fixedModel": {"lookahead": 1.5, "maxSeconds": 40., "maxCrossTrack": 2.,
                           "arrivalToleranceXZ": .3, "dutyTarget": .95},
            "geometry": geometry, "profiles": profiles,
            "byDelay": [{"nominalDelaySeconds": delay, **_summarize(
                [r for r in rows if r["nominalDelaySeconds"] == delay])} for delay in _DELAY_SECONDS],
            "matchedEffects": _matched_effects(rows), "cases": rows,
            "gameInputSent": False, "liveArrivalVerified": False,
            "limitations": [
                "Previously observed authored V3 geometry; not independent holdout validation.",
                "Nominal command delay is matched in seconds using whole-step FIFO; dt changes both integration and command sampling.",
                "Synthetic factor effects may interact; not physical causal effects or a reason to promote a policy.",
                "Settling is passive queue drain; modeled positive speed duty is not key duty.",
            ]}
