"""Offline integrity audit for taxi.native-candidate-series/1 receipts.

Inputs are an explicitly SHA-pinned original and an externally supplied exact
host/process/start/path/build/window/owner pin. Recompute sample/bracket
cadence, change metrics, optional candidate evidence, and sampled key-state
summary. Never open a game process, load a sibling project, send input, or
authorize live movement. A stored receipt cannot establish current freshness,
producer independence, physical movement or game-consumed key release.
"""
from __future__ import annotations

import argparse
import json
import math
import ntpath
from pathlib import Path
import re
import statistics
import struct

from .zone_correlation import _pinned_json
from .native_candidate import _matrix_descriptor
from .native_series import summarize_key_snapshots


class SeriesAuditRefused(ValueError):
    """Stored original is malformed, inconsistent, or outside its expected pin."""


def require(ok, message):
    if not ok:
        raise SeriesAuditRefused(message)


def integer(value, low, high, label):
    require(type(value) is int and low <= value <= high,label)
    return value


def number(value, label, low=-1e15, high=1e15):
    # Range check before conversion also handles arbitrary-size JSON integers.
    require(type(value) in (int,float) and low <= value <= high,label)
    return float(value)


def vector(value,label):
    require(isinstance(value,list) and len(value)==3,label)
    return tuple(number(x,label) for x in value)


def owner(value, *, allow_zero=False):
    require(isinstance(value,str) and re.fullmatch(r"0|[1-9][0-9]{0,19}",value) is not None,
            "invalid decimal owner/handle")
    integer(int(value),0 if allow_zero else 1,2**64-1,"owner/handle outside uint64")
    return value


def same_number(actual,expected,label):
    require(math.isclose(number(actual,label),expected,rel_tol=0.,abs_tol=1e-9),label)


def exact(actual,expected,label):
    """Compare nested JSON with exact scalar types (True must not equal 1)."""
    require(json.dumps(actual,sort_keys=True,allow_nan=False)==
            json.dumps(expected,sort_keys=True,allow_nan=False),label)


def false_fields(obj,*names):
    require(isinstance(obj,dict) and all(obj.get(n) is False for n in names),
            "candidate-only qualification flags missing or promoted")


def matrix_angle(bits):
    """Re-decode stored 32-bit words using the existing pure shape predicate."""
    require(isinstance(bits,list) and len(bits)==9,"matrix word count")
    for b in bits:
        integer(b,0,2**32-1,"invalid matrix word")
    return _matrix_descriptor(struct.pack("<9I",*bits))[1]


def _gap_summary(values):
    gaps=[b-a for a,b in zip(values,values[1:])]
    return {"minimum":min(gaps),"median":statistics.median(gaps),"maximum":max(gaps)}


def _verify_gaps(actual,expected):
    require(isinstance(actual,dict) and set(actual)==set(expected),"gap summary shape")
    for k,v in expected.items():
        same_number(actual[k],v,"gap summary mismatch: "+k)


def audit_document(doc, *, host,pid,start_ticks,exe_path,exe_sha256,hwnd,owner_key):
    """Check a parsed receipt against a separate explicit expected identity.

    The source and its digest are historical assertions, not authentication
    of an actual process or source epoch. The public CLI also pins exact bytes.
    """
    require(isinstance(doc,dict) and doc.get("schema")=="taxi.native-candidate-series/1"
            and doc.get("status")=="candidate-only","native series schema/status")
    source=doc["source"]
    require(isinstance(source,dict),"source identity object")
    for name,expected,limit in (("pid",pid,2**32-1),("startUtcTicks",start_ticks,2**63-1),
                                ("windowHandle",hwnd,2**64-1)):
        integer(expected,1,limit,"invalid expected "+name)
        require(integer(source.get(name),1,limit,"invalid source "+name)==expected,
                "source pin mismatch: "+name)
    require(isinstance(host,str) and bool(host.strip()) and host==host.strip()
            and isinstance(source.get("host"),str)
            and source["host"].casefold()==host.casefold(),"source host mismatch")
    path=source.get("executablePath")
    require(isinstance(path,str) and isinstance(exe_path,str) and ntpath.isabs(path)
            and ntpath.isabs(exe_path)
            and ntpath.normcase(ntpath.normpath(path))==ntpath.normcase(ntpath.normpath(exe_path)),
            "source executable path mismatch")
    require(isinstance(exe_sha256,str) and re.fullmatch(r"[a-fA-F0-9]{64}",exe_sha256)
            and isinstance(source.get("onDiskExecutableSha256"),str)
            and source["onDiskExecutableSha256"].lower()==exe_sha256.lower(),
            "source executable SHA-256 mismatch")
    require(owner(source["ownerKeyDecimalCandidate"])==owner(owner_key),"source owner mismatch")

    count=integer(doc["requestedSamples"],3,128,"requested sample count")
    require(integer(doc["completedSamples"],3,128,"completed sample count")==count,
            "incomplete series")
    spacing=integer(doc["requestedStartSpacingMs"],25,2000,"requested spacing")/1000.
    budget=number(doc["maxTotalSeconds"],"time budget",2.,60.)
    elapsed=number(doc["elapsedSecondsIncludingAdmissions"],"reported elapsed",0.,budget)
    require(doc.get("sampleSchedule")=="actual-start-relative-no-catch-up","sample schedule")
    opts=doc["optionalEvidenceRequested"]
    fields={"actorMatrix":"matrixEvidence","refreshGuard":"refreshGuardEvidence",
            "actorTranslation":"actorTranslationEvidence","zoneKey":"zoneKeyEvidence",
            "manualWindowsKeys":"manualWindowsKeyStates"}
    require(isinstance(opts,dict) and set(opts)==set(fields)
            and all(type(v) is bool for v in opts.values()),"optional evidence flags")
    keys=opts["manualWindowsKeys"]
    require(doc["manualWindowsKeyObservationRequested"] is keys,"key observation declaration")
    quals=doc["qualifications"]
    exact(quals,{"fullExecutableIdentityChecks":2,"singleReadOnlyProcessHandle":True,
        "perSampleProcessWindowChecks":True,"addonApiProducerQuietVerified":False,
        "externalActionReceiptsProvided":False,"readOnlyWindowsKeyPollingUsed":keys,
        "windowsKeyPollsAreNotGameInputProof":True,"physicalMovementVerified":False,
        "gameInputSent":False,"playerBodyHeadingVerified":False,
        "nativeXYZPassiveFreshnessVerified":False,"publicZoneIdVerified":False,
        "worldInstanceVerified":False,"liveJourneyVerified":False},"source qualifications")

    rows=doc["observations"]
    require(isinstance(rows,list) and len(rows)==count,"observation count")
    starts=[]; times=[]; ends=[]; positions=[]; headings=[]
    zones=set(); guards=set(); actor_angles=[]; matches=0
    key_polls=0
    for i,r in enumerate(rows,1):
        require(isinstance(r,dict),"observation object")
        require(integer(r["index"],1,count,"sample index")==i
                and owner(r["ownerKeyDecimal"])==owner_key,"sample index/owner mismatch")
        false_fields(r,"actorHeadingVerified","positionFreshnessVerified")
        for opt,field in fields.items():
            require((field in r)==opts[opt],"optional observation mismatch: "+field)
        start=number(r["captureStartMonotonicSeconds"],"capture start",0.)
        observed=number(r["observedMonotonicSeconds"],"capture timestamp",0.)
        end=number(r["captureEndMonotonicSeconds"],"capture end",0.)
        require(start<=observed<=end,"capture timestamp outside bracket")
        if starts:
            require(start>=ends[-1] and observed>times[-1]
                    and start+1e-9>=starts[-1]+spacing,"sample order/cadence violation")
        same_number(r["captureBracketSeconds"],end-start,"capture bracket duration")
        starts.append(start); times.append(observed); ends.append(end)
        positions.append(vector(r["xyzCandidate"],"XYZ candidate"))
        headings.append(number(r["playerSystemBearingDegreesCandidate"],"bearing",-180.,180.))
        if opts["actorMatrix"]:
            m=r["matrixEvidence"]
            false_fields(m,"actorHeadingVerified")
            a=matrix_angle(m["actorRawBits"])
            b=matrix_angle(m["positionSecondaryRawBits"])
            require(m["rawBitsMatch"] is (m["actorRawBits"]==m["positionSecondaryRawBits"]),
                    "matrix raw-bit agreement mismatch")
            for field,angle in (("actorPlanarAngleDegreesCandidate",a),
                                ("positionPlanarAngleDegreesCandidate",b)):
                if angle is None:
                    require(m[field] is None,"unqualified matrix has angle")
                else:
                    same_number(m[field],angle,"matrix angle mismatch")
            matches+=int(m["rawBitsMatch"])
            actor_angles.append(a)
        if opts["refreshGuard"]:
            g=r["refreshGuardEvidence"]
            false_fields(g,"knownWriterExecuted","passiveFreshnessVerified")
            handle=owner(g["handleDecimal"],allow_zero=True)
            flag=integer(g["flagRaw"],0,255,"refresh flag")
            branch=("handle-present-guard-candidate" if handle!="0" else
                    "alternate-flag-guard-candidate" if flag else
                    "both-known-top-level-routes-ineligible-candidate")
            require(g["topLevelBranchCandidate"]==branch,"refresh branch mismatch")
            guards.add((handle,flag))
        if opts["actorTranslation"]:
            tr=r["actorTranslationEvidence"]
            false_fields(tr,"independentlyFresh")
            vector(tr["actorStoredXYZCandidate"],"actor translation")
            vector(tr["secondaryXYZCandidate"],"secondary translation")
            number(tr["reconstructionResidual"],"translation residual",0.)
            require(isinstance(tr["renderBranch"],str) and bool(tr["renderBranch"]),"render branch")
        if opts["zoneKey"]:
            z=r["zoneKeyEvidence"]
            false_fields(z,"authoritativeZoneQualified")
            raw=integer(z["rawSelfZoneKey"],0,2**32-1,"raw zone key")
            require(z["rawSelfZoneKeyHex"]==f"0x{raw:08X}"
                    and z["sourceStatus"]=="same-owner-typed-raw-zone-key-candidate"
                    and z["publicZoneIdStatus"]=="not-derived"
                    and z["worldInstanceStatus"]=="unavailable","zone candidate declaration")
            zones.add(raw)
            require(len(zones)==1,"raw zone key changed")
        if keys:
            k=r["manualWindowsKeyStates"]
            false_fields(k,"gameInputConsumptionVerified")
            before,after=k["beforeNativeRead"],k["afterNativeRead"]
            for snap in (before,after):
                states=snap["keys"]
                require(isinstance(states,dict) and set(states)=={"W","A","D"}
                        and all(type(v) is bool for v in states.values()),"key snapshot shape")
            bt=number(before["atMonotonicSeconds"],"before key poll",0.)
            at=number(after["atMonotonicSeconds"],"after key poll",0.)
            require(start<=bt<=observed<=at<=end,"key poll outside observation bracket")
            require(k["unchangedDuringNativeRead"] is (before["keys"]==after["keys"]),
                    "key bracket equality mismatch")
            key_polls+=2
    # The original format does not store outer admission start/end epochs;
    # check the enclosed span, not an invented exact admission duration.
    require(ends[-1]-starts[0]<=elapsed+1e-9,"sample span exceeds reported elapsed")
    _verify_gaps(doc["observedSampleGapSeconds"],_gap_summary(times))
    _verify_gaps(doc["observedCaptureStartGapSeconds"],_gap_summary(starts))
    if keys:
        # Reuse the pure summary function after checking all raw snapshots.
        # This audits receipt consistency, not independent game consumption.
        exact(doc["manualWindowsKeyObservation"],summarize_key_snapshots(rows),"key summary mismatch")
    else:
        require(doc["manualWindowsKeyObservation"] is None,"unexpected key summary")
    diff=[b-a for a,b in zip(positions[0],positions[-1])]
    change=doc["candidateChanges"]
    exact(change,{"anyXYZChanged":any(v!=positions[0] for v in positions[1:]),
        "anyYawChanged":any(v!=headings[0] for v in headings[1:]),
        "firstToLastDeltaXYZ":diff,
        "firstToLastHorizontalXZDistanceSourceUnits":math.hypot(diff[0],diff[2]),
        "firstToLastYawDeltaDegrees":(headings[-1]-headings[0]+180.)%360.-180.,
        "freshPositionVerified":False,"bodyHeadingVerified":False},"candidate change summary")
    return {"schema":"taxi.native-series-audit/1","status":"stored-candidate-consistent",
            "source":source,"samples":count,"uniqueXYZCandidates":len(set(positions)),
            "uniqueScalarBearingCandidates":len(set(headings)),
            "observedSampleGapSeconds":_gap_summary(times),
            "observedCaptureStartGapSeconds":_gap_summary(starts),
            "maxCaptureBracketSeconds":max(b-a for a,b in zip(starts,ends)),
            "matrixMatches":matches if opts["actorMatrix"] else None,
            "uniqueActorAngleCandidates":len(set(actor_angles)) if opts["actorMatrix"] else None,
            "rawZoneKeys":[f"0x{v:08X}" for v in sorted(zones)],
            "refreshGuardPairs":[{"handleDecimal":h,"flagRaw":f} for h,f in sorted(guards)],
            "keyPollsPerKey":key_polls,"keyDownPollsByKey":
                doc["manualWindowsKeyObservation"]["observedDownPollsByKey"] if keys else None,
            "actualCurrentSessionVerified":False,"passiveFreshnessVerified":False,
            "bodyHeadingVerified":False,"publicZoneIdVerified":False,"worldInstanceVerified":False,
            "gameInputConsumptionVerified":False,"gameInputSent":False,
            "productionInputAuthorized":False,
            "limitations":["Checks stored candidate receipt consistency and exact supplied pins only.",
                           "Does not prove source authenticity, current state, passive freshness, or physical release."]}


def audit(path,expected_sha256,**pin):
    """Load bounded exact original bytes and audit without process access."""
    try:
        doc,original=_pinned_json(path,expected_sha256,"native series")
        return {**audit_document(doc,**pin),"original":original}
    except SeriesAuditRefused:
        raise
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError) as exc:
        raise SeriesAuditRefused(f"stored series refused: {exc}") from exc


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("report",type=Path)
    p.add_argument("--expected-sha256",required=True)
    p.add_argument("--host",required=True)
    p.add_argument("--pid",type=int,required=True)
    p.add_argument("--start-ticks",type=int,required=True)
    p.add_argument("--exe-path",required=True)
    p.add_argument("--exe-sha256",required=True)
    p.add_argument("--hwnd",type=int,required=True)
    p.add_argument("--owner",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args(argv)
    try:
        if a.out.exists():
            raise FileExistsError(a.out)
        result=audit(a.report,a.expected_sha256,host=a.host,pid=a.pid,start_ticks=a.start_ticks,
                     exe_path=a.exe_path,exe_sha256=a.exe_sha256,hwnd=a.hwnd,owner_key=a.owner)
        with a.out.open("x",encoding="utf-8",newline="\n") as stream:
            stream.write(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n")
        print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))
        return 0
    except (SeriesAuditRefused,OSError,ValueError) as exc:
        p.exit(2,f"Native series audit refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
