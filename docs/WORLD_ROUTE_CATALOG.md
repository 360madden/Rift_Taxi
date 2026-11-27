# Local route review catalog — M4 selection slice

The catalog selects existing complete candidate review packages. It is not a
Detour query, a graph planner or a live journey controller. In particular, no
connector from the supplied start to the path, physical arrival, obstacle
clearance, world instance or coordinate transform is verified.

Each catalog is a bounded JSON file in the same directory as its packages.
The caller supplies the expected SHA-256 of the catalog. Use explicit
lowercase IDs and filenames. Every row pins a package ID, source world,
canonical coordinate-frame SHA-256, patch ID and exact requested goal XYZ.
A destination ID is a local label, not verified service/NPC presence. In one
world/frame/patch scope, rows with that label must have the same requested
goal. The package must reproduce the scope and goal from original bytes.

```json
{
  "schema": "taxi.world-review-catalog/1",
  "entries": [
    {
      "routeId": "example-route",
      "destinationId": "example-endpoint",
      "destinationXYZ": [4, 0, 0],
      "packageFile": "example.json",
      "packageId": "REPLACE_WITH_PACKAGE_ID",
      "sourceWorld": "synthetic",
      "frameSHA256": "REPLACE_WITH_CANONICAL_FRAME_SHA",
      "patchId": "REPLACE_WITH_PATCH_ID"
    }
  ]
}
```

The digest of the complete coordinates object uses upstream-compatible
canonical sorted-key compact JSON and SHA-256 (the existing Taxi
content_id helper). Select only within one explicit scope, with separate
limits for query-start XZ/Y offset and both retained endpoint snaps.
The selector ranks by start XZ, start Y, total 3D path length, then route
ID. Every matching package is independently reopened; a malformed or
tampered match aborts the query. Out-of-scope packages are not opened.
An offset within the supplied limit is not a verified connector.

```powershell
$pin = (Get-FileHash -LiteralPath catalog.json -Algorithm SHA256).Hash.ToLowerInvariant()
python -B -m rift_taxi.world_route_catalog catalog.json --catalog-sha256 $pin --destination-id example-endpoint --source-world synthetic --frame-sha256 FRAME_PIN --patch-id PATCH_PIN --start-xyz 0 0 0 --max-start-xz 0.1 --max-start-y 0.1 --max-snap-xz 0.1 --max-snap-y 0.1 --out selection.json
```

Exit 0 is a review path selected, 1 is a valid no-match report, 2 is
invalid input or I/O refusal. Output paths must not exist. Filename rules
refuse separators, case aliases and reserved device names. Nonregular
files and observed reparse points are refused; this is not a hostile
filesystem race sandbox. All results explicitly retain false production
input and physical qualification flags.

## Retained original compatibility — LEGION November 27

The two original packages documented in WORLD_REVIEW_PACKAGE.md were
selected using their own exact start coordinates, a 0.01 source-unit start
limit on each axis component, and 0.1 XZ/Y snap limits. Both passed; querying
the other patch for each destination returned no matching route. No route
joining or live input was attempted.

| Route | Points | Computed 3D length (source units) |
|---|---:|---:|
| accepted | 36 | 26.1052977669 |
| leg-2 | 16 | 15.2933613908 |

The common declared frame digest is
5a48f01242b73bf8c12313b3be672de716c1dd3c2b18a2aa124f3187445a3989.
Their patch IDs differ, and the live transform remains unknown. Destination
labels are deliberately generic review labels, not asserted NPC names.

Private receipt directory: artifacts/m4-world-review-20261127-1108.
Final catalog review-catalog-02.json SHA-256:
7902202b3ccf80a2c1961279873e8b7896a55f0023c7f43e942e8308fd323efa.
Selection receipts accepted-selection-02.json:
352e44a249eb663cc782ee0bb48730e131abb9719d893c9da35e69b0b0034102;
leg-2-selection-02.json:
997f0fa3fdccf96b8811d65779d4716f5a7e0838501eb89d8b900ba60163c4ce.
The earlier draft 01 files were retained for history, not current admission.
All 27 world-focused tests passed, including ten new catalog regressions.
