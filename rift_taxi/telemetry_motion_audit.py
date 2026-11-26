"""Offline motion-field inventory of an already replayed RR2 Telemetry bracket.

This is a narrow second-stage audit, not another zone-capture implementation.
The caller pins both the original bracket summary and its upstream zone-replay
receipt. We reopen and hash each accepted original wire, check its generation,
player, sequence and source-clock projection, then report XYZ coverage and
changes. No game/process access or sibling runtime dependency. Source clocks
are not host UTC; retained-frame gaps do not measure live reader latency.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import ntpath
from pathlib import Path
import re
import stat
import statistics

from .zone_correlation import _pinned_json, _unique_object, _finite_float

PREFIX, SUFFIX = b"RIFTTLM1|", b"|ENDRIFTTLM1"
MAX_WIRE = 32768
COORDS = ("coordX", "coordY", "coordZ")
# Inventory these names only. A field's presence is never proof of body yaw,
# sign, units, coordinate convention, or independent position freshness.
HEADING_NAMES = frozenset(("heading", "facing", "yaw", "orientation",
                           "rotation", "angle", "direction", "bodyheading",
                           "bodyyaw", "actorheading", "actoryaw"))


class MotionAuditRefused(ValueError):
    """A pinned source is missing, inconsistent, or outside the supported scope."""


def require(ok, reason):
    if not ok:
        raise MotionAuditRefused(reason)


def positive(value):
    return type(value) is int and 0 < value <= 2**63-1


def epoch_ticks(value):
    """The upstream contract uses canonical decimal text for the process epoch."""
    return (isinstance(value,str) and re.fullmatch(r"[1-9][0-9]{0,18}",value)
            is not None and int(value)<=2**63-1)


def sha_text(value):
    return isinstance(value,str) and re.fullmatch(r"[0-9a-fA-F]{64}",value) is not None


def finite(value, low=-1e9, high=1e9):
    return type(value) in (int,float) and low <= value <= high


def read_wire(path, expected):
    """Read bounded bytes, refusing links/reparse points and invalid digests."""
    require(isinstance(expected,str) and re.fullmatch(r"[0-9a-fA-F]{64}",expected),
            "wire SHA-256 missing")
    info=path.lstat()
    require(stat.S_ISREG(info.st_mode) and not getattr(info,"st_file_attributes",0)&0x400
            and 0 < info.st_size <= MAX_WIRE, "wire not a bounded regular file")
    with path.open("rb") as f:
        raw=f.read(MAX_WIRE+1)
    require(0 < len(raw)<=MAX_WIRE and hashlib.sha256(raw).hexdigest()==expected.lower(),
            "wire size or digest mismatch")
    require(raw.startswith(PREFIX+b"{") and raw.endswith(SUFFIX),"wire envelope")
    def reject_constant(_):
        raise MotionAuditRefused("nonfinite JSON constant")
    return json.loads(raw[len(PREFIX):-len(SUFFIX)].decode("utf-8"),
                      object_pairs_hook=_unique_object,parse_float=_finite_float,
                      parse_constant=reject_constant)


def coordinates(player):
    """Missing or partial XYZ stays unavailable; malformed present fields refuse."""
    for k in COORDS:
        if k in player:
            require(finite(player[k]),"invalid API coordinate")
    if not all(k in player for k in COORDS):
        return None
    return [float(player[k]) for k in COORDS]


def project(doc, row, replay):
    """Check source projection before keeping only motion-relevant data."""
    require(isinstance(doc,dict) and type(doc.get("schemaVersion")) is int
            and doc["schemaVersion"]==4 and doc.get("addon")=="Telemetry"
            and doc.get("addonVersion")=="0.5.0" and doc.get("source")=="rift-api"
            and doc.get("status")=="observed","wire schema/status")
    s,e,t=doc.get("sequence"),doc.get("epoch"),doc.get("frameTime")
    require(positive(s) and positive(e) and finite(t,0.,1e12),"wire sequence/clock")
    require(positive(row.get("seq")) and positive(row.get("epoch"))
            and finite(row.get("clock"),0.,1e12)
            and s==row["seq"] and e==row["epoch"] and t==row["clock"]
            and e==replay["sourceEpoch"]
            and doc.get("sessionId")==row.get("session")==replay["sourceSessionId"],
            "wire generation/index projection")
    p=doc.get("player")
    pt=doc.get("playerTelemetry")
    require(isinstance(p,dict) and isinstance(pt,dict)
            and doc.get("playerId")==p.get("id")==pt.get("id")==replay["playerUnitId"]
            and pt.get("status")=="observed","API player projection")
    z=pt.get("zone")
    require(isinstance(z,dict) and z.get("status")=="observed"
            and z.get("id")==p.get("zone")==row.get("zoneId")==replay["zoneIdCandidate"],
            "API zone projection")
    return {"sequence":s,"sourceFrameSeconds":float(t),"xyzCandidate":coordinates(p),
            "headingLikeFieldNames":sorted(k for k in p if k.lower() in HEADING_NAMES),
            "wireSHA256":row["sha"].lower()}


def _audit(summary_path, summary_sha, replay_path, replay_sha):
    summary, original=_pinned_json(summary_path,summary_sha,"bracket summary")
    replay, replay_original=_pinned_json(replay_path,replay_sha,"upstream replay")
    require(summary.get("evidenceKind")=="physical-native-telemetry-zone-bracket-candidate/1"
            and replay.get("evidenceKind")=="physical-native-telemetry-zone-offline-replay/1"
            and all(type(d.get("schemaVersion")) is int and d["schemaVersion"]==1
                    and d.get("status")=="matching-candidates" for d in (summary,replay))
            and summary.get("sameProcessEpoch") is True,"successful upstream bracket required")
    require(isinstance(replay.get("evidenceSummarySha256"),str)
            and replay["evidenceSummarySha256"].lower()==original["originalSHA256"],
            "replay does not bind original summary")
    target=summary["target"]
    require(positive(target.get("processId")) and positive(replay.get("processId"))
            and target["processId"]==replay["processId"]
            and target["processId"]<=2**32-1
            and isinstance(target.get("hostName"),str) and bool(target["hostName"].strip())
            and target["hostName"]==target["hostName"].strip()
            and target["hostName"]==replay.get("hostName")
            and epoch_ticks(target.get("processStartUtcTicks"))
            and epoch_ticks(replay.get("processStartUtcTicks"))
            and target["processStartUtcTicks"]==replay["processStartUtcTicks"]
            and sha_text(target.get("executableSha256"))
            and sha_text(replay.get("executableSha256"))
            and target["executableSha256"].lower()==replay["executableSha256"].lower(),
            "upstream process pin mismatch")
    require(isinstance(replay.get("playerUnitId"),str)
            and re.fullmatch(r"u[0-9A-F]{16}",replay["playerUnitId"])
            and isinstance(replay.get("zoneIdCandidate"),str)
            and re.fullmatch(r"z[0-9A-F]{16}",replay["zoneIdCandidate"])
            and isinstance(replay.get("sourceSessionId"),str)
            and re.fullmatch(r"[0-9a-f]{32}",replay["sourceSessionId"])
            and positive(replay.get("sourceEpoch")),"upstream player/zone/generation")
    # Only accepted wires contribute to motion metrics. Excluded and failed
    # rows remain in the upstream archive; their zone replay is not replaced.
    root=Path(summary_path).parent
    passes=summary["passes"]
    require(isinstance(passes,list) and len(passes)==2,"capture pass count")
    # Refuse JSON bool/float aliases of integer counts. An upstream replay
    # receipt is an integrity-pinned dependency, not a reason to trust an
    # ill-typed projection at this downstream boundary.
    saved=replay.get("savedFrames")
    require(isinstance(saved,list) and len(saved)==2
            and all(positive(n) and n<=50 for n in saved)
            and all(positive(replay.get(k)) for k in
                    ("uniqueSourceSequences","firstSourceSequence","lastSourceSequence",
                     "newAdvancingSourceFrames")),"upstream count types")
    unique={}; pass_sequences=[]; counts=[]
    for i,entry in enumerate(passes,1):
        frames=entry["frames"]
        require(isinstance(frames,list) and 2<=len(frames)<=50,"bounded frame inventory")
        seqs=[]
        for n,row in enumerate(frames,1):
            require(isinstance(row,dict),"frame row")
            if "sha" not in row:
                # Match the known upstream refusal categories. We do not
                # revalidate excluded raw wires or the full zone proof here.
                require(row.get("error") in ("incomplete","schema-or-player-zone",
                        "invalid-json-or-frame","nonselected-publisher-generation"),
                        "unclassified skipped frame")
                continue
            name=f"frame-{n:02d}.wire"
            require(isinstance(row.get("wire"),str) and ntpath.basename(row["wire"])==name,
                    "wire index path mismatch")
            doc=read_wire(root/f"pass-{i:02d}"/name,row["sha"])
            r=project(doc,row,replay)
            s=r["sequence"]
            if s in unique:
                require(unique[s]==r,"conflicting retained sequence")
            unique[s]=r
            seqs.append(s)
        require(len(seqs)>=2,"insufficient accepted frames")
        pass_sequences.append(seqs);counts.append(len(seqs))
    rows=[unique[s] for s in sorted(unique)]
    require(counts==replay["savedFrames"] and len(rows)==replay["uniqueSourceSequences"]
            and rows[0]["sequence"]==replay["firstSourceSequence"]
            and rows[-1]["sequence"]==replay["lastSourceSequence"],"upstream frame counts")
    advancing=[s for s in pass_sequences[1] if s>max(pass_sequences[0])]
    require(len(advancing)==replay["newAdvancingSourceFrames"] and bool(advancing),
            "upstream advancing count")
    gaps=[b["sourceFrameSeconds"]-a["sourceFrameSeconds"] for a,b in zip(rows,rows[1:])]
    require(all(g>0 for g in gaps),"source clock did not advance")
    usable=[r for r in rows if r["xyzCandidate"] is not None]
    pairs=[]; adjacent_count=0; consecutive_count=0
    for a,b in zip(rows,rows[1:]):
        # Do not bridge missing coordinate observations. Separately count
        # actual consecutive publisher sequences versus retained gaps.
        if a["xyzCandidate"] is None or b["xyzCandidate"] is None:
            continue
        adjacent_count+=1
        consecutive=b["sequence"]==a["sequence"]+1
        consecutive_count+=int(consecutive)
        p,q=a["xyzCandidate"],b["xyzCandidate"]
        delta=math.hypot(q[0]-p[0],q[2]-p[2])
        pairs.append({"fromSequence":a["sequence"],"toSequence":b["sequence"],
                      "consecutivePublisherSequences":consecutive,
                      "sourceIntervalSeconds":b["sourceFrameSeconds"]-a["sourceFrameSeconds"],
                      "xzCandidateDifference":delta,"xyzChanged":p!=q})
    return {"schema":"taxi.telemetry-motion-audit/1","status":"stored-api-motion-fields-audited",
            "originals":{"summary":original,"upstreamZoneReplay":replay_original},
            "target":{"host":replay["hostName"],"pid":replay["processId"],
                      "startUtcTicks":replay["processStartUtcTicks"],
                      "buildSHA256":replay["executableSha256"].lower(),
                      "playerUnitId":replay["playerUnitId"],"zoneId":replay["zoneIdCandidate"]},
            "frameOccurrences":sum(counts),"uniqueSequences":len(rows),
            "newAdvancingSequences":sorted(set(advancing)),
            "sourceClockSpanSeconds":rows[-1]["sourceFrameSeconds"]-rows[0]["sourceFrameSeconds"],
            "retainedSourceGapSeconds":{"minimum":min(gaps),"median":statistics.median(gaps),
                                        "maximum":max(gaps)},
            "xyzAvailableFrames":len(usable),"uniqueXYZCandidates":len({tuple(r["xyzCandidate"]) for r in usable}),
            "headingLikeFieldNames":sorted({n for r in rows for n in r["headingLikeFieldNames"]}),
            "adjacentComparablePairs":adjacent_count,"consecutiveComparablePairs":consecutive_count,
            "changedComparablePairs":sum(r["xyzChanged"] for r in pairs),
            "maxAdjacentXZDifference":max((r["xzCandidateDifference"] for r in pairs),default=None),
            "frames":rows,"pairs":pairs,"sourceClockHostAligned":False,
            "nativePassiveFreshnessVerified":False,"bodyHeadingVerified":False,
            "gameInputConsumptionVerified":False,"actualCurrentSessionVerified":False,
            "productionInputAuthorized":False,
            "limitations":["Upstream zone replay is a pinned input, not independently reimplemented here.",
                           "Only accepted original wire motion fields are audited; absence is not API-wide absence.",
                           "Source timestamps and retained-frame spacing do not establish reader latency or position freshness.",
                           "Adjacent retained coordinate differences are not causal motion, speed, or body heading."]}


def audit(summary_path,summary_sha,replay_path,replay_sha):
    try:
        return _audit(summary_path,summary_sha,replay_path,replay_sha)
    except MotionAuditRefused:
        raise
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError,RecursionError) as exc:
        raise MotionAuditRefused(f"motion evidence refused: {exc}") from exc


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--summary",type=Path,required=True)
    p.add_argument("--summary-sha",required=True)
    p.add_argument("--replay",type=Path,required=True)
    p.add_argument("--replay-sha",required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args(argv)
    try:
        if a.out.exists():
            raise FileExistsError(a.out)
        result=audit(a.summary,a.summary_sha,a.replay,a.replay_sha)
        with a.out.open("x",encoding="utf-8",newline="\n") as f:
            f.write(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
        print(json.dumps({k:v for k,v in result.items() if k not in ("frames","pairs")},
                         sort_keys=True,indent=2,allow_nan=False))
        return 0
    except (MotionAuditRefused,OSError,ValueError) as exc:
        p.exit(2,f"Telemetry motion audit refused: {exc}\n")


if __name__=="__main__":
    raise SystemExit(main())
