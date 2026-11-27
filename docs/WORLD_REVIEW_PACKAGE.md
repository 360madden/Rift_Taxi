# Local world-candidate review packages

## Scope

The first M4 slice consumes a complete retained RiftWorld candidate-path
export for **offline review only**. It neither loads Detour binaries nor
runs a navigation query, transforms coordinates to the live game, certifies
clearance, or grants input authority. The original proposed execution-ready
world bundle remains unimplemented.

The validator uses the upstream candidate identity field set and canonical
SHA-256 serialization audited from RiftWorld core.py (SHA-256
bf62cb53abe8d39b4789af49fbc7037617613f3133c3113357ce9243f482d688).
Require a caller-supplied exact original SHA-256 and referenced source revision.
The revision is a reference to inspected source, not authentication of the
historical export's producer. The strict JSON parser rejects duplicate keys
and nonfinite values. Complete routes require 2–500 unique points, finite
source XYZ/Y-up, original evidence labels, explicit transform metadata,
consistent retained planner result, and matching snapped endpoints.
Any retained endpoint snap limits and measurements are cross-checked.
Nonzero connector offsets remain visible and unqualified. Patch coverage,
source world/floor, obstacle clearance, and transform authority are not
established by a standalone candidate. Source paths are not followed.

The portable single JSON file embeds the exact original bytes in canonical
base64, with a content-derived package ID. It carries no cached normalized
review or authority claims; reopening recomputes the review. A separately
retained expected package ID detects replacement of a self-consistent
envelope. It is an integrity check, not a signature or authentication.
Exclusive output creation refuses existing paths; interrupted output may
be incomplete and will fail inspection.

## CLI

From the Taxi checkout or installed Python package:

```powershell
$sha = (Get-FileHash -LiteralPath candidate.json -Algorithm SHA256).Hash.ToLowerInvariant()
python -B -m rift_taxi.world_candidate_review candidate.json --expected-sha256 $sha --source-commit SOURCE_COMMIT
python -B -m rift_taxi.world_review_package create candidate.json --expected-sha256 $sha --source-commit SOURCE_COMMIT --out new-package.json
python -B -m rift_taxi.world_review_package inspect new-package.json --expected-package-id PACKAGE_ID
```

Replace SOURCE_COMMIT and PACKAGE_ID with actual values. The create command
returns the package ID. Review does not require any sibling repository.

## Retained original compatibility check — LEGION, November 27

Read-only inspection of seven historical November 22 RiftWorld exports.
Current inspected RiftWorld checkout: 21379d48af770942174175cbb97457183f615903.
This is not proof that this commit produced the older files. Raw bytes
remain private local artifacts. The two unavailable snap-refused exports
were rejected; five complete exports passed the narrow review contract.

| Original basename | Original SHA-256 | Points |
|---|---|---:|
| destination-accepted.json | 08dde0ca8e28ae1e238ab6dc6bd74d7a251b4b61630e756bede1aad0386ae127 | 36 |
| legacy.json | 81a82467efe2bd886eea0a162e824328384f3ee53cd585b0ce628a3f11f70243 | 36 |
| near-surface.json | 36d41b3fd847a51e06fb4b3e3783b93e6c06acb49e3011dc68007f45aaca3431 | 36 |
| leg-1.json | 119a79853562710babcf12b90d99968fbe05c2df1c9820ee6a63edf96fb151cf | 16 |
| leg-2.json | 87b308ee921776352b99b7bb4350fc795cc55a81492ed1bd1c333a865ba8c568 | 16 |

The first three were from legion-watch-snap-limits-20261122-123202;
the last two from legion-watch-route-review-20261122. In particular, the
legacy requested goal is offset 2.5 XZ and 3.5871337891 Y source units
from its snapped point. Complete candidate status alone does not qualify
its connector.

Two exact-byte packages were created and independently reopened under
Taxi's ignored artifacts/m4-world-review-20261127-1108:

| Package | Package ID | File SHA-256 | Bytes |
|---|---|---|---:|
| accepted.json | 30012ad7e0e7a4124d8c8bfad5fe4c6112e14126980e38ff75b3d6c8f287506c | 9561da143083d91f5e20a7f9776787359a039f3d36f069c401ab368cb9df583c | 38085 |
| leg-2.json | dc5db2c6df55a0f24b31c4f37e13ea6f751ecc2e4ff1667d6da3d75a4d2664ea | e36ec3b6bd50ec7cf3ff0d3886bfea03fde6ddcf737a5db34806a4e8bf1927e1 | 21709 |

Decoded source hashes matched their pins; physical qualification remained
false. Eleven focused regressions passed, including synthetic package
reopening after original-source removal, malformed identity, wrong axis,
numeric type aliases, planner mismatch, snap refusal, duplicate keys,
modified package and exclusive publication. No game or sibling edits.

## Next boundary

Independently pin and inspect the authoritative patch/build/coverage chain
before introducing a local route catalog or executable route admission.
The missing-pole observation, incomplete coverage, source-to-live frame,
and current physical M1 requirements remain unresolved.
