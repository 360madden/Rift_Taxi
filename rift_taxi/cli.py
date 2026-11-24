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
from .simulation import simulate_route
from .simulation_stress import stress_route, compare_speed_policies
from .simulation_holdout import evaluate_holdout
from .simulation_holdout_v2 import evaluate_holdout_v2
from .simulation_ordered_comparison import compare_ordered_corners
from .simulation_delay_study import evaluate_delay_study
from .simulation_settling import evaluate_settling_study
from .simulation_recovery_audit import audit_recovery_efficiency
from .motion_timing import analyze_motion_timing
from .forward_bearing import (
    analyze_forward_bearing, compare_two_forward_bearings, ForwardBearingError,
)
from .zone_correlation import compare_native_zone_sources, ZoneCorrelationRefused
from .native_series import observe_native_series, SeriesUnavailable
from .release_supervisor import ReleaseLeasePin, SupervisorUnavailable
from .turn_probe import run_turn_probe, run_forward_probe, TurnProbeRefused
from .camera_probe import run_camera_orbit_probe, CameraProbeRefused
from .native_capture import capture_native_candidate, CandidateCaptureRefused
from .native_burst import capture_native_burst
from .native_pair import compare_native_candidates, NativePairError
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
        description="RIFT Taxi offline replay, read-only native observation and opt-in bounded calibration",
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
    sim = commands.add_parser("simulate-route", help="offline ideal synthetic feedback experiment; no game input")
    sim.add_argument("trace", help="synthetic-local-xyz trace; only route and initial pose used")
    sim.add_argument("--dt", type=float, default=.05)
    sim.add_argument("--speed", type=float, default=3.)
    sim.add_argument("--lookahead", type=float, default=1.5)
    sim.add_argument("--max-yaw-rate", type=float, default=180.)
    sim.add_argument("--max-seconds", type=float, default=30.)
    sim.add_argument("--max-cross-track", type=float, default=2.)
    sim.add_argument("--speed-policy", choices=("fixed", "turn-limited", "turn-limited-rejoin", "turn-limited-ordered"), default="fixed")
    sim.add_argument("--out", help="write synthetic report to a NEW file")
    stress = commands.add_parser("stress-route", help="offline fixed 180-case synthetic sensitivity benchmark")
    stress.add_argument("trace", help="synthetic-local-xyz trace")
    stress.add_argument("--speed-policy", choices=("fixed", "turn-limited", "turn-limited-rejoin", "turn-limited-ordered"), default="fixed")
    stress.add_argument("--out", help="write benchmark report to a NEW file")
    policy = commands.add_parser("compare-speed-policies", help="offline paired comparison on the unchanged 180-case grid")
    policy.add_argument("trace", help="synthetic-local-xyz trace")
    policy.add_argument("--out", help="write comparison to a NEW file")
    # Fixed synthetic holdout is intentionally self-contained; it accepts
    # no live client identity, map import or actuator parameters. Reports
    # use the same new-file-only output path as the other offline commands.
    holdout = commands.add_parser("evaluate-holdout", help="offline paired synthetic route-shape holdout v1")
    holdout.add_argument("--include-rejoin", action="store_true", help="compare the experimental third policy on v1 scenarios")
    holdout.add_argument("--out", help="write holdout report to a NEW file")
    # Diagnostic-only: use the unchanged synthetic recovery variant and
    # partition its generated time steps, without changing its duty metric.
    recovery = commands.add_parser("audit-recovery", help="offline synthetic recovery phase timing on v1 cases")
    recovery.add_argument("--out", help="write phase audit to a NEW file")
    # Separate command keeps the original v1 report byte-reproducible.
    # All route geometry and profiles are authored, synthetic and frozen.
    holdout_v2 = commands.add_parser("evaluate-holdout-v2", help="offline new 108-case paired synthetic validation")
    holdout_v2.add_argument("--out", help="write v2 comparison to a NEW file")
    # Compare the experimental fourth policy without changing either
    # original holdout command or promoting any game navigation default.
    ordered = commands.add_parser("compare-ordered-corners", help="offline paired comparison on frozen v1/v2 routes")
    ordered.add_argument("--out", help="write ordered corner comparison to a NEW file")
    # Synthetic-only delay experiment; never connects to an actuator.
    delay = commands.add_parser("study-synthetic-delay", help="offline whole-step command delay sensitivity")
    delay.add_argument("--out", help="write synthetic delay study to a NEW file")
    # Audit post-arrival FIFO drain separately from the historical first
    # arrival study. No live actuator or movement is involved.
    settling = commands.add_parser("study-synthetic-settling", help="offline terminal FIFO drain and ideal settling")
    settling.add_argument("--out", help="write synthetic settling report to a NEW file")
    timing = commands.add_parser("measure-motion-timing",
        help="offline only: source-aware pose/key temporal analysis, never calibrated game response")
    timing.add_argument("trace", help="source-hashed motion trace JSON")
    timing.add_argument("--movement-threshold-xz", type=float, default=.02)
    timing.add_argument("--max-interval-seconds", type=float, default=.25)
    timing.add_argument("--response-horizon-seconds", type=float, default=1.0)
    timing.add_argument("--coast-window-seconds", type=float, default=.5)
    timing.add_argument("--out", help="write report to a NEW file; never overwrite")
    heading = commands.add_parser("analyze-forward-bearing",
        help="OFFLINE: validate source-hashed physical W/release receipts and compare native heading candidates")
    heading.add_argument("--report", required=True, help="original real bounded W-only JSON")
    heading.add_argument("--report-sha256", required=True, help="trusted original W report SHA-256")
    heading.add_argument("--release-audit", required=True, help="original W child release JSONL")
    heading.add_argument("--release-sha256", required=True, help="trusted original child audit SHA-256")
    heading.add_argument("--out", help="write candidate-only JSON to NEW file; never overwrite")
    two = commands.add_parser("compare-two-forward-bearings",
        help="OFFLINE: compare two original physical W pulses/child ledgers at distinct headings")
    two.add_argument("--first-report", required=True)
    two.add_argument("--first-report-sha256", required=True)
    two.add_argument("--first-release-audit", required=True)
    two.add_argument("--first-release-sha256", required=True)
    two.add_argument("--second-report", required=True)
    two.add_argument("--second-report-sha256", required=True)
    two.add_argument("--second-release-audit", required=True)
    two.add_argument("--second-release-sha256", required=True)
    two.add_argument("--out", help="write candidate-only comparison to NEW JSON file")
    native_zone = commands.add_parser("correlate-zone-candidates",
        help="OFFLINE: compare source-hashed Taxi and RR2 native zone candidates; no game access")
    native_zone.add_argument("--taxi-report", required=True)
    native_zone.add_argument("--taxi-sha256", required=True)
    native_zone.add_argument("--rr2-report", required=True)
    native_zone.add_argument("--rr2-sha256", required=True)
    native_zone.add_argument("--out", help="write candidate-only JSON to NEW file")
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
    candidate.add_argument("--include-zone-key-candidate", action="store_true",
        help="read current same-owner raw zone key; not public zone ID/world instance")
    candidate.add_argument("--include-actor-translation-candidate", action="store_true",
        help="same-owner secondary XYZ + actor offsets/render world translation; not live pose proof")
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
    series = commands.add_parser("observe-native-series",
        help="one read-only pinned process handle, 3..128 owner-checked samples; no input")
    series.add_argument("--pid", required=True, type=int)
    series.add_argument("--start-ticks", required=True, type=int)
    series.add_argument("--exe-path", required=True)
    series.add_argument("--sha256", required=True)
    series.add_argument("--hwnd", required=True, type=lambda raw: int(raw, 0))
    series.add_argument("--host", required=True)
    series.add_argument("--samples", type=int, default=16)
    series.add_argument("--interval-ms", type=int, default=150)
    series.add_argument("--max-total-seconds", type=float, default=20.0)
    series.add_argument("--start-delay-seconds", type=float, default=0.0)
    series.add_argument("--include-matrix-candidate", action="store_true")
    series.add_argument("--include-refresh-guard-candidate", action="store_true")
    series.add_argument("--include-actor-translation-candidate", action="store_true")
    series.add_argument("--include-zone-key-candidate", action="store_true",
        help="read same-owner raw key at each sample; fail closed on changes")
    series.add_argument("--observe-manual-keys", action="store_true",
        help="read-only W/A/D high-bit polling while RIFT is foreground; no input sent")
    series.add_argument("--out", required=True, help="new JSON report; never overwrite")
    turn = commands.add_parser("probe-ad-turn",
        help="ONE bounded A or D calibration (not navigation); dry-run unless explicitly physical")
    turn.add_argument("--pid", required=True, type=int)
    turn.add_argument("--start-ticks", required=True, type=int)
    turn.add_argument("--exe-path", required=True)
    turn.add_argument("--sha256", required=True)
    turn.add_argument("--hwnd", required=True, type=lambda raw: int(raw, 0))
    turn.add_argument("--host", required=True)
    turn.add_argument("--owner-key", required=True, type=int,
        help="exact current self owner-key decimal, independently observed")
    turn.add_argument("--key", choices=("A", "D"), required=True)
    turn.add_argument("--hold-ms", type=int, default=100,
        help="60..160 ms single A/D edge, never W")
    turn.add_argument("--audit", required=True, help="new separate-process release audit JSONL")
    turn.add_argument("--out", required=True, help="NEW probe report JSON")
    turn.add_argument("--scene-image-sha256",
        help="SHA-256 of freshly reviewed actual game-screen image")
    turn.add_argument("--execute-physical", action="store_true",
        help="Actually send one A or D DOWN/UP; otherwise dry-run only")
    forward = commands.add_parser("probe-w-forward",
        help="ONE bounded W-only forward calibration; dry-run unless explicitly physical")
    forward.add_argument("--pid", required=True, type=int)
    forward.add_argument("--start-ticks", required=True, type=int)
    forward.add_argument("--exe-path", required=True)
    forward.add_argument("--sha256", required=True)
    forward.add_argument("--hwnd", required=True, type=lambda raw: int(raw, 0))
    forward.add_argument("--host", required=True)
    forward.add_argument("--owner-key", required=True, type=int,
        help="exact current self owner-key decimal, independently observed")
    forward.add_argument("--hold-ms", type=int, default=100,
        help="60..160 ms single W pulse; separate post-release readback")
    forward.add_argument("--audit", required=True,
        help="NEW external release child audit JSONL")
    forward.add_argument("--out", required=True, help="NEW forward probe JSON report")
    forward.add_argument("--scene-image-sha256",
        help="SHA-256 of independently reviewed current clear-ground game scene")
    forward.add_argument("--execute-physical", action="store_true",
        help="Actually send one W DOWN/UP; otherwise dry-run only")
    camera = commands.add_parser("probe-camera-orbit",
        help="ONE bounded left-mouse camera-orbit negative control; dry-run by default")
    camera.add_argument("--pid", required=True, type=int)
    camera.add_argument("--start-ticks", required=True, type=int)
    camera.add_argument("--exe-path", required=True)
    camera.add_argument("--sha256", required=True)
    camera.add_argument("--hwnd", required=True, type=lambda raw: int(raw, 0))
    camera.add_argument("--host", required=True)
    camera.add_argument("--owner-key", required=True, type=int)
    camera.add_argument("--drag-px", type=int, default=60,
        help="30..90 pixel bounded horizontal relative camera orbit")
    camera.add_argument("--hold-ms", type=int, default=100,
        help="80..160 ms one left-mouse-only gesture")
    camera.add_argument("--cursor-x-fraction", type=float, required=True,
        help="reviewed clear-ground screen X fraction, 0.2..0.7")
    camera.add_argument("--cursor-y-fraction", type=float, required=True,
        help="reviewed clear-ground screen Y fraction, 0.25..0.65")
    camera.add_argument("--scene-image-sha256",
        help="SHA-256 of freshly reviewed real game scene")
    camera.add_argument("--audit", required=True, help="NEW release-only child JSONL audit")
    camera.add_argument("--out", required=True, help="NEW candidate-only orbit JSON")
    camera.add_argument("--execute-physical", action="store_true",
        help="Actually inject one left-mouse drag with independent mouse UP; default is dry-run")
    pair = commands.add_parser("compare-native-candidates",
        help="offline only: SHA-pinned same-process/owner XYZ/yaw/matrix/actor comparison")
    pair.add_argument("--before", required=True, help="original first one-shot JSON receipt")
    pair.add_argument("--after", required=True, help="original later one-shot JSON receipt")
    pair.add_argument("--out", help="write JSON to a NEW file; never overwrite")
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
        elif args.command == "simulate-route":
            _write_or_print(simulate_route(
                load_trace(args.trace), dt=args.dt, speed=args.speed,
                lookahead=args.lookahead, max_yaw_rate=args.max_yaw_rate,
                max_seconds=args.max_seconds, max_cross_track=args.max_cross_track,
                speed_policy=args.speed_policy,
            ), args.out)
        elif args.command == "stress-route":
            _write_or_print(stress_route(load_trace(args.trace), speed_policy=args.speed_policy), args.out)
        elif args.command == "compare-speed-policies":
            _write_or_print(compare_speed_policies(load_trace(args.trace)), args.out)
        elif args.command == "evaluate-holdout":
            _write_or_print(evaluate_holdout(include_rejoin=args.include_rejoin), args.out)
        elif args.command == "audit-recovery":
            _write_or_print(audit_recovery_efficiency(), args.out)
        elif args.command == "evaluate-holdout-v2":
            _write_or_print(evaluate_holdout_v2(), args.out)
        elif args.command == "compare-ordered-corners":
            _write_or_print(compare_ordered_corners(), args.out)
        elif args.command == "study-synthetic-delay":
            _write_or_print(evaluate_delay_study(), args.out)
        elif args.command == "study-synthetic-settling":
            _write_or_print(evaluate_settling_study(), args.out)
        elif args.command == "measure-motion-timing":
            report = analyze_motion_timing(
                load_trace(args.trace),
                movement_threshold_xz=args.movement_threshold_xz,
                max_interval_s=args.max_interval_seconds,
                response_horizon_s=args.response_horizon_seconds,
                coast_window_s=args.coast_window_seconds,
            )
            _write_or_print(report, args.out)
        elif args.command == "analyze-forward-bearing":
            if args.out is not None:
                _capture_preflight(args.out, 0.)
            _write_or_print(analyze_forward_bearing(
                report=args.report, report_sha256=args.report_sha256,
                release_audit=args.release_audit,
                release_audit_sha256=args.release_sha256,
            ), args.out)
        elif args.command == "compare-two-forward-bearings":
            if args.out is not None:
                _capture_preflight(args.out, 0.)
            _write_or_print(compare_two_forward_bearings(
                first_report=args.first_report,
                first_report_sha256=args.first_report_sha256,
                first_release_audit=args.first_release_audit,
                first_release_audit_sha256=args.first_release_sha256,
                second_report=args.second_report,
                second_report_sha256=args.second_report_sha256,
                second_release_audit=args.second_release_audit,
                second_release_audit_sha256=args.second_release_sha256,
            ), args.out)
        elif args.command == "correlate-zone-candidates":
            if args.out is not None:
                _capture_preflight(args.out, 0.)
            _write_or_print(compare_native_zone_sources(
                taxi_report=args.taxi_report, taxi_sha256=args.taxi_sha256,
                rr2_report=args.rr2_report, rr2_sha256=args.rr2_sha256,
            ), args.out)
        elif args.command == "inspect-native-candidate":
            _capture_preflight(args.out, args.start_delay_seconds)
            report = capture_native_candidate(
                pid=args.pid, start_utc_ticks=args.start_ticks,
                executable_path=args.exe_path, executable_sha256=args.sha256,
                window_handle=args.hwnd, host=args.host,
                max_capture_s=args.max_capture_seconds,
                include_matrix_candidate=args.include_matrix_candidate,
                include_refresh_guard_candidate=args.include_refresh_guard_candidate,
                include_actor_translation_candidate=args.include_actor_translation_candidate,
                include_zone_key_candidate=args.include_zone_key_candidate,
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
        elif args.command == "observe-native-series":
            _capture_preflight(args.out, args.start_delay_seconds)
            report = observe_native_series(
                pid=args.pid, start_utc_ticks=args.start_ticks,
                executable_path=args.exe_path, executable_sha256=args.sha256,
                window_handle=args.hwnd, host=args.host,
                samples=args.samples, interval_ms=args.interval_ms,
                max_total_s=args.max_total_seconds,
                include_matrix_candidate=args.include_matrix_candidate,
                include_refresh_guard_candidate=args.include_refresh_guard_candidate,
                include_actor_translation_candidate=args.include_actor_translation_candidate,
                include_zone_key_candidate=args.include_zone_key_candidate,
                observe_manual_keys=args.observe_manual_keys,
            )
            _write_or_print(report, args.out)
        elif args.command == "probe-ad-turn":
            _capture_preflight(args.out, 0.)
            report = run_turn_probe(
                pin=ReleaseLeasePin(
                    args.host, args.pid, args.start_ticks, args.hwnd,
                    args.exe_path, args.sha256,
                ),
                expected_owner_key=args.owner_key, key=args.key,
                hold_ms=args.hold_ms, audit_path=args.audit,
                scene_image_sha256=args.scene_image_sha256,
                dry_run=not args.execute_physical,
            )
            _write_or_print(report, args.out)
        elif args.command == "probe-w-forward":
            _capture_preflight(args.out, 0.)
            report = run_forward_probe(
                pin=ReleaseLeasePin(
                    args.host, args.pid, args.start_ticks, args.hwnd,
                    args.exe_path, args.sha256,
                ),
                expected_owner_key=args.owner_key,
                hold_ms=args.hold_ms, audit_path=args.audit,
                scene_image_sha256=args.scene_image_sha256,
                dry_run=not args.execute_physical,
            )
            _write_or_print(report, args.out)
        elif args.command == "probe-camera-orbit":
            _capture_preflight(args.out, 0.)
            report = run_camera_orbit_probe(
                pin=ReleaseLeasePin(
                    args.host, args.pid, args.start_ticks, args.hwnd,
                    args.exe_path, args.sha256,
                ),
                expected_owner_key=args.owner_key,
                horizontal_drag_px=args.drag_px,
                hold_ms=args.hold_ms,
                cursor_x_fraction=args.cursor_x_fraction,
                cursor_y_fraction=args.cursor_y_fraction,
                audit_path=args.audit,
                scene_image_sha256=args.scene_image_sha256,
                dry_run=not args.execute_physical,
            )
            _write_or_print(report, args.out)
        elif args.command == "compare-native-candidates":
            report = compare_native_candidates(args.before, args.after)
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
                # Legacy flag means qualified live pose provider, not raw candidates.
                "nativeReaderImplemented": False,
                "nativeReadOnlyCandidateReaderImplemented": True,
                "nativeCandidateCaptureAvailable": True,
                "nativeCandidateBurstAvailable": True,
                "nativeCandidateSeriesAvailable": True,
                "rawSelfZoneKeyCandidateAvailable": True,
                "publicZoneIdAndWorldInstanceQualified": False,
                "boundedADTurnCalibrationAvailable": True,
                "boundedWForwardCalibrationAvailable": True,
                "boundedCameraOrbitNegativeControlAvailable": True,
                "readOnlyManualKeyObservationAvailable": True,
                "offlineFacingPhaseComparisonAvailable": True,
                "offlineNativeCandidatePairComparisonAvailable": True,
                "offlineMotionTimingAvailable": True,
                "offlineSyntheticFeedbackAvailable": True,
                "offlineSyntheticStressBenchmarkAvailable": True,
                "offlineSyntheticSpeedPolicyComparisonAvailable": True,
                "offlineSyntheticRouteHoldoutAvailable": True,
                "offlineSyntheticRecoveryPhaseAuditAvailable": True,
                "offlineSyntheticRouteHoldoutV2Available": True,
                "offlineSyntheticOrderedCornerComparisonAvailable": True,
                "offlineSyntheticDelayStudyAvailable": True,
                "offlineSyntheticSettlingStudyAvailable": True,
                "offlinePhysicalForwardBearingComparisonAvailable": True,
                "offlineTwoHeadingForwardComparisonAvailable": True,
                "offlineRR2NativeZoneCorrelationAvailable": True,
                "nativeZoneCandidateQualifiedForPublicApi": False,
                "nativeCandidateQualifiedForMovement": False,
                "siblingRepositoryRequired": False,
            }, None)
        return 0
    except (TraceError, ValueError, OSError, IdentityUnavailable,
            NativeReadUnavailable, NativeCandidateUnavailable, CandidateCaptureRefused,
            FacingSignatureError, NativePairError, SupervisorUnavailable,
            TurnProbeRefused, CameraProbeRefused, ForwardBearingError, ZoneCorrelationRefused) as error:
        print(f"rift-taxi: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
