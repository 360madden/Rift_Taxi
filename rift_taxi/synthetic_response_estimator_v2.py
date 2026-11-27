"""Experimental robust response estimator for the offline sampled plant.

Use signed, midpoint-heading displacement rather than unsigned distance;
aggregate consecutive increments to reduce differenced observation noise.
A qualified model is monitored on disjoint four-tick innovation blocks.
Two inconsistent blocks invalidate it and start a new bounded fit window.
No game access, input, physical telemetry qualification, or production use.
"""
from collections import deque
import math
from statistics import median

from .contracts import TraceError
from .steering import _angle_delta
from .synthetic_response_estimator import (
    DELAYS, DT, MAX_HISTORY, NOMINAL, ZERO, Fit, _finite_number,
)

WINDOW = 32
BLOCK = 4
MIN_PAIRS = 12
FIT_EVERY = 2
HOLD_TICKS = 64
# Fixed research thresholds, authored before observing study results.
SPEED_SCALE = .12
YAW_SCALE = 4.
MAX_SCORE = 3.
MIN_SEPARATION = .08
CHANGE_SPEED = .35
CHANGE_YAW = 10.
CHANGE_BLOCKS = 2


def _request(requests, tick, delay):
    index = tick-delay
    if index < 0:
        return ZERO
    if index >= len(requests):
        raise TraceError("robust response attempted future command")
    c = requests[index]
    if (not isinstance(c,(tuple,list)) or len(c)!=2
            or not _finite_number(c[0],0.,20.)
            or not _finite_number(c[1],-720.,720.)):
        raise TraceError("invalid command in robust response")
    return c


def _blocks(pairs):
    """Overlapping BLOCK-interval windows, but never span a capture gap."""
    values = list(pairs)
    for i in range(len(values)-BLOCK+1):
        b = values[i:i+BLOCK]
        if b[-1][0]-b[0][0]==BLOCK-1:
            yield b


def _huber(value):
    a = abs(value)
    return .5*a*a if a<=1.5 else 1.5*(a-.75)


def _channel(x,y,scale,excitation):
    """Bounded robust scalar fit using a median seed and three IRLS passes.

    The loss is expressed in fixed channel-specific units. Excitation
    rejects a channel that cannot measure its gain. Delay confidence still
    requires a competing candidate and a distinct residual minimum.
    """
    ratios = [b/a for a,b in zip(x,y) if abs(a)>=excitation]
    if len(ratios)<4:
        return None
    gain = min(1.5,max(.5,median(ratios)))
    for _ in range(3):
        residuals = [abs((b-gain*a)/scale) for a,b in zip(x,y)]
        weights = [min(1.,1.5/r) if r else 1. for r in residuals]
        xx = sum(w*a*a for a,w in zip(x,weights))
        if xx<=1e-12:
            return None
        gain = min(1.5,max(.5,sum(w*a*b for a,b,w in zip(x,y,weights))/xx))
    return gain,sum(_huber((b-gain*a)/scale) for a,b in zip(x,y))/len(x)


def fit_robust(pairs,requests):
    """Find a uniquely supported constant response in the current window."""
    if len(pairs)>WINDOW or len(requests)>MAX_HISTORY:
        raise TraceError("robust response window/history out of bounds")
    previous=-1
    for tick,v,r in pairs:
        if (type(tick) is not int or not previous<tick<len(requests)
                or not _finite_number(v,-40.,40.) or not _finite_number(r,-1200.,1200.)):
            raise TraceError("invalid robust response pair")
        previous=tick
    if len(pairs)<MIN_PAIRS:
        return None
    blocks=list(_blocks(pairs))
    if len(blocks)<6:
        return None
    yv=[sum(p[1] for p in b)/BLOCK for b in blocks]
    yr=[sum(p[2] for p in b)/BLOCK for b in blocks]
    candidates=[]
    for delay in DELAYS:
        averages=[]
        for b in blocks:
            commands=[_request(requests,p[0],delay) for p in b]
            averages.append(tuple(sum(c[k] for c in commands)/BLOCK for k in (0,1)))
        v=_channel([a[0] for a in averages],yv,SPEED_SCALE,.05)
        r=_channel([a[1] for a in averages],yr,YAW_SCALE,1.)
        if v is not None and r is not None:
            candidates.append(((v[1]+r[1])/2.,delay,v[0],r[0]))
    candidates.sort()
    if len(candidates)<2:
        return None
    score,delay,vg,yg=candidates[0]
    separation=candidates[1][0]-score
    if score>MAX_SCORE or separation<MIN_SEPARATION:
        return None
    return Fit(delay,vg,yg,score,separation,len(pairs))


class RobustResponseEstimator:
    """Causal robust estimator; invalidated fits cannot remain qualified.

    Confidence is a model-fit classification, not measured RIFT freshness.
    Only admitted observations and issued history are accepted. Innovation
    blocks are disjoint and a capture gap resets the change streak.
    """
    def __init__(self):
        self.pairs=deque(maxlen=WINDOW)
        self.innovations=[]
        self.previous=None
        self.last_delivery=None
        self.last_fit=None
        self.last_fit_tick=None
        self.accepted_pairs=0
        self.fit_attempts=0
        self.qualified_updates=0
        self.change_resets=0
        self.bad_blocks=0
        self._suspect=[]

    def observe(self,capture,xyz,yaw,delivered,requests):
        if (type(capture) is not int or type(delivered) is not int
                or not 0<=capture<=delivered<=MAX_HISTORY or len(requests)!=delivered
                or (self.last_delivery is not None and delivered<self.last_delivery)
                or not isinstance(xyz,(tuple,list)) or len(xyz)!=3
                or any(not _finite_number(v,-1e6,1e6) for v in xyz)
                or not _finite_number(yaw,-180.,180.)):
            raise TraceError("invalid robust causal observation")
        prior=self.previous
        if prior is not None and capture<=prior[0]:
            raise TraceError("robust response sequence rollback")
        self.previous=(capture,tuple(xyz),yaw)
        self.last_delivery=delivered
        if prior is None or capture!=prior[0]+1:
            self.innovations.clear()
            self.bad_blocks=0
            self._suspect.clear()
            return
        tick,old,old_yaw=prior
        if old[1]!=xyz[1]:
            raise TraceError("robust response requires flat synthetic motion")
        delta=_angle_delta(yaw,old_yaw)
        mid=math.radians(old_yaw+delta/2.)
        # Signed projection avoids the positive-speed bias of noisy stationary
        # Euclidean distances. The yaw error is a wrapped one-tick increment.
        v=((xyz[0]-old[0])*math.cos(mid)+(xyz[2]-old[2])*math.sin(mid))/DT
        r=delta/DT
        if not _finite_number(v,-40.,40.) or not _finite_number(r,-1200.,1200.):
            raise TraceError("robust response increment out of bounds")
        pair=(tick,v,r)
        self.pairs.append(pair)
        self.accepted_pairs+=1
        if self.last_fit is not None and capture-self.last_fit_tick>HOLD_TICKS:
            self.last_fit=None
            self.last_fit_tick=None
            self.innovations.clear()
            self.bad_blocks=0
            self._suspect.clear()
        if self.last_fit is not None:
            f=self.last_fit
            cv,cr=_request(requests,tick,f.delay)
            self.innovations.append((pair,v-cv*f.speed_gain,r-cr*f.yaw_gain))
            if len(self.innovations)==BLOCK:
                block=self.innovations
                self.innovations=[]
                ev=abs(sum(p[1] for p in block)/BLOCK)
                er=abs(sum(p[2] for p in block)/BLOCK)
                if ev>CHANGE_SPEED or er>CHANGE_YAW:
                    self.bad_blocks+=1
                    self._suspect.extend(p[0] for p in block)
                else:
                    self.bad_blocks=0
                    self._suspect.clear()
                if self.bad_blocks>=CHANGE_BLOCKS:
                    # Keep only recent inconsistent evidence, not the old
                    # response regime. Do not renew confidence on that same
                    # decision; fitting resumes after more new observations.
                    self.pairs=deque(self._suspect,maxlen=WINDOW)
                    self.last_fit=None
                    self.last_fit_tick=None
                    self.bad_blocks=0
                    self._suspect.clear()
                    self.change_resets+=1
                    return
        # Freeze the currently monitored model during an inconsistent block
        # streak; otherwise refitting could conceal a real change.
        if (self.bad_blocks==0 and len(self.pairs)>=MIN_PAIRS
                and self.accepted_pairs%FIT_EVERY==0):
            self.fit_attempts+=1
            fit=fit_robust(self.pairs,requests)
            if fit is not None:
                self.last_fit=fit
                self.last_fit_tick=capture
                self.qualified_updates+=1

    def estimate(self,tick):
        if (type(tick) is not int or tick<0
                or (self.last_delivery is not None and tick<self.last_delivery)):
            raise TraceError("invalid robust estimator decision epoch")
        if self.last_fit is not None and tick-self.last_fit_tick<=HOLD_TICKS:
            f=self.last_fit
            return {"delay":f.delay,"speedGain":f.speed_gain,"yawGain":f.yaw_gain,
                    "qualified":True,"fitCaptureTick":self.last_fit_tick,
                    "score":f.score,"separation":f.separation,"pairs":f.pairs,
                    "changeResets":self.change_resets}
        return {"delay":NOMINAL[0],"speedGain":NOMINAL[1],"yawGain":NOMINAL[2],
                "qualified":False,"fitCaptureTick":None,"score":None,
                "separation":None,"pairs":0,"changeResets":self.change_resets}
