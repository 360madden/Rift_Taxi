# Synthetic route obligations — first offline acceptance slice

The existing steering and feedback simulators deliberately refuse traces with
mandatory passages and hard stops. This module adds a separate **sampled
evidence audit**, not an implementation of a live route follower. It requires
a strict `taxi.motion-trace/1` synthetic trace in synthetic-local XYZ units.
It does not accept historical or live game data.

## Policy

Supply a separate JSON policy with the following fields. The hash must be the
SHA-256 of the exact trace bytes, not the example placeholder.

```json
{
  "schema": "taxi.synthetic-route-constraints/1",
  "traceSHA256": "REPLACE_WITH_EXACT_TRACE_SHA256",
  "maxSampleGapSeconds": 0.25,
  "stopDwellSeconds": 0.4,
  "stopYTolerance": 0.1,
  "passageRegions": [
    {"pointIndex": 2, "minXYZ": [1.5, -0.1, -1], "maxXYZ": [2.5, 0.1, 1]}
  ]
}
```

Point indices are zero-based and refer to the trace's route points. Exactly
one positive-extent axis-aligned XYZ region per mandatory passage, in route
order, is required. A nominal point must lie within its region; a witness
can be anywhere in that region. A region visit is only an observed sample,
not proof of a required topological transition or physical clearance.

Hard stops and destination use the trace's XZ arrival tolerance plus the
explicit Y tolerance. They require consecutive, exactly equal synthetic
XYZ samples spanning the dwell duration, bounded intersample gaps, and no
supplied key activity during the witness interval. The destination witness
must end at the final observed sample. Each obligation consumes distinct
ordered samples; an earlier missing obligation blocks subsequent ones.
This is a conservative sampled rule, not proof of unobserved continuous
stationarity. Guides and optional points never create stop obligations.

## Usage

```powershell
python -B -m rift_taxi.synthetic_route_constraints trace.json policy.json --require-observed --out new-audit.json
```

Exit 0 indicates a valid report (or all observations when the optional
flag is set); exit 1 is a valid incomplete witness set under
`--require-observed`; exit 2 is invalid input or output refusal.
Both source and policy digests appear in the CLI receipt. Existing reports
are never overwritten. Neither a passing audit nor a complete synthetic
trajectory authorizes navigation in RIFT.

## Next boundary

Use this acceptance contract to inform a synthetic constrained journey
producer, and later qualify actual corridor regions, topology, sampled
freshness and stationary evidence independently. Do not turn an authored
region into a physical route clearance assertion. The original simulator's
constraint refusal and M1–M6 physical milestone criteria remain intact.
