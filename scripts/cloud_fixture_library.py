"""Verify the explicitly approved cloud fixture library.

Development-only: reads a bounded source-controlled manifest and its named
synthetic motion traces, verifies exact bytes with SHA-256, and reuses Taxi's
existing trace contract on an isolated copy. No globbing of local captures,
no historical source import, no game access, no physical qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import tempfile

from rift_taxi.contracts import TraceError, load_trace

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "samples/cloud_fixtures.json"
SCHEMA = "taxi.cloud-fixture-library/1"
MAX_MANIFEST = 64 * 1024
MAX_FIXTURE = 1024 * 1024
MAX_FIXTURES = 32
ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}\Z")
PATH = re.compile(r"samples/(?:cloud_fixtures/)?[a-z0-9][a-z0-9_-]{0,79}\.json\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
FIELDS = {
    "id", "path", "sha256", "sizeBytes", "traceSchema", "sourceType",
    "generator", "routeId", "units", "pointCount", "poseCount", "eventCount",
}


class FixtureLibraryError(ValueError):
    """A portable fixture or manifest is invalid or not explicitly approved."""


def require(condition, message):
    if not condition:
        raise FixtureLibraryError(message)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _finite_float(value):
    parsed = float(value)
    require(math.isfinite(parsed), "non-finite JSON number")
    return parsed


def _constant(_value):
    raise FixtureLibraryError("non-finite JSON constant")


def _json(raw):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                          parse_float=_finite_float, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise FixtureLibraryError("invalid fixture JSON") from exc


def _bounded_file(root, relative, maximum):
    """Check each path component; never follow a fixture-directory symlink."""
    current = root
    parts = relative.split("/")
    for i, part in enumerate(parts):
        current = current / part
        info = current.lstat()
        require(not stat.S_ISLNK(info.st_mode)
                and not (getattr(info, "st_file_attributes", 0) & 0x400),
                "fixture path is a link or reparse point")
        final = i == len(parts)-1
        require(stat.S_ISREG(info.st_mode) if final else stat.S_ISDIR(info.st_mode),
                "fixture path is not a regular file or directory")
    require(0 < info.st_size <= maximum, "fixture size outside bound")
    with current.open("rb") as stream:
        raw = stream.read(maximum+1)
    require(0 < len(raw) <= maximum, "fixture read outside bound")
    return raw


def _integer(value, lo, hi):
    return type(value) is int and lo <= value <= hi


def _verify_entry(root, row):
    require(isinstance(row, dict) and set(row) == FIELDS, "fixture entry fields")
    require(isinstance(row["id"], str) and ID.fullmatch(row["id"]), "fixture ID")
    require(isinstance(row["path"], str) and PATH.fullmatch(row["path"])
            and row["path"] != MANIFEST, "fixture path outside approved sample folders")
    require(isinstance(row["sha256"], str) and DIGEST.fullmatch(row["sha256"]),
            "fixture digest format")
    require(row["traceSchema"] == "taxi.motion-trace/1"
            and row["sourceType"] == "synthetic"
            and row["units"] == "synthetic-units", "non-synthetic fixture declaration")
    for name in ("generator", "routeId"):
        require(isinstance(row[name], str) and 0 < len(row[name]) <= 160,
                "invalid fixture metadata")
    require(_integer(row["sizeBytes"], 1, MAX_FIXTURE)
            and _integer(row["pointCount"], 2, 500)
            and _integer(row["poseCount"], 2, 250000)
            and _integer(row["eventCount"], 0, 500000), "fixture count or size")
    raw = _bounded_file(root, row["path"], MAX_FIXTURE)
    require(len(raw) == row["sizeBytes"]
            and hashlib.sha256(raw).hexdigest() == row["sha256"], "fixture bytes mismatch")
    doc = _json(raw)
    require(isinstance(doc, dict)
            and set(doc) == {"schema", "sourceType", "source", "frame", "route",
                             "movementWindow", "poses", "events"}
            and doc.get("schema") == row["traceSchema"]
            and doc.get("sourceType") == "synthetic"
            and doc.get("source") == {"generator": row["generator"]},
            "fixture is not an approved standalone synthetic trace")
    # Validate the exact bytes already checked, not a later reread of a path
    # that could change. The isolated directory contains no historical originals.
    with tempfile.TemporaryDirectory(prefix="taxi-cloud-fixture-") as temp:
        copy = Path(temp) / "trace.json"
        copy.write_bytes(raw)
        trace = load_trace(copy)
    require(trace.trace_sha256 == row["sha256"]
            and trace.source_type == "synthetic"
            and trace.verified_source_sha256 is None
            and trace.frame["units"] == row["units"]
            and trace.route_id == row["routeId"]
            and len(trace.points) == row["pointCount"]
            and len(trace.poses) == row["poseCount"]
            and len(trace.events) == row["eventCount"],
            "fixture semantic projection mismatch")
    return dict(row)


def verify_library(root=ROOT):
    """Return a deterministic integrity receipt; no scan or upload occurs.

    A passing receipt establishes consistency with a committed manifest,
    not source authenticity, live observation freshness or permission to
    turn private historical evidence into a public fixture.
    """
    try:
        root = Path(root).resolve(strict=True)
        raw = _bounded_file(root, MANIFEST, MAX_MANIFEST)
        document = _json(raw)
        require(isinstance(document, dict)
                and set(document) == {"schema", "classification", "fixtures"}
                and document["schema"] == SCHEMA
                and document["classification"] == "SYNTHETIC_ONLY",
                "fixture manifest schema/classification")
        entries = document["fixtures"]
        require(isinstance(entries, list) and 0 < len(entries) <= MAX_FIXTURES,
                "fixture inventory outside bound")
        verified = [_verify_entry(root, row) for row in entries]
        ids = [r["id"] for r in verified]
        paths = [r["path"] for r in verified]
        require(ids == sorted(set(ids)) and len(set(paths)) == len(paths),
                "duplicate or unordered fixture inventory")
        return {"schema": "taxi.cloud-fixture-verification/1", "status": "passed",
                "classification": "SYNTHETIC_ONLY",
                "manifestSHA256": hashlib.sha256(raw).hexdigest(),
                "fixtureCount": len(verified),
                "totalBytes": sum(r["sizeBytes"] for r in verified),
                "fixtures": verified, "physicalQualification": False,
                "gameInputSent": False}
    except (OSError, TraceError, ValueError, TypeError, KeyError, OverflowError) as exc:
        if isinstance(exc, FixtureLibraryError):
            raise
        raise FixtureLibraryError("fixture library refused: " + type(exc).__name__) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="optional new receipt; never overwrite")
    args = parser.parse_args(argv)
    try:
        if args.out is not None and args.out.exists():
            raise FileExistsError(args.out)
        receipt = verify_library()
        if args.out is not None:
            with args.out.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
                stream.write("\n")
        print(json.dumps(receipt, sort_keys=True, allow_nan=False))
        return 0
    except (FixtureLibraryError, OSError) as exc:
        parser.exit(2, "Cloud fixture verification refused: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
