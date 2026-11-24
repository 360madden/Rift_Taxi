"""Read-only verification of a saved V3 synthetic benchmark receipt.

Entry point: audit_v3_receipt(path, expected_sha256=None). Bounded JSON
loading rejects ambiguous or nonfinite data; a caller-supplied digest
checks exact source bytes. Recompute aggregate counts independently, then
replay the frozen synthetic evaluator to compare every scenario and outcome.

No report is overwritten, no simulator policy is changed, and no physical
game state or input is involved. Replay proves consistency with this
repository's synthetic model, not authenticity or physical ground truth.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean

from .contracts import TraceError
from .simulation_holdout_v3 import evaluate_holdout_v3
from .simulation_holdout import _case_trace

_MAX_BYTES = 8 * 1024 * 1024
_KEYS = ("routeId","routeXYZ","initialXYZ","initialYawDegrees",
         "lateralOffset","headingOffsetDegrees","speed","maxYawRate","dt")
_OUTCOMES = ("fixed:0","turn-limited:0","turn-limited-rejoin:0",
             "turn-limited-ordered:0","turn-limited-ordered:1","turn-limited-ordered:3")


def _unique_pairs(pairs):
    """Reject duplicate members at every JSON object level."""
    obj = {}
    for key,value in pairs:
        if key in obj:
            raise TraceError(f"duplicate receipt key: {key}")
        obj[key] = value
    return obj


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise TraceError("nonfinite receipt number")
    return number


def _reject_constant(value):
    raise TraceError(f"invalid receipt JSON constant: {value}")


def _canonical(value):
    """Type-sensitive comparison; JSON true, 1, and 1.0 remain distinct."""
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)


def _load_receipt(path,expected_sha256):
    """Read once, hash those same bytes, and decode only bounded strict JSON.

    The expected digest must come from a separately retained source to
    support an exact-byte provenance check. Without it, the digest is only
    an identifier for the bytes inspected in this call.
    """
    if expected_sha256 is not None and (
            not isinstance(expected_sha256,str)
            or re.fullmatch("[0-9a-fA-F]{64}",expected_sha256) is None):
        raise TraceError("expected SHA-256 must contain exactly 64 hex digits")
    try:
        with Path(path).open("rb") as source:
            raw = source.read(_MAX_BYTES+1)
        if len(raw)>_MAX_BYTES:
            raise TraceError("receipt exceeds 8 MiB limit")
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 is not None and digest!=expected_sha256.lower():
            raise TraceError("receipt SHA-256 mismatch")
        receipt = json.loads(raw.decode("utf-8"),object_pairs_hook=_unique_pairs,
                             parse_float=_finite_float,parse_constant=_reject_constant)
    except (OSError,UnicodeError,ValueError,RecursionError) as exc:
        if isinstance(exc,TraceError):
            raise
        raise TraceError("cannot read strict synthetic receipt JSON") from exc
    if not isinstance(receipt,dict):
        raise TraceError("receipt must be a JSON object")
    return receipt,digest,len(raw)


def _summary(group,key):
    """Independently recount outcomes, using only successful arrival times."""
    outcomes = [row["outcomes"][key] for row in group]
    arrivals = [o for o in outcomes if o["metrics"]["syntheticArrival"]]
    for o in outcomes:
        arrival = o["metrics"]["syntheticArrival"]
        if type(arrival) is not bool or arrival is not (o["status"]=="synthetic-arrived"):
            raise TraceError("receipt arrival/status mismatch")
        if o["arrivalAndDutyTarget"] is not (arrival and o["metrics"]["forwardDutyRatio"]>=.95):
            raise TraceError("receipt duty target mismatch")
    result = {"cases":len(outcomes),"geometricArrivals":len(arrivals),
              "arrivalAndDutyTarget":sum(o["arrivalAndDutyTarget"] for o in outcomes),
              "statusCounts":dict(sorted(Counter(o["status"] for o in outcomes).items())),
              "meanArrivalSeconds":mean(o["metrics"]["elapsedSeconds"] for o in arrivals)
                                   if arrivals else None}
    if key.startswith("turn-limited-ordered:"):
        drains = [o["terminalDrain"] for o in outcomes]
        for o,d in zip(outcomes,drains,strict=True):
            if type(d["settledWithinTolerance"]) is not bool:
                raise TraceError("invalid receipt settling flag")
            if not o["metrics"]["syntheticArrival"] and d["settledWithinTolerance"]:
                raise TraceError("receipt promotes failed approach to settling")
        result["settledWithinTolerance"] = sum(d["settledWithinTolerance"] for d in drains)
        result["sampledToleranceExits"] = sum(d.get("leftToleranceAtSample",False) for d in drains)
    return result


def _check_coverage_and_aggregates(receipt):
    """Verify row identities, complete matched coverage, and group summaries.

    Self-consistent hashes alone are insufficient: the subsequent frozen
    replay checks that each scenario actually belongs to this benchmark.
    """
    if (receipt["schema"]!="taxi.synthetic-holdout-v3/1"
            or receipt["classification"]!="SYNTHETIC_CLOSED_LOOP_ONLY"
            or receipt["scenarioSet"]!="route-shape-holdout-v3"
            or any(receipt[k] is not False for k in
                   ("gameInputSent","liveArrivalVerified","liveNavigabilityVerified"))):
        raise TraceError("receipt schema or synthetic classification mismatch")
    rows = receipt["cases"]
    if (not isinstance(rows,list) or len(rows)!=72
            or type(receipt["scenarioCount"]) is not int or receipt["scenarioCount"]!=72
            or type(receipt["simulationCount"]) is not int or receipt["simulationCount"]!=432):
        raise TraceError("receipt case or execution coverage mismatch")
    seen = set()
    for i,row in enumerate(rows,1):
        if type(row["case"]) is not int or row["case"]!=i:
            raise TraceError("receipt case ordering mismatch")
        trace = _case_trace({k:row[k] for k in _KEYS},generator="taxi-holdout-v3")
        if trace.trace_sha256!=row["scenarioSHA256"] or trace.trace_sha256 in seen:
            raise TraceError("receipt scenario hash mismatch or duplicate")
        seen.add(trace.trace_sha256)
        if set(row["outcomes"])!=set(_OUTCOMES):
            raise TraceError("receipt policy/delay coverage mismatch")
        for key,o in row["outcomes"].items():
            policy,delay = key.split(":")
            if (o["speedPolicy"]!=policy or type(o["delaySteps"]) is not int
                    or o["delaySteps"]!=int(delay)
                    or o["nominalDelaySeconds"]!=int(delay)*row["dt"]):
                raise TraceError("receipt policy/delay identity mismatch")
    if _canonical(receipt["summary"])!=_canonical({k:_summary(rows,k) for k in _OUTCOMES}):
        raise TraceError("receipt overall aggregate mismatch")
    # Derive groups from cases rather than trusting supplied group labels
    # or counts. Retain first occurrence order used by the original schema.
    names = list(dict.fromkeys(r["routeId"] for r in rows))
    groups = [{"routeId":name,"summary":{k:_summary([r for r in rows if r["routeId"]==name],k)
                                        for k in _OUTCOMES}} for name in names]
    if _canonical(receipt["byRoute"])!=_canonical(groups):
        raise TraceError("receipt route aggregate mismatch")


def audit_v3_receipt(path,*,expected_sha256=None):
    """Return a new audit receipt only if all checks and replay succeed.

    This is intentionally strict about the frozen report schema. Full
    replay prevents a coordinated edit to scenario rows and aggregate
    summaries from being accepted just because they agree internally.
    JSON formatting/order may vary; supplying a digest additionally pins
    exact source bytes. No claims of a cryptographic signature are made.
    """
    receipt,digest,size = _load_receipt(path,expected_sha256)
    try:
        _check_coverage_and_aggregates(receipt)
        replay = evaluate_holdout_v3()
        if _canonical(receipt)!=_canonical(replay):
            raise TraceError("receipt differs from frozen synthetic replay")
    except (KeyError,TypeError,IndexError,AttributeError,ValueError,OverflowError,RecursionError) as exc:
        if isinstance(exc,TraceError):
            raise
        raise TraceError("malformed V3 synthetic receipt") from exc
    return {"schema":"taxi.synthetic-v3-receipt-audit/1",
            "classification":"SYNTHETIC_CLOSED_LOOP_ONLY",
            "sourceSHA256":digest,"sourceBytes":size,
            "expectedSHA256Matched":True if expected_sha256 is not None else None,
            "scenarioCount":72,"simulationCount":432,
            "scenarioHashesVerified":True,"aggregateCountsVerified":True,
            "frozenReplayMatched":True,"gameInputSent":False,"liveArrivalVerified":False,
            "limitations":["Replay checks internal synthetic reproducibility, not physical truth or source authenticity.",
                           "Exact byte provenance requires a separately trusted expected digest.",
                           "No game access or controller change."]}
