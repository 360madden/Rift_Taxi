"""Bounded online estimator for an ideal *synthetic* sampled actuator.

Fit whole-step command latency and independent velocity/yaw gains using
only admitted, consecutive capture poses and already issued commands.
No game, OS input, physical calibration, or access to future observations.
This estimator is deliberately conservative under unexcited motion:
constant commands cannot identify delay, and missing turn evidence cannot
identify yaw response. A qualified fit ages out to a fixed nominal model.
"""
from collections import deque
from dataclasses import dataclass
import math

from .contracts import TraceError
from .steering import _angle_delta

DT = .0625
WINDOW = 48
MIN_PAIRS = 8
MIN_ACTIVE = 4
FIT_EVERY = 4
HOLD_TICKS = 96
MAX_HISTORY = 640
DELAYS = tuple(range(11))
NOMINAL = (3, 1., 1.)
ZERO = (0., 0.)


@dataclass(frozen=True)
class Fit:
    delay: int
    speed_gain: float
    yaw_gain: float
    score: float
    separation: float
    pairs: int


def _fit_channel(x, y, threshold):
    """Fit scalar least squares, with explicit excitation and gain bounds.

    x/y are corresponding requested and observed velocities or yaw rates.
    Use a normalized residual based on observed energy, so neither unit
    convention nor an unusually high yaw rate dominates the delay score.
    """
    if sum(abs(v) >= threshold for v in x) < MIN_ACTIVE:
        return None
    xx = sum(v*v for v in x)
    yy = sum(v*v for v in y)
    if xx <= 1e-12 or yy <= 1e-12:
        return None
    gain = min(1.5, max(.5, sum(a*b for a,b in zip(x,y))/xx))
    residual = sum((b-gain*a)**2 for a,b in zip(x,y))/yy
    return gain,residual


def _finite_number(value, low, high):
    return type(value) in (int,float) and math.isfinite(value) and low <= value <= high


def fit_response(pairs, requests):
    """Return an identifiable fit or None, using bounded one-step increments.

    Each pair is (plant interval index, observed forward speed, observed yaw
    rate). Multi-step gaps are intentionally excluded: chord length is not
    path length, and wrapped angle differences could be ambiguous. A
    candidate delay is ranked by both normalized residuals. Refuse close
    alternatives instead of picking a delay arbitrarily.
    """
    if len(pairs) > WINDOW or len(requests) > MAX_HISTORY:
        raise TraceError("response fit exceeds bounded window/history")
    previous_tick = -1
    for tick, velocity, rate in pairs:
        if (type(tick) is not int or not previous_tick < tick < len(requests)
                or not _finite_number(velocity,0.,30.+1e-8)
                or not _finite_number(rate,-1080.-1e-8,1080.+1e-8)):
            raise TraceError("invalid response fit pair")
        previous_tick = tick
    if len(pairs) < MIN_PAIRS:
        return None
    candidates = []
    for delay in DELAYS:
        predicted = []
        for tick, _, _ in pairs:
            index = tick-delay
            if index >= len(requests):
                raise TraceError("response fit attempted future request")
            command = requests[index] if index >= 0 else ZERO
            if (not isinstance(command,(tuple,list)) or len(command) != 2
                    or not _finite_number(command[0],0.,20.)
                    or not _finite_number(command[1],-720.,720.)):
                raise TraceError("invalid issued command in response fit")
            predicted.append(command)
        v = _fit_channel([c[0] for c in predicted],[p[1] for p in pairs],.05)
        r = _fit_channel([c[1] for c in predicted],[p[2] for p in pairs],1.)
        if v is not None and r is not None:
            candidates.append(((v[1]+r[1])/2.,delay,v[0],r[0]))
    candidates.sort()
    # A single surviving candidate is not evidence of delay separation;
    # require an actual competing fit and a meaningful residual margin.
    if len(candidates) < 2:
        return None
    score, delay, vg, yg = candidates[0]
    gap = candidates[1][0]-score
    if score > .02 or gap < .001:
        return None
    return Fit(delay,vg,yg,score,gap,len(pairs))


class ResponseEstimator:
    """Stateful, causal fitting with a finite window and expiry.

    The caller must supply only admitted observations in increasing capture
    order and requests through (but not including) the current delivery
    tick. Initial zero command history is part of the model. No estimator
    output can qualify pose freshness, route progress, arrival, or rearm.
    """
    def __init__(self):
        self.pairs = deque(maxlen=WINDOW)
        self.previous = None
        self.last_delivery = None
        self.last_fit = None
        self.last_fit_tick = None
        self.accepted_pairs = 0
        self.fit_attempts = 0
        self.qualified_updates = 0

    def observe(self, capture, xyz, yaw, delivered, requests):
        if (type(capture) is not int or type(delivered) is not int
                or not 0 <= capture <= delivered <= MAX_HISTORY or len(requests) != delivered
                or (self.last_delivery is not None and delivered < self.last_delivery)
                or not isinstance(xyz,(tuple,list)) or len(xyz) != 3
                or any(not _finite_number(v,-1e6,1e6) for v in xyz)
                or not _finite_number(yaw,-180.,180.)):
            raise TraceError("invalid causal response observation")
        prior = self.previous
        if prior is not None and capture <= prior[0]:
            raise TraceError("response observation sequence rollback")
        self.previous = (capture,tuple(xyz),yaw)
        self.last_delivery = delivered
        if prior is None or capture != prior[0]+1:
            return
        tick, old, old_yaw = prior
        if old[1] != xyz[1]:
            raise TraceError("response estimator requires flat synthetic motion")
        velocity = math.hypot(xyz[0]-old[0],xyz[2]-old[2])/DT
        rate = _angle_delta(yaw,old_yaw)/DT
        # DT and maximum ideal rate bound keep one-tick yaw unambiguous.
        self.pairs.append((tick,velocity,rate))
        self.accepted_pairs += 1
        if self.accepted_pairs >= MIN_PAIRS and self.accepted_pairs % FIT_EVERY == 0:
            self.fit_attempts += 1
            fit = fit_response(self.pairs,requests)
            if fit is not None:
                self.last_fit = fit
                self.last_fit_tick = capture
                self.qualified_updates += 1

    def estimate(self, tick):
        """Return a finite-lived fit or the fixed nominal fallback."""
        if (type(tick) is not int or tick < 0
                or (self.last_delivery is not None and tick < self.last_delivery)):
            raise TraceError("invalid response estimator decision epoch")
        if self.last_fit is not None and tick-self.last_fit_tick <= HOLD_TICKS:
            f = self.last_fit
            return {"delay": f.delay,"speedGain": f.speed_gain,"yawGain": f.yaw_gain,
                    "qualified": True,"fitCaptureTick": self.last_fit_tick,
                    "score": f.score,"separation": f.separation,"pairs": f.pairs}
        return {"delay": NOMINAL[0],"speedGain": NOMINAL[1],"yawGain": NOMINAL[2],
                "qualified": False,"fitCaptureTick": None,
                "score": None,"separation": None,"pairs": 0}
