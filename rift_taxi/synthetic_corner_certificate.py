"""Offline geometric certificate for a noisy synthetic corner observation.

A configured per-axis measurement-error envelope is independent of the
actual sensor profile. This is a sufficient spatial test for a captured
point, not an estimate of current position, traversability, or a live
measurement guarantee. No game, network, input, or process access.
"""
import math

from .contracts import TraceError


# Covers all four current deterministic fixture profiles, including the
# occasional impulse. This is a research assumption, not RIFT calibration.
AXIS_ERROR_BOUND = .08


def worst_case_distance_xz(measured, vertex, axis_bound=AXIS_ERROR_BOUND):
    """Maximum XZ separation over the entire axis-aligned error rectangle.

    For each horizontal coordinate, the farthest endpoint from the vertex
    is abs(measured-vertex)+bound. The farthest rectangle corner gives the
    exact maximum Euclidean distance over that rectangle. Y is irrelevant
    to this strictly planar experiment.
    """
    if (type(axis_bound) not in (float,int) or not 0. <= axis_bound <= 1.):
        raise TraceError("invalid corner measurement envelope")
    if (not isinstance(measured,(list,tuple)) or not isinstance(vertex,(list,tuple))
            or len(measured)!=3 or len(vertex)!=3 or
            any(type(v) not in (float,int) or not -1e7 <= v <= 1e7
                for v in (*measured,*vertex))):
        raise TraceError("invalid synthetic corner geometry")
    return math.hypot(abs(measured[0]-vertex[0])+axis_bound,
                      abs(measured[2]-vertex[2])+axis_bound)


def certified_corner(measured,vertex,radius):
    """True only if every position inside the declared envelope is in radius."""
    if (type(radius) not in (float,int) or not 0.<radius<=1.):
        raise TraceError("invalid synthetic corner radius")
    return worst_case_distance_xz(measured,vertex)<=radius
