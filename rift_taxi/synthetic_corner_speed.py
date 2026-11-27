"""Fixed tapered speed-cap experiment for certified synthetic sharp corners.

The corner certificate remains unchanged. This module only determines a
requested forward-speed cap from the forecast chord in synthetic units.
It is not an actuator, stopping-distance guarantee, or RIFT calibration.
"""
import math
from .contracts import TraceError

BASE_GAIN = 4.  # inverse synthetic seconds; original bounded approach
EXTRA_GAIN = 4.
KNEE_XZ = .25  # retain the original cap throughout the final approach


def tapered_corner_cap(chord):
    """Continuous monotonic cap: 4d inside knee, 4d+4(d-knee) outside.

    The controller still applies heading, curvature, nominal speed, and
    one-tick overshoot limits. A forecast chord cannot certify passage.
    """
    if (type(chord) not in (float,int) or not 0. <= chord <= 1e7
            or not math.isfinite(chord)):
        raise TraceError("invalid synthetic corner chord")
    return BASE_GAIN*chord + EXTRA_GAIN*max(0.,chord-KNEE_XZ)
