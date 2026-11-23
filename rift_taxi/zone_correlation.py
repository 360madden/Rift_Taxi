"""Offline, source-hashed comparison of Taxi and RR2 zone candidates.

The RR2 executable is never invoked here. Both original sources are explicit,
SHA-pinned files under the caller's control. A same-epoch native candidate
agreement is NOT independent public API or world instance verification.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import ntpath
from pathlib import Path
import re

_SHA = re.compile(r"[a-fA-F0-9]{64}\Z")
_ZONE = re.compile(r"z[0-9A-F]{16}\Z")
_OWNER = re.compile(r"[1-9][0-9]*\Z")
_MAX_BYTES = 1024*1024


class ZoneCorrelationRefused(ValueError):
    """Missing, altered, contradictory or insufficient candidate evidence."""


def _pinned_json(path: str | Path, expected_sha256: str, label: str) -> tuple[dict,dict]:
    if not isinstance(expected_sha256,str) or not _SHA.fullmatch(expected_sha256):
        raise ZoneCorrelationRefused(f"{label}: exact 64-hex original SHA-256 required")
    p=Path(path)
    if not p.is_file() or not 0 < p.stat().st_size <= _MAX_BYTES:
        raise ZoneCorrelationRefused(f"{label}: original file missing or unbounded")
    raw=p.read_bytes()
    actual=hashlib.sha256(raw).hexdigest()
    if actual!=expected_sha256.lower():
        raise ZoneCorrelationRefused(f"{label}: original SHA-256 mismatch")
    try:
        doc=json.loads(raw.decode("utf-8"), parse_constant=lambda val:
            (_ for _ in ()).throw(ZoneCorrelationRefused("non-finite JSON refused")))
    except (UnicodeError,ValueError) as ex:
        raise ZoneCorrelationRefused(f"{label}: invalid UTF-8 JSON") from ex
    if not isinstance(doc,dict):
        raise ZoneCorrelationRefused(f"{label}: root JSON object required")
    return doc,{"name":p.name,"originalSHA256":actual,"sizeBytes":len(raw)}


def _positive_int(value: object, name: str) -> int:
    if type(value) is not int or value<=0:
        raise ZoneCorrelationRefused(f"{name} must be positive exact integer")
    return value


def _source_identity(doc: dict, *, rr2: bool) -> tuple[int,int,str,str,int|None]:
    if rr2:
        obs=doc.get("observation")
        if not isinstance(obs,dict):
            raise ZoneCorrelationRefused("RR2 observation missing")
        ident=obs.get("identity")
        if not isinstance(ident,dict):
            raise ZoneCorrelationRefused("RR2 exact process identity missing")
        pid=_positive_int(ident.get("processId"),"RR2 PID")
        ticks=_positive_int(ident.get("processStartUtcTicks"),"RR2 epoch")
        exe=ident.get("executablePath")
        sha=ident.get("executableSha256")
        hwnd=None
    else:
        ident=doc.get("process")
        if not isinstance(ident,dict):
            raise ZoneCorrelationRefused("Taxi exact process identity missing")
        pid=_positive_int(ident.get("pid"),"Taxi PID")
        ticks=_positive_int(ident.get("startUtcTicks"),"Taxi epoch")
        exe=ident.get("executablePath")
        sha=ident.get("onDiskExecutableSha256")
        hwnd=_positive_int(ident.get("windowHandle"),"Taxi HWND")
        if ident.get("host") is None or not isinstance(ident["host"],str) or not ident["host"].strip():
            raise ZoneCorrelationRefused("Taxi host missing")
        if ident.get("foregroundAtStartAndEnd") is not True:
            raise ZoneCorrelationRefused("Taxi foreground source not confirmed")
    if not isinstance(exe,str) or not ntpath.isabs(exe):
        raise ZoneCorrelationRefused("absolute game executable source required")
    if not isinstance(sha,str) or not _SHA.fullmatch(sha):
        raise ZoneCorrelationRefused("exact game executable SHA required")
    return pid,ticks,ntpath.normcase(ntpath.normpath(exe)),sha.casefold(),hwnd


def _time(value: object, label: str) -> datetime:
    if not isinstance(value,str):
        raise ZoneCorrelationRefused(f"{label}: timestamp required")
    try:
        d=datetime.fromisoformat(value)
    except ValueError as error:
        raise ZoneCorrelationRefused(f"{label}: invalid source timestamp") from error
    if d.tzinfo is None or d.utcoffset() is None:
        raise ZoneCorrelationRefused(f"{label}: timezone required")
    return d.astimezone(timezone.utc)


def compare_native_zone_sources(
    *, taxi_report: str | Path, taxi_sha256: str,
    rr2_report: str | Path, rr2_sha256: str,
) -> dict:
    """Check exact same process/owner/raw key and preserve the typed zone ID.

    No equivalence to RIFT Inspect.Unit.Detail('player').zone is inferred.
    """
    if Path(taxi_report).resolve()==Path(rr2_report).resolve():
        raise ZoneCorrelationRefused("two different original source files required")
    taxi,taxi_file=_pinned_json(taxi_report,taxi_sha256,"Taxi source")
    rr2,rr2_file=_pinned_json(rr2_report,rr2_sha256,"RR2 source")
    if (taxi.get("schema")!="taxi.native-candidate/1"
            or taxi.get("status")!="candidate-only"
            or taxi.get("evidence",{}).get("zoneKeyEvidenceRequested") is not True
            or taxi.get("evidence",{}).get("inputSent") is not False
            or taxi.get("evidence",{}).get("actorHeadingQualified") is not False
            or taxi.get("evidence",{}).get("passivePositionFreshnessQualified") is not False):
        raise ZoneCorrelationRefused("Taxi source must remain read-only, candidate-only zone observation")
    if (rr2.get("schemaVersion")!=1
            or rr2.get("contractVersion")!="native-current-zone-seed-candidate/1"
            or rr2.get("status")!="complete"):
        raise ZoneCorrelationRefused("RR2 original native zone-seed contract required")
    a=_source_identity(taxi,rr2=False)
    b=_source_identity(rr2,rr2=True)
    if a[:4]!=b[:4]:
        raise ZoneCorrelationRefused("native process/start epoch/executable SHA/path mismatch")
    t_candidate=taxi.get("candidate")
    t_zone=taxi.get("zoneKeyEvidence")
    obs=rr2.get("observation")
    if (not isinstance(t_candidate,dict) or not isinstance(t_zone,dict)
            or not isinstance(obs,dict)):
        raise ZoneCorrelationRefused("missing candidate payload")
    owner=t_candidate.get("ownerKeyDecimal")
    if (not isinstance(owner,str) or not _OWNER.fullmatch(owner)
            or int(owner)!=_positive_int(obs.get("selfKey"),"RR2 self key")):
        raise ZoneCorrelationRefused("same player owner not verified")
    raw=t_zone.get("rawSelfZoneKey")
    native_raw=obs.get("rawZoneKey")
    if (type(raw) is not int or type(native_raw) is not int
            or not 0<=raw<=0xFFFFFFFF or raw!=native_raw
            or t_zone.get("rawSelfZoneKeyHex")!=f"0x{raw:08X}"):
        raise ZoneCorrelationRefused("raw zone key mismatch or bad format")
    if (t_zone.get("authoritativeZoneQualified") is not False
            or t_zone.get("publicZoneIdStatus")!="not-derived"
            or t_zone.get("worldInstanceStatus")!="unavailable"):
        raise ZoneCorrelationRefused("Taxi raw key cannot claim public zone authority")
    full_id=obs.get("zoneIdCandidate")
    child=obs.get("childKey")
    if (obs.get("status")!="type-0073-candidate"
            or obs.get("childStatus")!="type-1e17-raw-candidate"
            or obs.get("outerVtableCandidate") is not True
            or type(child) is not int or not 0<=child<=0xFFFFFFFF
            or not isinstance(full_id,str) or not _ZONE.fullmatch(full_id)
            or not full_id.startswith(f"z{raw:08X}")):
        raise ZoneCorrelationRefused("RR2 typed native record/zone ID candidate unqualified")
    if (not isinstance(obs.get("qualification"),str)
            or "candidate" not in obs["qualification"]):
        raise ZoneCorrelationRefused("RR2 zone qualification unavailable")
    t=_time(obs.get("startedAtUtc"),"RR2 startedAtUtc")
    u=_time(obs.get("completedAtUtc"),"RR2 completedAtUtc")
    if u<t or (u-t).total_seconds()>5:
        raise ZoneCorrelationRefused("RR2 native observation bracket invalid")
    clock=t_candidate.get("observationMonotonicSeconds")
    if isinstance(clock,bool) or not isinstance(clock,(int,float)) or clock<=0:
        raise ZoneCorrelationRefused("Taxi monotonic sample clock invalid")
    return {
        "schema":"taxi.m1-cross-source-zone-candidate/1",
        "status":"native-zone-candidates-correlated-not-publicly-qualified",
        "originals":{"taxi":taxi_file,"rr2":rr2_file},
        "sameSourceIdentity":{
            "pid":a[0],"startUtcTicks":a[1],
            "onDiskExecutableSha256":a[3],"exactWindowsExePathMatch":True,
            "taxiWindowHandle":a[4],"nativeOwnerKeyDecimal":owner,
        },
        "candidates":{
            "rawSelfZoneKeyHex":f"0x{raw:08X}",
            "rawSelfZoneKeyUnsigned":raw,
            "nativeZoneIdCandidate":full_id,
            "rr2TypedRecordStatus":obs["status"],
            "rr2ChildRecordStatus":obs["childStatus"],
            "rr2ChildRawKey":child,
            "rr2NativeReadStartUtc":t.isoformat(),
            "rr2NativeReadEndUtc":u.isoformat(),
            "taxiSourceMonotonicSeconds":float(clock),
        },
        "qualification":{
            "sourceOriginalsSHA256Verified":True,
            "exactGameEpochAndPlayerOwnerMatch":True,
            "twoRawNativeKeyReadingsAgree":True,
            "publicZoneIdFromAddonApiVerified":False,
            "publicLocationNameVerified":False,
            "worldInstanceVerified":False,
            "passiveNativeXYZFreshnessVerified":False,
            "bodyHeadingVerified":False,
            "productionNavigationArmed":False,
            "M1Complete":False,
        },
        "limitations":[
            "Both native readers access the same game process; not a public API independent zone confirmation.",
            "Taxi monotonic and RR2 UTC clocks cannot be directly compared without a calibration.",
            "The native source observations are sequential and cannot establish atomic world-instance identity.",
            "Typed native zone ID is only a candidate until corroborated by Inspect.Unit.Detail/Inspect.Zone.Detail.",
            "No game input, addon modification, sibling build/commit or runtime RR2 dependency occurs here.",
        ],
    }
