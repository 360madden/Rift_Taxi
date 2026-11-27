# M4 catalog construction — independent development handoff

November 27, 2026. Isolated branch `research/catalog-build-20261127`,
based on `35d15f1ae8bcd3a4463bb62d6b6de6ce291e56ec` of
`research/journey-automation-reporting` (PR #9). That base passed all
three hosted CI jobs in run 45935823679. Do not confuse this new
unvalidated slice with that already-passing baseline.

## Motivation and scope

The existing selector requires a catalog with exact package ID,
source world, frame digest, patch ID and requested destination.
Manual entry previously produced a draft missing destination binding.
The new standalone builder automates metadata derivation without
inventing labels, connectors, route joins, coordinate transforms or
physical traversal evidence. It uses only Taxi-owned local code and
externally pinned existing review packages. Source authentication,
live transform, collision clearance and movement authorization remain
unverified.

## Usage

Put a small explicit plan in the same directory as the review packages.
The only supplied fields are the local route/destination labels and
package basenames and IDs (the external expected package IDs, not
untrusted values discovered by inspecting arbitrary files).

```json
{
  "schema": "taxi.world-review-catalog-plan/1",
  "entries": [
    {
      "routeId": "example-route",
      "destinationId": "example-endpoint",
      "packageFile": "example.json",
      "packageId": "REPLACE_WITH_EXTERNAL_PACKAGE_ID"
    }
  ]
}
```

Use the trusted plan SHA-256, or compute the pin from the exact plan
bytes you just authored. A matching hash does not establish the source's
authenticity. Output must be a new file in the same directory.

```powershell
$pin = (Get-FileHash -LiteralPath plan.json -Algorithm SHA256).Hash.ToLowerInvariant()
python -B -m rift_taxi.world_catalog_build plan.json --expected-plan-sha256 $pin --out catalog.json
```

The command prints the exact output catalog SHA-256 and entry count.
Feed that hash to the existing `world_route_catalog` selector as
documented in WORLD_ROUTE_CATALOG.md. Catalog construction sorts
rows by route ID, derives the full world/frame/patch/goal from
reopened packages, refuses ambiguous labels in one scope, duplicate
IDs and unsafe filenames, and writes canonical UTF-8 bytes using
exclusive creation. Failure refuses the entire inventory. This is
not a hostile concurrent-filesystem sandbox; package pins remain
the integrity boundary.

## Validation and resume

Seven authored tests cover canonical bytes and end-to-end selection,
plan and package pin mismatches, corrupt alternate package, duplicate
identity/unsafe filename, conflicting destination, caller scope
override, and exclusive same-directory CLI output. Run:

```powershell
python -B -m unittest discover -s tests -p 'test_world_catalog_build.py' -v
python -B -m unittest discover -s tests -v
```

Hosted validation must pass at the new exact head before integration.
This branch contains no local or proprietary receipts, no game or
desktop action, and no sister-repository edits. LEGION was reachable
and reported a responding RIFT process PID 33672; its exact current
actor/zone/foreground/pose was not qualified. The local constrained
audit files and CI workflow changed concurrently during inspection,
then the local connector returned Session terminated. The independent
branch deliberately leaves those files, PR #9, and the working tree
untouched. Direct cloud Git clone could not resolve github.com;
GitHub connector publication and hosted Actions are the alternative.
After successful CI, integrate this small slice into the current
research branch with a normal reviewed merge (no force push).
Revalidate real package compatibility when LEGION is available.
Do not promote M1/M2/M3/M4 based on synthetic or offline evidence.
