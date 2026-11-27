"""Offline import of original RR2 native-continuous-move JSONL receipts.

No game process is opened, no RR2 executable is launched, and no input is sent.
Imported records remain historical and never qualify a live Taxi journey.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from .contracts import TraceError, MAX_SOURCE_BYTES, load_trace, _read_bounded, _strict_json, _number

_COMMIT = re.compile(r"[a-fA-F0-9]{40}\Z")
_SHA = re.compile(r"[a-fA-F0-9]{64}\Z")


def _required_obj(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise TraceError(f"{label} must be an object")
    return value


def _valid_xyz(value: Any, label: str) -> list[float]:
    obj = _required_obj(value, label)
    try:
        # Keep numeric JSON types strict: a bool or numeric string is not
        # an observed coordinate, even if float() would accept it.
        return [_number(obj[key], f"{label}.{key}") for key in ("x", "y", "z")]
    except KeyError as error:
        raise TraceError(f"{label} requires numeric x/y/z") from error


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise TraceError(f"{label} must be ISO 8601 text")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise TraceError(f"{label} is invalid ISO 8601") from error
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise TraceError(f"{label} requires explicit UTC offset")
    return instant


def _decode_one_record(raw: bytes) -> dict:
    """Parse the caller's exact bounded byte snapshot; never reopen a path."""
    try:
        records = raw.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as error:
        raise TraceError(f"cannot decode RR2 original JSONL: {error}") from error
    if len(records) != 1 or not records[0].strip():
        raise TraceError("only a single original RR2 JSONL record is supported")
    return _required_obj(_strict_json(records[0], "RR2 original JSONL"), "RR2 source record")


def _read_one_record(path: Path) -> tuple[dict, bytes]:
    raw = _read_bounded(path, MAX_SOURCE_BYTES, "RR2 JSONL source")
    return _decode_one_record(raw), raw


def _relative_seconds(dt: datetime, origin: datetime) -> float:
    return (dt - origin).total_seconds()


def _convert(record: dict, *, source_sha: str, source_commit: str) -> tuple[dict, dict]:
    if record.get("kind") != "native-continuous-move":
        raise TraceError("source is not an RR2 native-continuous-move record")
    target = _required_obj(record.get("target"), "target")
    if not isinstance(record.get("playerKey"), str) or not record["playerKey"]:
        raise TraceError("RR2 source needs playerKey")
    if not isinstance(target.get("machineName"), str) or not target["machineName"]:
        raise TraceError("RR2 source needs target machine")
    if (type(target.get("processId")) is not int or target["processId"] <= 0
            or type(target.get("processStartUtcTicks")) is not int
            or target["processStartUtcTicks"] <= 0):
        raise TraceError("RR2 source needs exact process ID and start ticks")
    sha = target.get("executableSha256")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise TraceError("RR2 source requires exact executable SHA256")

    path = record.get("path")
    events = record.get("keySendEvents")
    if not isinstance(path, list) or len(path) < 2:
        raise TraceError("RR2 source requires at least two observed poses")
    if not isinstance(events, list) or len(events) < 2:
        raise TraceError("RR2 source requires input event timestamps")
    origin = _utc(_required_obj(path[0], "path[0]").get("observedAtUtc"), "path[0].observedAtUtc")
    poses = []
    for i, sample in enumerate(path):
        row = _required_obj(sample, f"path[{i}]")
        t = _relative_seconds(_utc(row.get("observedAtUtc"), f"path[{i}].observedAtUtc"), origin)
        poses.append({
            "t": t,
            "xyz": _valid_xyz(row, f"path[{i}]"),
            # RR2's native 'bearing' in this artifact is a *candidate* field.
            # Do not silently promote it into qualified actor yaw.
            "actorYawDeg": None,
        })

    normalized_events = []
    for i, source_event in enumerate(events):
        row = _required_obj(source_event, f"keySendEvents[{i}]")
        key = row.get("key")
        if not isinstance(key, str) or key.lower() not in {"w", "a", "d", "s", "q", "e"}:
            raise TraceError("RR2 original key event is unsupported")
        phase = row.get("phase")
        if phase not in ("key-down", "key-up") or row.get("inserted") is not True:
            raise TraceError("RR2 key send event must be an inserted key-down/up")
        began = _utc(row.get("callStartedAtUtc"), f"keySendEvents[{i}].callStartedAtUtc")
        ended = _utc(row.get("callCompletedAtUtc"), f"keySendEvents[{i}].callCompletedAtUtc")
        if ended < began:
            raise TraceError("RR2 key send completed before it started")
        normalized_events.append({
            "t": _relative_seconds(began, origin),
            "key": key.upper(),
            "edge": "down" if phase == "key-down" else "up",
        })
    if not any(e["key"] == "W" and e["edge"] == "down" for e in normalized_events):
        raise TraceError("RR2 source contains no forward movement input")

    goal = _valid_xyz(record.get("goal"), "goal")
    route_points = [{
        "name": "Source first pose", "kind": "guide",
        "xyz": poses[0]["xyz"],
    }]
    passage = record.get("passedWaypoints")
    if passage is not None:
        if not isinstance(passage, list):
            raise TraceError("passedWaypoints must be an array")
        for i, row in enumerate(passage):
            point = _required_obj(row, f"passedWaypoints[{i}]")
            name = point.get("name")
            if not isinstance(name, str) or not name.strip():
                raise TraceError("passed waypoint requires name")
            route_points.append({
                "name": name.strip(),
                # RR2's automatic 'settled-corner' is a measured *stop*,
                # but is not proof that user requested a hard stop.
                "kind": "guide",
                "xyz": _valid_xyz(point.get("position"), f"passedWaypoints[{i}]"),
            })
    route_points.append({"name": "Recorded final goal", "kind": "destination", "xyz": goal})

    if normalized_events[0]["t"] < poses[0]["t"] or normalized_events[-1]["t"] > poses[-1]["t"]:
        raise TraceError("RR2 send events fall outside original pose observation window")
    window_start = normalized_events[0]["t"]
    window_end = normalized_events[-1]["t"]
    if window_end <= window_start:
        raise TraceError("RR2 input window must have positive duration")

    trace = {
        "schema": "taxi.motion-trace/1",
        "sourceType": "historical",
        "source": {
            "repository": "RR2",
            "commit": source_commit,
            "originalFile": "sources/original.jsonl",
            "sha256": source_sha,
            "timeBasis": "same-host-utc",
        },
        "frame": {
            "frameId": "rift-native-xyz-candidate",
            "axisOrder": ["x", "y", "z"], "upAxis": "y",
            "units": "source-world-unit",
        },
        "route": {
            "id": "rr2-native-" + source_sha[:16],
            "points": route_points,
            "arrivalToleranceXZ": 0.3,
        },
        "movementWindow": [window_start, window_end],
        "poses": poses,
        "events": normalized_events,
    }
    manifest = {
        "schema": "taxi.rr2-import-manifest/1",
        "sourceSHA256": source_sha,
        "sourceRepository": "RR2",
        "referencedSourceSnapshotCommit": source_commit,
        "snapshotCommitAuthenticatesCapture": False,
        "target": {
            "machineName": target["machineName"],
            "processId": target["processId"],
            "processStartUtcTicks": target["processStartUtcTicks"],
            "executableSha256": sha,
            "playerKey": record["playerKey"],
        },
        "upstreamReportedStatus": record.get("status"),
        "upstreamReportedReleaseSucceeded": record.get("releaseSucceeded"),
        "sourcePoseCount": len(poses),
        "sourceKeySendEvents": len(normalized_events),
        "timeBasis": "same-host-utc",
        "uncertainty": [
            "UTC source clocks can jump; only original event ordering is established.",
            "Key-send insertion is not proof game consumed input.",
            "Original bearing is candidate-only; Taxi actorYawDeg intentionally unavailable.",
            "Historical RR2 completion does not verify a new Taxi live arrival.",
            "Passed guides may have RR2 automatic pauses, not user hard-stop requirements.",
        ],
    }
    return trace, manifest


def import_rr2(source_file: str | Path, output_dir: str | Path, *, source_commit: str) -> dict:
    """Atomically create a self-contained, ignored data bundle with original source bytes."""
    if not _COMMIT.fullmatch(source_commit):
        raise TraceError("--source-commit needs an explicit 40-character repository SHA")
    source = Path(source_file)
    output = Path(output_dir)
    if output.exists() or not output.parent.is_dir():
        raise TraceError("output directory must be new with an existing parent")
    record, raw = _read_one_record(source)
    digest = hashlib.sha256(raw).hexdigest()
    trace, manifest = _convert(record, source_sha=digest, source_commit=source_commit)
    staging_path: Path | None = None
    try:
        staging_path = Path(tempfile.mkdtemp(prefix=".taxi-rr2-", dir=output.parent))
        (staging_path / "sources").mkdir()
        (staging_path / "sources" / "original.jsonl").write_bytes(raw)
        (staging_path / "trace.json").write_text(
            json.dumps(trace, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        (staging_path / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        validated = load_trace(staging_path / "trace.json")
        if output.exists():
            raise TraceError("refusing to overwrite an existing destination")
        os.rename(staging_path, output)
        staging_path = None
    finally:
        if staging_path is not None:
            shutil.rmtree(staging_path, ignore_errors=True)

    return {
        "schema": "taxi.rr2-import-result/1",
        "status": "imported-historical-offline",
        "originalSourceSha256": digest,
        "traceSha256": validated.trace_sha256,
        "sourceIntegrityVerified": validated.verified_source_sha256 == digest,
        "liveTaxiJourneyVerified": False,
        "output": str(output),
        "poseCount": len(validated.poses),
        "keyEventCount": len(validated.events),
    }
