"""End-to-end offline journey demonstration using the existing synthetic plant.

The three phases are deliberately reported separately: approach, passive
FIFO drain and optional bounded terminal correction. This module neither
opens a game process nor sends operating-system input.
"""
import argparse
import json
from pathlib import Path

from .contracts import TraceError, load_trace
from .simulation import simulate_route, _bounded_number
from .simulation_integrity import verify_synthetic_trajectory
from .simulation_settling import drain_after_arrival
from .synthetic_terminal_finish import finish_after_drain


def journey(trace, *, dt=.1, speed=3., yaw_rate=115., delay_steps=0,
            approach_budget=40., terminal_budget=5., lookahead=1.5,
            approach_mode="baseline", prediction_delay_steps=None):
    """Run bounded synthetic phases; experimental approach modes are opt-in.

    Prediction modes model nonzero transport delay. The zero-delay rejoin
    mode addresses local arc progress without forecasting. All modes share
    the same observation gates, drain and correction, never live input.
    An explicit prediction_delay_steps changes only the approach estimator;
    drain and terminal correction still use the actual ideal plant delay.
    """
    if approach_mode not in ("baseline", "predict-near-goal", "predict-near-stall", "zero-delay-rejoin"):
        raise TraceError("unknown synthetic journey approach mode")
    predicting = approach_mode in ("predict-near-goal", "predict-near-stall")
    if predicting and delay_steps == 0:
        raise TraceError("predictive journey requires nonzero delay")
    terminal_budget = _bounded_number(terminal_budget, "terminal budget", .01, 30.)
    approach = simulate_route(
        trace, dt=dt, speed=speed, max_yaw_rate=yaw_rate,
        delay_steps=delay_steps, max_seconds=approach_budget,
        lookahead=lookahead, max_cross_track=2.,
        speed_policy="turn-limited-ordered",
        predict_command_application=predicting,
        prediction_rejoin_policy="near-stall" if approach_mode == "predict-near-stall" else "near-goal",
        recover_terminal_progress=approach_mode == "zero-delay-rejoin",
        prediction_delay_steps=prediction_delay_steps)
    verify_synthetic_trajectory(approach, trace)
    drain = drain_after_arrival(approach, trace)
    correction = None
    arrived = approach["metrics"]["syntheticArrival"]

    # A failed route is not eligible for terminal-only recovery. Never
    # reinterpret an approach timeout as a successful journey.
    if arrived:
        last = drain["observations"][-1]
        correction = finish_after_drain(
            xyz=last["xyz"], yaw=last["yawDegrees"], goal=trace.points[-1].xyz,
            dt=dt, speed=speed, yaw_rate=yaw_rate, delay_steps=delay_steps,
            tolerance=trace.arrival_tolerance_xz, budget=terminal_budget)

    settled = bool(correction and correction["settled"])
    # Phase times describe disjoint intervals. For an approach failure the
    # drain and correction were never executed; their costs remain zero.
    # In particular, an unfinished FIFO on failure is not a settled plant.
    metrics = approach["metrics"]
    drain_seconds = (drain["queueDrainSeconds"] +
                     drain["stationaryVerificationSeconds"]) if arrived else 0.
    drain_distance = drain["postArrivalDistanceXZ"] if arrived else 0.
    correction_seconds = correction["extraSeconds"] if correction else 0.
    correction_distance = correction["extraTravelXZ"] if correction else 0.
    total_seconds = metrics["elapsedSeconds"] + drain_seconds + correction_seconds
    # Use actual applied synthetic velocity, not requested motion. Stationary
    # witness intervals and delayed zero commands count toward elapsed time.
    drain_forward = dt * sum(
        row["appliedSpeed"] > 0. for row in drain.get("observations", [])[1:])
    correction_forward = dt * sum(
        row["appliedSpeed"] > 0. for row in correction["frames"][1:]) if correction else 0.
    forward_seconds = metrics["forwardSeconds"] + drain_forward + correction_forward
    return {
        "schema": "taxi.synthetic-journey-demo/1",
        "classification": "SYNTHETIC_ONLY",
        **({"experimentalApproachMode": approach_mode} if approach_mode != "baseline" else {}),
        "routeId": trace.route_id,
        "inputTraceSHA256": trace.trace_sha256,
        "approach": approach,
        "passiveDrain": drain,
        "terminalCorrection": correction,
        "summary": {
            "geometricArrival": arrived,
            "passiveSettled": bool(drain["settledWithinTolerance"]),
            "finalModelSettled": settled,
            "approachSeconds": metrics["elapsedSeconds"],
            "passiveDrainSeconds": drain_seconds,
            "terminalCorrectionSeconds": correction_seconds,
            "totalElapsedSeconds": total_seconds,
            "approachForwardDutyRatio": metrics["forwardDutyRatio"],
            "totalForwardDutyRatio": forward_seconds / total_seconds if total_seconds else 0.,
            "totalDistanceXZ": metrics["simulatedDistanceXZ"] + drain_distance + correction_distance,
            "finalObservedErrorXZ": correction["finalErrorXZ"] if correction else metrics["finalXZError"],
            "status": ("approach-failed" if not arrived else
                       "model-settled" if settled else "terminal-unsettled"),
        },
        "physicalQualification": False,
        "gameInputSent": False,
        "limitations": [
            "Synthetic flat-plane ideal plant only; no collision or real actuator model.",
            "Correction budget is separate from approach and passive drain.",
            "No change to the established approach metrics or runtime policy.",
        ],
    }


def compact_report(result):
    """Extract an automation-oriented summary without dropping failure reasons.

    The full report remains the evidence source. The compact view includes
    provenance, policy, phase statuses, timing and explicit synthetic flags;
    a failed approach is not represented as a successful journey.
    """
    correction = result["terminalCorrection"]
    return {
        "schema": "taxi.synthetic-journey-summary/1",
        "classification": result["classification"],
        "routeId": result["routeId"],
        "inputTraceSHA256": result["inputTraceSHA256"],
        "approachMode": result.get("experimentalApproachMode", "baseline"),
        **({"assumedDelaySteps": result["approach"]["syntheticCommandPrediction"]["assumedDelaySteps"]}
           if "assumedDelaySteps" in result["approach"].get("syntheticCommandPrediction", {}) else {}),
        "approachStatus": result["approach"]["status"],
        "passiveDrainStatus": result["passiveDrain"]["status"],
        "terminalCorrectionStatus": correction["status"] if correction else None,
        "summary": result["summary"],
        "physicalQualification": result["physicalQualification"],
        "gameInputSent": result["gameInputSent"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", help="versioned synthetic motion-trace JSON")
    parser.add_argument("--dt", type=float, default=.1)
    parser.add_argument("--speed", type=float, default=3.)
    parser.add_argument("--yaw-rate", type=float, default=115.)
    parser.add_argument("--delay-steps", type=int, default=0)
    parser.add_argument("--approach-mode", default="baseline",
                        choices=("baseline", "predict-near-goal", "predict-near-stall", "zero-delay-rejoin"),
                        help="opt-in synthetic approach policy; baseline unchanged")
    parser.add_argument("--approach-budget", type=float, default=40.)
    parser.add_argument("--terminal-budget", type=float, default=5.)
    parser.add_argument("--lookahead", type=float, default=1.5)
    parser.add_argument("--out", type=Path, help="new full JSON report; never overwrite")
    parser.add_argument("--summary", action="store_true",
                        help="print compact JSON to stdout; --out still saves the full report")
    parser.add_argument("--require-settled", action="store_true",
                        help="return exit 1 for a valid but unsettled model journey")
    args = parser.parse_args(argv)
    try:
        result = journey(
            load_trace(args.trace), dt=args.dt, speed=args.speed,
            yaw_rate=args.yaw_rate, delay_steps=args.delay_steps,
            approach_budget=args.approach_budget, terminal_budget=args.terminal_budget,
            lookahead=args.lookahead, approach_mode=args.approach_mode)
        encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
        # Write the complete receipt first. A refusal to create the file
        # must not be masked by printing a successful-looking summary.
        if args.out is not None:
            with args.out.open("x", encoding="utf-8", newline="\n") as writer:
                writer.write(encoded)
        if args.summary:
            print(json.dumps(compact_report(result), indent=2, allow_nan=False))
        elif args.out is None:
            print(encoded, end="")
        # Keep legacy exit semantics unless the caller explicitly requests
        # a settled model journey. Exit 2 remains invalid input/I/O refusal.
        return 1 if args.require_settled and not result["summary"]["finalModelSettled"] else 0
    except (TraceError, ValueError, OSError) as error:
        parser.exit(2, f"Synthetic journey refused: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
