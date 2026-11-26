"""Deterministic bounded measurement perturbations for offline research.

Noise affects captured observations only, not the plant, timestamps,
transport order or command queue. The function is a reproducible fixture,
not a statistical sensor model or measured RIFT noise distribution.
"""
from .contracts import TraceError
from .steering import _angle_delta

PROFILES = ("none","mild","moderate","impulse")
BOUNDS = {"none":(0.,0.),"mild":(.005,.25),
          "moderate":(.015,.75),"impulse":(.005,.25)}


def _unit(tick,channel):
    """Stable integer mixing, independent of Python hash/random process state."""
    x=((tick+1)*0x9e3779b1+(channel+1)*0x85ebca77)&0xffffffff
    x=((x^(x>>16))*0x7feb352d)&0xffffffff
    x=((x^(x>>15))*0x846ca68b)&0xffffffff
    x=x^(x>>16)
    return 2.*(x/0xffffffff)-1.


def measurement(tick,xyz,yaw,profile):
    """Return a synthetic captured pose without changing the source epoch."""
    if profile not in PROFILES or type(tick) is not int or not 0<=tick<=650:
        raise TraceError("invalid synthetic sensor profile or epoch")
    if profile=="none":
        return tuple(xyz),yaw
    pos,angle=BOUNDS[profile]
    if profile=="impulse" and tick%29==13:
        pos,angle=.08,3.
    return (xyz[0]+pos*_unit(tick,0),xyz[1],xyz[2]+pos*_unit(tick,1)), _angle_delta(yaw+angle*_unit(tick,2),0.)
