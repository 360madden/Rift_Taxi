"""RIFT Taxi CLI: offline replay and explicit read-only native candidate capture."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time
from typing import Sequence

from .contracts import TraceError, load_trace
from .replay import analyze, compare
from .import_rr2 import import_rr2
from .steering import preview_steering
from .native_capture import capture_native_candidate, CandidateCaptureRefused
from .native_burst import capture_native_burst
from .facing_signature import compare_facing_phases, FacingSignatureError
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


def _capture_preflight(output: str, delay_seconds: float) -> None:
    """Reject unusable output/delay before touching a live target."""
    target = Path(output)
    if target.exists() or target.is_symlink():
        raise TraceError("refusing to overwrite existing report")
    if not target.parent.is_dir():
        raise TraceError("output parent directory does not exist")
    if (isinstance(delay_seconds, bool) or not isinstance(delay_seconds, (int, float))
            or not math.isfinite(delay_seconds) or not 0 <= delay_seconds <= 15):
        raise ValueError("start delay must be finite and within 0..15 seconds")
    if delay_seconds:
        time.sleep(delay_seconds)


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
    candidate.add_argument("--start-delay-seconds", type=float, default=0.0,
        help="optional 0..15 sec to switch foreground back to RIFT before reading")
    candidate.add_argument("--include-matrix-candidate", action="store_true",
        help="also capture same-owner position-secondary and actor matrix raw bits; never qualified heading")
    candidate.add_argument("--include-refresh-guard-candidate", action="store_true",
        help="co-sampled cache refresh guard bytes; no writer-execution/freshness proof")
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
    burst.add_argument("--start-delay-seconds", type=float, default=0.0,
        help="optional 0..15 sec to restore RIFT foreground before burst")
    burst.add_argument("--include-matrix-candidate", action="store_true",
        help="also compare exact-build actor/position matrix raw bits in each sample; heading unverified")
    burst.add_argument("--include-refresh-guard-candidate", action="store_true",
        help="also compare sampled cached XYZ refresh guard bytes; not writer/freshness proof")
    burst.add_argument("--out", required=True, help="new JSON file; no overwrite")
    phases = commands.add_parser("compare-facing-phases",
        help="offline only: compare five manually labeled matrix-enabled candidate bursts")
    for phase in ("baseline", "camera-only", "turn-left", "turn-right", "forward"):
        phases.add_argument("--" + phase, required=True,
            help="local matrix-enabled candidate burst JSON (phase label not action proof)")
    phases.add_argument("--out", help="save JSON to NEW file; never overwrite")
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
            _capture_preflight(args.out, args.start_delay_seconds)
            report = capture_native_candidate(
                pid=args.pid, start_utc_ticks=args.start_ticks,
                executable_path=args.exe_path, executable_sha256=args.sha256,
                window_handle=args.hwnd, host=args.host,
                max_capture_s=args.max_capture_seconds,
                include_matrix_candidate=args.include_matrix_candidate,
                include_refresh_guard_candidate=args.include_refresh_guard_candidate,
            )
            _write_or_print(report, args.out)
        elif args.command == "inspect-native-burst":
            _capture_preflight(args.out, args.start_delay_seconds)
            report = capture_native_burst(
                pid=args.pid, start_utc_ticks=args.start_ticks,
                executable_path=args.exe_path, executable_sha256=args.sha256,
                window_handle=args.hwnd, host=args.host, samples=args.samples,
                interval_ms=args.interval_ms, max_total_s=args.max_total_seconds,
                include_matrix_candidate=args.include_matrix_candidate,
                include_refresh_guard_candidate=args.include_refresh_guard_candidate,
            )
            _write_or_print(report, args.out)
        elif args.command == "compare-facing-phases":
            report = compare_facing_phases(
                baseline=args.baseline, camera_only=args.camera_only,
                turn_left=args.turn_left, turn_right=args.turn_right,
                forward=args.forward,
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
                "offlineFacingPhaseComparisonAvailable": True,
                "nativeCandidateQualifiedForMovement": False,
                "siblingRepositoryRequired": False,
            }, None)
        return 0
    except (TraceError, ValueError, OSError, IdentityUnavailable,
            NativeReadUnavailable, NativeCandidateUnavailable, CandidateCaptureRefused,
            FacingSignatureError) as error:
        print(f"rift-taxi: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
