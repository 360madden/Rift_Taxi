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
from bisect import bisect_left
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
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


# A manifest describes ordinary Windows files, not Win32 aliases or devices.
# This includes superscript digits which Windows also recognizes in COM/LPT
# device names. Reject rather than normalize away ambiguous evidence.
_RESERVED_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"}
    | {prefix + digit for prefix in ("COM", "LPT") for digit in "123456789¹²³"}
)


def _valid_component(part):
    """Recognize unambiguous ordinary Win32 path components.

    Trailing dots/spaces, device names (even with extensions), controls,
    surrogates and forbidden punctuation cannot represent distinct ordinary
    files in the inventory. Keep the check lexical: never open game paths.
    """
    return (
        bool(part)
        and part not in (".", "..")
        and not part.endswith((".", " "))
        and not any(ch in '<>:"/\\|?*' or ord(ch) < 32
                    or 0xD800 <= ord(ch) <= 0xDFFF for ch in part)
        and part.split(".", 1)[0].rstrip(" ").upper() not in _RESERVED_DEVICE_NAMES
    )


def _root_key(value):
    """Require the resolved, drive-qualified local Windows root the helper emits.

    Device namespaces, UNC roots, dot segments and alternate spellings are
    deliberately outside this local-install evidence contract. Do not silently
    normalize an invalid root into a different installation identity.
    """
    if not isinstance(value, str):
        raise ValueError("invalid game installation root")
    root = PureWindowsPath(value)
    if (not root.is_absolute() or not re.fullmatch(r"[A-Za-z]:", root.drive)
            or str(root) != value or not all(_valid_component(p) for p in root.parts[1:])):
        raise ValueError("invalid canonical local game installation root")
    return value.casefold()


def _file_stamp(info):
    """Identity and mutable metadata shared by path stat and Windows fstat.

    Windows handle creation time may differ from path creation time; do not
    compare it across those APIs. The pre/post path check also includes ctime.
    These checks detect observable races, not maliciously restored timestamps.
    """
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _path_stat(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise ValueError("manifest must be a regular non-reparse file")
    return info


def _read_saved_bytes(path):
    """Read bounded evidence once and refuse an observed edit or replacement.

    Using the same bytes for JSON decoding and SHA-256 avoids a second-read
    hash/content mismatch. Path and handle identity also let the caller refuse
    aliases/hard links offered as separate capture files.
    """
    path = Path(path)
    before = _path_stat(path)
    if before.st_size > MAX_MANIFEST_BYTES:
        raise ValueError("manifest exceeds bounded evidence size")
    with path.open("rb") as stream:
        if _file_stamp(os.fstat(stream.fileno())) != _file_stamp(before):
            raise ValueError("manifest changed while opening")
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
        if _file_stamp(os.fstat(stream.fileno())) != _file_stamp(before):
            raise ValueError("manifest changed while reading")
    after = _path_stat(path)
    if (_file_stamp(before) != _file_stamp(after)
            or before.st_ctime_ns != after.st_ctime_ns or len(raw) != before.st_size):
        raise ValueError("manifest changed while reading")
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("manifest exceeds bounded evidence size")
    return raw, (before.st_dev, before.st_ino)


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
    raw, file_identity = _read_saved_bytes(path)
    # The producer writes UTF-8, not UTF-16/32 or a different document format.
    # On older supported Python versions deep JSON can raise RecursionError.
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                         parse_constant=_reject_constant)
    except RecursionError as exc:
        raise ValueError("manifest JSON nesting exceeds decoder limits") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ValueError("unsupported manifest schema")
    if doc.get("complete") is not True or doc.get("phase") != phase:
        raise ValueError(f"expected a complete {phase} capture")
    if (not isinstance(expected_host, str) or not expected_host
            or expected_host.strip() != expected_host or doc.get("host") != expected_host):
        raise ValueError("manifest host mismatch or missing host pin")
    root = _root_key(doc.get("root"))
    started, finished = _time(doc.get("started_utc")), _time(doc.get("finished_utc"))
    if started >= finished:
        raise ValueError("capture interval must have positive duration")
    files = doc.get("files")
    if not isinstance(files, list):
        raise ValueError("missing file inventory")
    index = {}
    lengths = {}
    for row in files:
        if not isinstance(row, dict):
            raise ValueError("invalid file row")
        rel, size, sha = row.get("path"), row.get("size"), row.get("sha256")
        # Update Helper emits POSIX-relative names, even on Windows. Refuse
        # traversal and ambiguous path spellings before comparing inventories.
        if not isinstance(rel, str) or not all(_valid_component(p) for p in rel.split("/")):
            raise ValueError("invalid relative file path")
        if (type(size) is not int or size < 0 or not isinstance(sha, str)
                or not SHA.fullmatch(sha) or type(row.get("mtime_ns")) is not int):
            raise ValueError(f"invalid file evidence: {rel}")
        key = rel.casefold()
        if key in index:
            raise ValueError(f"duplicate file path: {rel}")
        if lengths.setdefault(sha, size) != size:
            raise ValueError("identical content hash has conflicting file lengths")
        index[key] = (size, sha)
    # A flat file manifest cannot contain a file as the parent directory of
    # another file. Binary search for each prefix in the sorted inventory
    # avoids walking every ancestor of an arbitrarily deep malformed path.
    keys = sorted(index)
    for key in keys:
        prefix = key + "/"
        pos = bisect_left(keys, prefix)
        if pos < len(keys) and keys[pos].startswith(prefix):
            raise ValueError(f"file-directory inventory conflict: {key}")
    if ("rift_x64.exe" not in index or index["rift_x64.exe"][0] == 0
            or type(doc.get("file_count")) is not int
            or doc["file_count"] != len(index) or type(doc.get("bytes")) is not int
            or doc["bytes"] != sum(size for size, _ in index.values())):
        raise ValueError("manifest totals or executable identity invalid")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "root": root, "file_identity": file_identity,
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
    # Even replacing a file with a different inode must not let the same
    # pathname stand for two supposedly immutable captures. The later handle
    # identity check catches hard-link and other same-file aliases.
    names = {os.path.normcase(os.path.abspath(p)) for p in (before, after_a, after_b)}
    if len(names) != 3:
        raise ValueError("post captures are duplicated by pathname")
    a = read_manifest(after_a, expected_host, "after")
    b = read_manifest(after_b, expected_host, "after")
    # Equal bytes or aliases of one underlying file cannot demonstrate two
    # separately retained captures. Distinct file identities and declared
    # intervals still do not authenticate that the scanner actually ran twice.
    if (len({pre["file_identity"], a["file_identity"], b["file_identity"]}) != 3
            or a["sha256"] == b["sha256"] or a["root"] != pre["root"]
            or b["root"] != pre["root"] or a["started"] < pre["finished"]
            or b["started"] < a["finished"] or b["started"] <= a["started"]):
        raise ValueError("post captures are duplicated, overlapping or from another root")
    if a["index"] != b["index"]:
        raise ValueError("post captures disagree; wait for updater to settle and recapture")

    # Identical SHA-256s with conflicting lengths are inconsistent content
    # evidence, not a meaningful patch change. Check across both inventories.
    # Identical bytes necessarily have identical lengths.
    left, right = pre["index"], b["index"]
    lengths = {}
    for index in (left, right):
        for size, sha in index.values():
            if lengths.setdefault(sha, size) != size:
                raise ValueError("identical content hash has conflicting file lengths")

    # Only compare immutable manifests; Update Helper remains the sole scanner.
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
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        print(f"PATCH EVIDENCE BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
