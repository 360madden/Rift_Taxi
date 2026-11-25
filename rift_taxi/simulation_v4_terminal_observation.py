"""Observed V4 terminal-queue diagnostic, separate from the frozen experiment.

No controller changes or physical inputs. Reconstruct only the existing
long-short-ladder cases at 360 ms to inspect the passive FIFO drain. This
is an observed development set, not a fresh validation set.
"""
import json
import math
from collections import Counter
from statistics import mean

from .simulation import simulate_route
from .simulation_holdout import _case_trace
from .simulation_holdout_v4_design import scenarios, GENERATOR
from .simulation_holdout_v4_comparison import BASE_LOOKAHEAD, candidate_lookahead
from .simulation_integrity import verify_synthetic_trajectory
from .simulation_settling import drain_after_arrival


def inspect_terminal(result, trace):
    """Separate geometric arrival, subsequent tolerance exit and endpoint.

    The displacement and endpoint-distance change are different quantities:
    even positive queued distance can initially reduce endpoint error.
    The triangle bound checks sampled kinematic consistency, not clearance.
    """
    verify_synthetic_trajectory(result, trace)
    drain = drain_after_arrival(result, trace)
    if not result["metrics"]["syntheticArrival"]:
        return dict(arrived=False, settled=False, terminal=None)
    initial = drain["firstArrivalErrorXZ"]
    final = drain["settledErrorXZ"]
    travel = drain["postArrivalDistanceXZ"]
    if abs(final - initial) > travel + 1e-8:
        raise ValueError("terminal displacement violates triangle bound")
    observations = drain["observations"]
    return dict(arrived=True, settled=drain["settledWithinTolerance"], terminal=dict(
        firstError=initial, finalError=final, errorChange=final-initial,
        queuedTravel=travel, maxError=drain["maxSampledErrorXZ"],
        leftTolerance=drain["leftToleranceAtSample"],
        drainSeconds=drain["queueDrainSeconds"],
        queue=result.get("syntheticDelay", {}).get("pendingCommands", []),
        observations=observations))


def evaluate():
    """Replay the 12 observed pairs without modifying the source reports."""
    rows = []
    for item in scenarios():
        spec = item["scenario"]
        if spec["routeId"] != "long-short-ladder":
            continue
        trace = _case_trace(spec, generator=GENERATOR)
        if trace.trace_sha256 != item["scenarioSHA256"]:
            raise ValueError("scenario identity mismatch")
        steps = item["delaySteps"][-1]
        if not math.isclose(steps * spec["dt"], .36, abs_tol=1e-12, rel_tol=0.):
            raise ValueError("unexpected nominal delay")
        row = dict(scenarioSHA256=trace.trace_sha256, scenario=spec, delaySeconds=.36)
        for name, lookahead in (("baseline", BASE_LOOKAHEAD),
                                ("candidate", candidate_lookahead(spec["speed"], .36))):
            result = simulate_route(trace, speed=spec["speed"], max_yaw_rate=spec["maxYawRate"],
                                    dt=spec["dt"], lookahead=lookahead, max_seconds=40.,
                                    max_cross_track=2., speed_policy="turn-limited-ordered",
                                    delay_steps=steps)
            row[name] = inspect_terminal(result, trace)
        rows.append(row)
    if len(rows) != 12 or len({r["scenarioSHA256"] for r in rows}) != 12:
        raise ValueError("incomplete terminal diagnostic")
    summary = {}
    for name in ("baseline", "candidate"):
        outcomes = [r[name] for r in rows]
        arrivals = [o["terminal"] for o in outcomes if o["arrived"]]
        summary[name] = dict(arrivals=len(arrivals), settled=sum(o["settled"] for o in outcomes),
                             sampledExits=sum(t["leftTolerance"] for t in arrivals),
                             meanQueuedTravel=mean(t["queuedTravel"] for t in arrivals) if arrivals else None,
                             meanErrorChange=mean(t["errorChange"] for t in arrivals) if arrivals else None)
    return dict(schema="taxi.synthetic-v4-terminal-observation/1", pairs=len(rows),
                summary=summary, rows=rows, physicalQualification=False, gameInputSent=False)


if __name__ == "__main__":
    print(json.dumps(evaluate(), sort_keys=True, allow_nan=False))
