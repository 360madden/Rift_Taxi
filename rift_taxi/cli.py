"""RIFT Taxi CLI: offline replay and explicit read-only native candidate capture."""

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
from .native_capture import capture_native_candidate, CandidateCaptureRefused
from .native_burst import capture_native_burst
from .native_candidate import NativeCandidateUnavailable
from .native_memory import NativeReadUnavailable
from .win32_identity import IdentityUnavailable


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
        description="RIFT Taxi offline replay and explicit read-only candidate observation; no game input",
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
    candidate = commands.add_parser("inspect-native-candidate",
        help="one explicit pinned read-only RIFT candidate capture; NEVER sends input")
    candidate.add_argument("--pid", required=True, type=int)
    candidate.add_argument("--start-ticks", required=True, type=int,
        help="exact process creation epoch in .NET UTC ticks")
    candidate.add_argument("--exe-path", required=True, help="absolute expected executable path")
    candidate.add_argument("--sha256", required=True, help="trusted on-disk executable SHA-256")
    candidate.add_argument("--hwnd", required=True, type=lambda raw: int(raw, 0),
        help="exact window handle (decimal or 0x hex)")
    candidate.add_argument("--host", required=True, help="expected Windows machine name")
    candidate.add_argument("--out", required=True, help="NEW local JSON report; never overwrite")
    candidate.add_argument("--max-capture-seconds", type=float, default=3.0)
    burst = commands.add_parser("inspect-native-burst",
        help="2..8 fully pinned read-only candidate captures for manual change analysis; no input")
    burst.add_argument("--pid", required=True, type=int)
    burst.add_argument("--start-ticks", required=True, type=int)
    burst.add_argument("--exe-path", required=True)
    burst.add_argument("--sha256", required=True)
    burst.add_argument("--hwnd", required=True, type=lambda raw: int(raw, 0))
    burst.add_argument("--host", required=True)
    burst.add_argument("--samples", type=int, default=4)
    burst.add_argument("--interval-ms", type=int, default=250)
    burst.add_argument("--max-total-seconds", type=float, default=30.0)
    burst.add_argument("--out", required=True, help="new JSON file; no overwrite")
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
        elif args.command == "inspect-native-candidate":
            report = capture_native_candidate(
                pid=args.pid, start_utc_ticks=args.start_ticks,
                executable_path=args.exe_path, executable_sha256=args.sha256,
                window_handle=args.hwnd, host=args.host,
                max_capture_s=args.max_capture_seconds,
            )
            _write_or_print(report, args.out)
        elif args.command == "inspect-native-burst":
            report = capture_native_burst(
                pid=args.pid, start_utc_ticks=args.start_ticks,
                executable_path=args.exe_path, executable_sha256=args.sha256,
                window_handle=args.hwnd, host=args.host, samples=args.samples,
                interval_ms=args.interval_ms, max_total_s=args.max_total_seconds,
            )
            _write_or_print(report, args.out)
        else:
            _write_or_print({
                "schema": "taxi.doctor/1",
                "status": "offline-replay-ready",
                "python": sys.version.split()[0],
                "runtime": "stdlib",
                "gameInputEnabled": False,
                "nativeReaderImplemented": False,
                "nativeCandidateCaptureAvailable": True,
                "nativeCandidateBurstAvailable": True,
                "nativeCandidateQualifiedForMovement": False,
                "siblingRepositoryRequired": False,
            }, None)
        return 0
    except (TraceError, ValueError, OSError, IdentityUnavailable,
            NativeReadUnavailable, NativeCandidateUnavailable, CandidateCaptureRefused) as error:
        print(f"rift-taxi: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
