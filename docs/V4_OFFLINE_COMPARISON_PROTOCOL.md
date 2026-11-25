# V4 offline comparison protocol

Prespecified before V4 outcomes are evaluated. The scenario design in simulation_holdout_v4_design.py remains unchanged. This is an ideal planar simulation experiment, not a RIFT control change.

## Candidate and controls

Use the existing turn-limited-ordered simulator and passive terminal drain. Baseline lookahead is 1.5 synthetic units. The single opt-in sensitivity candidate increases lookahead by nominal speed times modeled FIFO latency, capped at 3 synthetic units. At zero delay the candidate is exactly the baseline. This is a parameter sensitivity experiment, not a prediction of the queued pose; the existing lookahead parameter also controls internal rejoin and sharp-corner radii, so any effect cannot be attributed solely to anticipation.

No simulator source edits, physical calibration, network or game input. Preserve all original reports. Keep the 40-second approach budget, 2-unit cross-track limit, .30 endpoint tolerance, .95 positive-applied-velocity duty target, speed, yaw cap, timestep, route and starting pose unchanged.

## Evaluation

Run both configurations on all 72 V4 scenario IDs and 3 nominal delays, retaining each outcome (432 total simulation calls). Pair by source identity and delay. Verify each trajectory using the existing synthetic verifier and independently drain the FIFO for each geometric arrival. Record status, geometric arrival, settled-within-tolerance, combined arrival-and-duty, elapsed time, final error and settled error (null for failed approaches). Count gains and losses independently for each delay and each outcome; no survivor-only success denominators.

Zero-delay cases must have exactly matching outcome records. A candidate merits additional offline investigation only if no baseline geometric or settled successes are lost, at least one settled success is gained at nonzero delay, and there are no losses of arrival-plus-duty successes. Failure of any gate rejects this candidate under this protocol; no automatic promotion even if every gate passes. This strict gate is a research screen, not a proof of physical performance.

Freeze the candidate and comparator before evaluating V4. After inspection, retain this set as observed research, not a fresh holdout for subsequent tuning. No live qualification, safe traversal, physical actuator, or game-consumed STOP claim.
