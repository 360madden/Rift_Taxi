"""Prespecified V4 synthetic holdout design, frozen before outcome inspection.

Only scenario construction is exposed here. Do not evaluate or tune a new
candidate on this set until its implementation and comparison rules are
frozen. These authored geometries are not physical maps or random samples.
"""
from itertools import product
import math

from .simulation_holdout import _case_trace

GENERATOR = "taxi-holdout-v4-prespecified"
# Distinct invented geometry: repeated acute turns, alternating long/short
# legs, a concave loop with exit, an oblique close-return, offset crossing,
# and a final approach turning back toward the incoming leg.
ROUTES = (
    ("acute-alternation", ((0., 0.), (4., 0.), (1., 1.8), (5., 3.), (2., 5.), (7., 6.))),
    ("long-short-ladder", ((0., 0.), (7., 1.), (7.2, 2.), (1., 3.), (1.2, 4.2), (8., 5.))),
    ("concave-loop-exit", ((0., 0.), (5., 0.), (5., 5.), (2., 3.), (1., 5.), (-1., 2.), (-3., 4.))),
    ("oblique-close-return", ((-4., -3.), (2., 1.), (1., 2.), (-3., -.3), (-5., 3.))),
    ("offset-crossing", ((1., -2.), (7., 5.), (-1., 4.), (6., -1.), (8., 2.))),
    ("reverse-terminal", ((0., 0.), (6., 2.), (8., 5.), (4., 6.), (4.8, 5.2))),
)
OFFSETS = (-.45, .85)
HEADINGS = (-55., 70., 155.)
# Two profiles not taken from the V3 factorial grid. Each profile admits
# the same three nominal delays exactly as bounded whole FIFO steps.
PROFILES = ((2.8, 85., .06), (3.1, 115., .12))
DELAYS_SECONDS = (0., .12, .36)


def scenarios():
    """Return 72 canonical specs, each with three prespecified delay levels.

    Use the existing synthetic trace factory to obtain the source identity
    rather than inventing a second trace schema or physical coordinates.
    The scenario digest deliberately excludes the tested delay, so matched
    delay runs share one geometry/profile identity as in the V3 study.
    """
    rows = []
    for (name, points), offset, heading, (speed, rate, dt) in product(
            ROUTES, OFFSETS, HEADINGS, PROFILES):
        dx = points[1][0] - points[0][0]
        dz = points[1][1] - points[0][1]
        length = math.hypot(dx, dz)
        spec = {"routeId": name,
                "routeXYZ": [[x, 0., z] for x, z in points],
                "initialXYZ": [points[0][0] - offset * dz / length, 0.,
                               points[0][1] + offset * dx / length],
                "initialYawDegrees": math.degrees(math.atan2(dz, dx)) + heading,
                "lateralOffset": offset, "headingOffsetDegrees": heading,
                "speed": speed, "maxYawRate": rate, "dt": dt}
        trace = _case_trace(spec, generator=GENERATOR)
        delay_steps = tuple(round(delay / dt) for delay in DELAYS_SECONDS)
        if any(not 0 <= n <= 10 or not math.isclose(n * dt, delay, rel_tol=0., abs_tol=1e-12)
               for n, delay in zip(delay_steps, DELAYS_SECONDS)):
            raise ValueError("prespecified delay not representable")
        rows.append({"scenario": spec, "scenarioSHA256": trace.trace_sha256,
                     "delaySteps": delay_steps})
    return rows
