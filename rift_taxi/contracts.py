"""Strict offline movement trace contracts; no game interaction or source imports."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Literal

SCHEMA = "taxi.motion-trace/1"
KINDS = frozenset({"guide", "optional", "mandatory_passage", "hard_stop", "destination"})
KEYS = frozenset({"W", "A", "D", "S", "Q", "E"})
MAX_BYTES = 8 * 1024 * 1024
MAX_SOURCE_BYTES = 64 * 1024 * 1024
_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
_COMMIT = re.compile(r"[0-9a-fA-F]{40}\Z")
_DRIVE_OR_ABSOLUTE = re.compile(r"^[A-Za-z]:")


class TraceError(ValueError):
    """Invalid, ambiguous or unsupported trace input."""


def _dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TraceError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TraceError(f"{label} must be an array")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise TraceError(f"{label} must be nonempty text without outer whitespace")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TraceError(f"{label} must be a finite number")
    try:
        x = float(value)
    except (OverflowError, ValueError) as error:
        raise TraceError(f"{label} must be finite") from error
    if not math.isfinite(x):
        raise TraceError(f"{label} must be finite")
    return x


def _xyz(value: Any, label: str) -> tuple[float, float, float]:
    items = _list(value, label)
    if len(items) != 3:
        raise TraceError(f"{label} must have X,Y,Z")
    return tuple(_number(v, f"{label}[{i}]") for i, v in enumerate(items))  # type: ignore[return-value]


def _require_keys(value: dict[str, Any], keys: set[str], label: str) -> None:
    if set(value) != keys:
        missing = sorted(keys - set(value))
        extra = sorted(set(value) - keys)
        raise TraceError(f"{label} fields differ: missing={missing} extra={extra}")


@dataclass(frozen=True)
class Point:
    name: str
    kind: Literal["guide", "optional", "mandatory_passage", "hard_stop", "destination"]
    xyz: tuple[float, float, float]


@dataclass(frozen=True)
class PoseSample:
    t: float
    xyz: tuple[float, float, float]
    actor_yaw_deg: float | None


@dataclass(frozen=True)
class InputEvent:
    t: float
    key: str
    edge: Literal["down", "up"]


@dataclass(frozen=True)
class MovementTrace:
    source_type: Literal["synthetic", "historical"]
    source: dict[str, Any]
    frame: dict[str, Any]
    route_id: str
    points: tuple[Point, ...]
    arrival_tolerance_xz: float
    window_start: float
    window_end: float
    poses: tuple[PoseSample, ...]
    events: tuple[InputEvent, ...]
    trace_sha256: str
    verified_source_sha256: str | None


def _verify_source_file(source: dict[str, Any], trace_path: Path) -> str:
    _require_keys(
        source,
        {"repository", "commit", "originalFile", "sha256", "timeBasis"},
        "historical source",
    )
    if _text(source["repository"], "source.repository") != "RR2":
        raise TraceError("historical input currently supports source.repository=RR2 only")
    if not _COMMIT.fullmatch(_text(source["commit"], "source.commit")):
        raise TraceError("source.commit must be a 40-digit Git SHA")
    if source["timeBasis"] not in {"single-monotonic", "same-host-utc"}:
        raise TraceError("historical trace requires an explicit single-clock time basis")
    expected = _text(source["sha256"], "source.sha256")
    if not _SHA256.fullmatch(expected):
        raise TraceError("source.sha256 must be 64 hex digits")
    relative = _text(source["originalFile"], "source.originalFile")
    if ("\\" in relative or _DRIVE_OR_ABSOLUTE.match(relative)
            or relative.startswith("/") or any(
                part in {"", ".", ".."} for part in relative.split("/")
            )):
        raise TraceError("historical source path must be a contained relative POSIX path")
    root = trace_path.parent.resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise TraceError("historical source file missing or outside trace folder")
    if candidate.stat().st_size > MAX_SOURCE_BYTES:
        raise TraceError("historical original source too large")
    digest = hashlib.sha256()
    with candidate.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest().lower() != expected.lower():
        raise TraceError("historical source SHA256 mismatch")
    return digest.hexdigest()


def load_trace(path: str | Path) -> MovementTrace:
    """Load locally bundled trace. Original historical bytes must be co-located and hash-verified.

    This validates integrity of *submitted* source material; it does not authenticate a
    real game session or independently certify that the submitted data is original.
    """
    file = Path(path)
    try:
        if file.stat().st_size > MAX_BYTES:
            raise TraceError("trace JSON too large")
        raw = file.read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TraceError(f"cannot load trace JSON: {error}") from error
    data = _dict(document, "trace")
    _require_keys(
        data,
        {"schema", "sourceType", "source", "frame", "route",
         "movementWindow", "poses", "events"},
        "trace",
    )
    if data["schema"] != SCHEMA:
        raise TraceError(f"unsupported trace schema: {data['schema']!r}")

    source_type = data["sourceType"]
    if source_type not in {"synthetic", "historical"}:
        raise TraceError("sourceType must be synthetic or historical")
    source = _dict(data["source"], "source")
    verified_sha = None
    if source_type == "synthetic":
        _require_keys(source, {"generator"}, "synthetic source")
        _text(source["generator"], "source.generator")
    else:
        verified_sha = _verify_source_file(source, file)

    frame = _dict(data["frame"], "frame")
    _require_keys(frame, {"frameId", "axisOrder", "upAxis", "units"}, "frame")
    _text(frame["frameId"], "frame.frameId")
    _text(frame["units"], "frame.units")
    if frame["axisOrder"] != ["x", "y", "z"] or frame["upAxis"] != "y":
        raise TraceError("frame must use X/Y/Z and Y-up; no silent conversion")

    route = _dict(data["route"], "route")
    _require_keys(route, {"id", "points", "arrivalToleranceXZ"}, "route")
    route_id = _text(route["id"], "route.id")
    tolerance = _number(route["arrivalToleranceXZ"], "arrivalToleranceXZ")
    if tolerance <= 0:
        raise TraceError("arrival tolerance must be positive")
    points = []
    for i, value in enumerate(_list(route["points"], "route.points")):
        point = _dict(value, f"point[{i}]")
        _require_keys(point, {"name", "kind", "xyz"}, f"point[{i}]")
        kind = point["kind"]
        if not isinstance(kind, str) or kind not in KINDS:
            raise TraceError(f"unsupported point kind at {i}")
        points.append(Point(
            name=_text(point["name"], f"point[{i}].name"),
            kind=kind, xyz=_xyz(point["xyz"], f"point[{i}].xyz"),
        ))
    if len(points) < 2 or len(points) > 500:
        raise TraceError("route requires 2-500 points")
    if points[-1].kind != "destination" or any(
        p.kind == "destination" for p in points[:-1]
    ):
        raise TraceError("only final route point may be destination")

    window = _list(data["movementWindow"], "movementWindow")
    if len(window) != 2:
        raise TraceError("movementWindow must contain start/end times")
    start = _number(window[0], "movementWindow[0]")
    end = _number(window[1], "movementWindow[1]")
    if not (0 <= start < end):
        raise TraceError("movementWindow must be positive and ordered")

    poses = []
    for i, value in enumerate(_list(data["poses"], "poses")):
        entry = _dict(value, f"pose[{i}]")
        _require_keys(entry, {"t", "xyz", "actorYawDeg"}, f"pose[{i}]")
        yaw = entry["actorYawDeg"]
        poses.append(PoseSample(
            t=_number(entry["t"], f"pose[{i}].t"),
            xyz=_xyz(entry["xyz"], f"pose[{i}].xyz"),
            actor_yaw_deg=(None if yaw is None else _number(yaw, f"pose[{i}].actorYawDeg")),
        ))
    if len(poses) < 2 or len(poses) > 250000:
        raise TraceError("poses requires 2-250000 samples")
    if any(p.t < 0 for p in poses) or any(
        b.t <= a.t for a, b in zip(poses, poses[1:])
    ):
        raise TraceError("poses must be strictly increasing nonnegative time")
    if start < poses[0].t or end > poses[-1].t:
        raise TraceError("movementWindow must lie inside pose sample range")

    events = []
    held: set[str] = set()
    previous_t = -1.0
    for i, value in enumerate(_list(data["events"], "events")):
        event = _dict(value, f"event[{i}]")
        _require_keys(event, {"t", "key", "edge"}, f"event[{i}]")
        t = _number(event["t"], f"event[{i}].t")
        key = event["key"]
        edge = event["edge"]
        if not isinstance(key, str) or key not in KEYS or not isinstance(edge, str) or edge not in {"down", "up"}:
            raise TraceError(f"event[{i}] has unsupported key or edge")
        if t < previous_t or not (poses[0].t <= t <= poses[-1].t):
            raise TraceError("events must be ordered and inside pose timeline")
        if edge == "down":
            if key in held:
                raise TraceError(f"duplicate key down: {key}")
            held.add(key)
            if "A" in held and "D" in held:
                raise TraceError("A and D cannot be held together in one input stream")
        else:
            if key not in held:
                raise TraceError(f"orphan key up: {key}")
            held.remove(key)
        previous_t = t
        events.append(InputEvent(t=t, key=key, edge=edge))
    if len(events) > 500000:
        raise TraceError("too many input events")

    if source_type == "historical" and source["timeBasis"] == "same-host-utc":
        # Integrity of raw bytes is not enough: the normalized pose/key timeline
        # must also agree with the SHA-verified original RR2 record.
        from .import_rr2 import _convert, _read_one_record

        original = file.parent / source["originalFile"]
        upstream, _ = _read_one_record(original)
        normalized, _ = _convert(
            upstream, source_sha=verified_sha, source_commit=source["commit"]
        )
        if data != normalized:
            raise TraceError("historical RR2 normalization differs from original source")

    return MovementTrace(
        source_type=source_type, source=source, frame=frame, route_id=route_id,
        points=tuple(points), arrival_tolerance_xz=tolerance,
        window_start=start, window_end=end, poses=tuple(poses),
        events=tuple(events), trace_sha256=hashlib.sha256(raw).hexdigest(),
        verified_source_sha256=verified_sha,
    )
