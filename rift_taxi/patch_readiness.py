"""Development-only patch evidence gate for RIFT Taxi.

Consumes explicit, saved Update Helper game-file manifests. It never scans the
game installation, opens the game process, sends input, changes layouts, imports
a sibling repository or authorizes production navigation. The Update Helper owns
capture; this module independently checks the evidence at Taxi's boundary.

Use --before alone for a pinned pre-patch baseline. After the updater settles,
supply TWO separately captured after manifests. All comparisons are content-only
(path, byte length, SHA-256), not file timestamps or claims about live behavior.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import sys

SCHEMA = "update-helper.game-files.v1"
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
SHA = re.compile(r"[0-9a-f]{64}\Z")


def _unique_object(pairs):
    """Reject ambiguous JSON instead of silently accepting a duplicate key."""
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def _reject_constant(value):
    raise ValueError(f"non-finite JSON number: {value}")


def _time(value):
    """Return an offset-aware datetime; reject unqualified local clock values."""
    if not isinstance(value, str):
        raise ValueError("capture timestamp must be a string")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("capture timestamp lacks offset")
    return parsed


def read_manifest(path, expected_host, phase):
    """Read one immutable evidence file and validate its complete file inventory.

    Return the original-byte SHA-256, normalized Windows installation identity,
    capture interval and a case-insensitive path -> (size, SHA-256) map. This is
    validation of saved evidence, not a fresh hash of any installed game file.
    """
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("manifest exceeds bounded evidence size")
    doc = json.loads(raw, object_pairs_hook=_unique_object,
                     parse_constant=_reject_constant)
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ValueError("unsupported manifest schema")
    if doc.get("complete") is not True or doc.get("phase") != phase:
        raise ValueError(f"expected a complete {phase} capture")
    if doc.get("host") != expected_host:
        raise ValueError("manifest host mismatch")
    root = doc.get("root")
    if not isinstance(root, str) or not PureWindowsPath(root).is_absolute():
        raise ValueError("invalid game installation root")
    started, finished = _time(doc.get("started_utc")), _time(doc.get("finished_utc"))
    if started > finished:
        raise ValueError("capture interval is reversed")
    files = doc.get("files")
    if not isinstance(files, list):
        raise ValueError("missing file inventory")
    index = {}
    for row in files:
        if not isinstance(row, dict):
            raise ValueError("invalid file row")
        rel, size, sha = row.get("path"), row.get("size"), row.get("sha256")
        # Update Helper emits POSIX-relative names, even on Windows. Refuse
        # traversal and ambiguous path spellings before comparing inventories.
        if (not isinstance(rel, str) or "\\" in rel or ":" in rel
                or any(part in ("", ".", "..") for part in rel.split("/"))):
            raise ValueError("invalid relative file path")
        if (type(size) is not int or size < 0 or not isinstance(sha, str)
                or not SHA.fullmatch(sha) or type(row.get("mtime_ns")) is not int):
            raise ValueError(f"invalid file evidence: {rel}")
        key = rel.casefold()
        if key in index:
            raise ValueError(f"duplicate file path: {rel}")
        index[key] = (size, sha)
    if ("rift_x64.exe" not in index or type(doc.get("file_count")) is not int
            or doc["file_count"] != len(index) or type(doc.get("bytes")) is not int
            or doc["bytes"] != sum(size for size, _ in index.values())):
        raise ValueError("manifest totals or executable identity invalid")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "root": str(PureWindowsPath(root)).casefold(),
        "started": started, "finished": finished, "index": index,
    }


def assess(before, expected_host, expected_before_sha, after_a=None, after_b=None):
    """Assess a saved baseline or stable pair of post-update snapshots.

    A clean result means only that the supplied snapshots are internally
    consistent; it does NOT certify the live client. A changed executable,
    changed other files, or even unchanged files all require fresh qualification
    before any live experiment. No outcome can turn on production input.
    """
    if not isinstance(expected_before_sha, str) or not SHA.fullmatch(expected_before_sha):
        raise ValueError("explicit baseline SHA-256 pin required")
    pre = read_manifest(before, expected_host, "before")
    if pre["sha256"] != expected_before_sha:
        raise ValueError("baseline byte hash mismatch")
    result = {
        "schema": "taxi.patch-readiness/1", "host": expected_host,
        "baseline_manifest_sha256": pre["sha256"],
        "baseline_executable_sha256": pre["index"]["rift_x64.exe"][1],
        "baseline_file_count": len(pre["index"]),
        "production_input_authorized": False,
        "fresh_live_qualification_required": True,
        "status": "baseline-only",
    }
    if after_a is None and after_b is None:
        return result
    if after_a is None or after_b is None:
        raise ValueError("two separate post-patch manifests are required")
    a = read_manifest(after_a, expected_host, "after")
    b = read_manifest(after_b, expected_host, "after")
    # Equal bytes are not evidence of two independent capture intervals.
    if (a["sha256"] == b["sha256"] or a["root"] != pre["root"]
            or b["root"] != pre["root"] or a["started"] < pre["finished"]
            or b["started"] < a["finished"] or b["started"] <= a["started"]):
        raise ValueError("post captures are duplicated, overlapping or from another root")
    if a["index"] != b["index"]:
        raise ValueError("post captures disagree; wait for updater to settle and recapture")

    # Only compare immutable manifests; Update Helper remains the sole scanner.
    left, right = pre["index"], b["index"]
    added = sorted(right.keys() - left.keys())
    removed = sorted(left.keys() - right.keys())
    modified = sorted(key for key in left.keys() & right.keys() if left[key] != right[key])
    exe_changed = left["rift_x64.exe"] != right["rift_x64.exe"]
    result.update({
        "after_manifest_sha256": [a["sha256"], b["sha256"]],
        "after_executable_sha256": right["rift_x64.exe"][1],
        "added": added, "removed": removed, "modified": modified,
        "executable_changed": exe_changed,
        "status": ("executable-changed" if exe_changed else
                   "other-files-changed" if added or removed or modified else
                   "no-content-change"),
    })
    return result


def main(argv=None):
    """Print a JSON receipt; exit 2 on missing, corrupt or unstable evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--expected-before-sha", required=True)
    parser.add_argument("--after-a", type=Path)
    parser.add_argument("--after-b", type=Path)
    args = parser.parse_args(argv)
    try:
        result = assess(args.before, args.expected_host, args.expected_before_sha,
                        args.after_a, args.after_b)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"PATCH EVIDENCE BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
