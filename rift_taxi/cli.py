"""Offline-only CLI for trace validation, analysis and comparison."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Sequence

from .contracts import TraceError, load_trace
from .replay import analyze, compare
from .import_rr2 import import_rr2
from .steering import preview_steering


def _write_or_print(result: dict, output: str | None) -> None:
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if output is None:
        print(encoded, end="")
        return
    target = Path(output)
    if not target.parent.is_dir():
        raise TraceError("output parent directory does not exist")
    # Never overwrite existing measurement evidence.
    try:
        with target.open("x", encoding="utf-8", newline="\n") as writer:
            writer.write(encoded)
    except FileExistsError as error:
        raise TraceError("refusing to overwrite existing report") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rift-taxi",
        description="RIFT Taxi offline replay; no live client access or game input",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    replay = commands.add_parser("replay", help="analyze a versioned offline motion trace")
    replay.add_argument("trace", help="local taxi.motion-trace/1 JSON")
    replay.add_argument("--out", help="write JSON to a NEW file (never overwrite)")
    cmp = commands.add_parser("compare", help="compare the same route's two offline traces")
    cmp.add_argument("left", help="baseline trace path")
    cmp.add_argument("right", help="candidate trace path")
    cmp.add_argument("--out", help="write JSON to a NEW file (never overwrite)")
    imp = commands.add_parser("import-rr2", help="bundle an ORIGINAL RR2 movement receipt for offline replay")
    imp.add_argument("source", help="original single-record RR2 JSONL file")
    imp.add_argument("--source-commit", required=True, help="40-digit observed RR2 Git revision (not capture authentication)")
    imp.add_argument("--out-dir", required=True, help="new output directory for source, manifest and normalized trace")
    steering = commands.add_parser("preview-steering", help="inspect pure-pursuit intent on a synthetic route; never sends input")
    steering.add_argument("trace", help="synthetic-local-xyz trace JSON")
    steering.add_argument("--lookahead", type=float, default=2.0)
    steering.add_argument("--deadband-degrees", type=float, default=4.0)
    steering.add_argument("--out", help="write report to a NEW file")
    commands.add_parser("doctor", help="offline environment check; never selects RIFT")
    args = parser.parse_args(argv)
    try:
        if args.command == "replay":
            _write_or_print(analyze(load_trace(args.trace)), args.out)
        elif args.command == "compare":
            left, right = load_trace(args.left), load_trace(args.right)
            _write_or_print(compare(left, right), args.out)
        elif args.command == "import-rr2":
            _write_or_print(import_rr2(args.source, args.out_dir, source_commit=args.source_commit), None)
        elif args.command == "preview-steering":
            _write_or_print(preview_steering(load_trace(args.trace), lookahead=args.lookahead,
                                            deadband_degrees=args.deadband_degrees), args.out)
        else:
            _write_or_print({
                "schema": "taxi.doctor/1",
                "status": "offline-replay-ready",
                "python": sys.version.split()[0],
                "runtime": "stdlib",
                "gameInputEnabled": False,
                "nativeReaderImplemented": False,
                "siblingRepositoryRequired": False,
            }, None)
        return 0
    except (TraceError, ValueError, OSError) as error:
        print(f"rift-taxi: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
