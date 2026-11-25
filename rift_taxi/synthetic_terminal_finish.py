"""Experimental terminal-only recovery on an ideal synthetic plant.

The approach and passive FIFO drain are immutable inputs to this experiment.
Only after the prior queue is empty do we model a bounded corrective maneuver.
This is not a RIFT actuator, a collision model, or a live authorization.
"""
from collections import deque
import json
import math

from .simulation import _bounded_number
from .steering import _angle_delta


def finish_after_drain(*, xyz, yaw, goal, dt, speed, yaw_rate, delay_steps,
                       tolerance=.3, budget=5.):
    """Model a finite stop-align-finish maneuver from a stationary state.

    This deliberately conservative ideal-model baseline turns in place, then
    translates along the resulting bearing. A FIFO delays each request.
    All commands, including the zero-command drain and witness, must fit
    the separate terminal budget before the maneuver starts. No approach
    success or duty metric is changed. Exact fractional synthetic rates
    are not a claim about physical input capabilities.
    """
    dt = _bounded_number(dt, "dt", .01, .2)
    speed = _bounded_number(speed, "speed", .1, 20.)
    yaw_rate = _bounded_number(yaw_rate, "yaw rate", 10., 720.)
    tolerance = _bounded_number(tolerance, "tolerance", .01, 5.)
    budget = _bounded_number(budget, "terminal budget", .01, 30.)
    if type(delay_steps) is not int or not 0 <= delay_steps <= 10:
        raise ValueError("invalid terminal delay")
    if len(xyz) != 3 or len(goal) != 3:
        raise ValueError("expected three-dimensional positions")
    x, y, z = (_bounded_number(v, "position", -1e6, 1e6) for v in xyz)
    gx, gy, gz = (_bounded_number(v, "goal", -1e6, 1e6) for v in goal)
    yaw = _angle_delta(_bounded_number(yaw, "yaw", -1e6, 1e6), 0.)
    if abs(y-gy) > 1e-9:
        raise ValueError("terminal experiment requires a flat synthetic plane")
    initial_error = math.hypot(gx-x, gz-z)
    frames = [{"elapsedSeconds": 0., "xyz": [x,y,z], "yawDegrees": yaw,
               "errorXZ": initial_error, "appliedSpeed": 0., "appliedYawRate": 0.}]

    def receipt(status):
        return {"status": status, "initialErrorXZ": initial_error,
                "finalErrorXZ": frames[-1]["errorXZ"],
                "settled": frames[-1]["errorXZ"] <= tolerance,
                "extraSeconds": frames[-1]["elapsedSeconds"],
                "extraTravelXZ": sum(f["appliedSpeed"]*dt for f in frames[1:]),
                "frames": frames, "physicalQualification": False,
                "gameInputSent": False}

    # Preserve every already-successful passive endpoint exactly.
    if initial_error <= tolerance:
        return receipt("already-settled")

    # The exact ideal plant supports fractional commands; the two-phase
    # reference deliberately avoids assumptions about real key timings.
    bearing = math.degrees(math.atan2(gz-z, gx-x))
    turn = _angle_delta(bearing, yaw)
    turn_steps = math.ceil(abs(turn)/(yaw_rate*dt))
    # Move only far enough to reach a point at half the tolerance radius.
    distance = initial_error - tolerance/2.
    move_steps = math.ceil(distance/(speed*dt))
    intervals = turn_steps + move_steps + delay_steps + 1
    if intervals*dt > budget + 1e-12:
        return receipt("terminal-budget-insufficient")

    requested = []
    if turn_steps:
        requested.extend([(0., turn/(turn_steps*dt))]*turn_steps)
    requested.extend([(distance/(move_steps*dt), 0.)]*move_steps)
    # Once requests finish, drain all delayed commands, then observe
    # one complete stationary interval. Never truncate the final queue.
    requested.extend([(0.,0.)]*(delay_steps+1))
    pending = deque([(0.,0.)]*delay_steps)
    for i, command in enumerate(requested, 1):
        if delay_steps:
            pending.append(command)
            velocity, rate = pending.popleft()
        else:
            velocity, rate = command
        midpoint = math.radians(yaw + rate*dt/2.)
        x += velocity*dt*math.cos(midpoint)
        z += velocity*dt*math.sin(midpoint)
        yaw = _angle_delta(yaw+rate*dt, 0.)
        frames.append({"elapsedSeconds": i*dt, "xyz": [x,y,z],
                       "yawDegrees": yaw, "errorXZ": math.hypot(gx-x,gz-z),
                       "appliedSpeed": velocity, "appliedYawRate": rate})
    assert all(v == 0. and r == 0. for v,r in pending)
    return receipt("model-corrected" if frames[-1]["errorXZ"] <= tolerance
                   else "model-correction-failed")


def evaluate_observed():
    """Exercise the 24 previously observed V4 endpoints, not a new holdout."""
    from .simulation_v4_terminal_observation import evaluate
    source = evaluate()
    rows = []
    for row in source["rows"]:
        spec = row["scenario"]
        for side in ("baseline", "candidate"):
            terminal = row[side]["terminal"]
            if terminal is None:
                rows.append({"scenarioSHA256": row["scenarioSHA256"], "side": side,
                             "passiveSettled": False, "correction": None})
                continue
            last = terminal["observations"][-1]
            correction = finish_after_drain(
                xyz=last["xyz"], yaw=last["yawDegrees"], goal=spec["routeXYZ"][-1],
                dt=spec["dt"], speed=spec["speed"], yaw_rate=spec["maxYawRate"],
                delay_steps=round(row["delaySeconds"]/spec["dt"]))
            rows.append({"scenarioSHA256": row["scenarioSHA256"], "side": side,
                         "passiveSettled": row[side]["settled"], "correction": correction})
    summary = {}
    for side in ("baseline", "candidate"):
        group = [r for r in rows if r["side"] == side]
        summary[side] = {"cases": len(group),
                         "passiveSettled": sum(r["passiveSettled"] for r in group),
                         "afterCorrectionSettled": sum(bool(r["correction"] and r["correction"]["settled"]) for r in group),
                         "maxExtraSeconds": max((r["correction"]["extraSeconds"] for r in group if r["correction"]), default=0.)}
    return {"schema": "taxi.synthetic-terminal-finish/1",
            "classification": "SYNTHETIC_TERMINAL_ONLY",
            "summary": summary, "rows": rows, "physicalQualification": False,
            "gameInputSent": False,
            "limitations": ["Previously observed development cases; not independent validation.",
                            "Ideal fractional commands, stationary start, flat plane, no collision or inertia model.",
                            "Terminal correction does not improve approach metrics or imply live arrival."]}


if __name__ == "__main__":
    print(json.dumps(evaluate_observed(), sort_keys=True, allow_nan=False))
