# Original world-chain review — M4 metadata and retained payload slice

## Scope

The standalone world candidate reviewer has been extended with a separate
chain validator for the observed single-box RiftWorld scene-request-selection
format. It explicitly requires original candidate, patch and navigation-build
SHA-256 pins, a reference source revision, and four caller-supplied payload
paths. It never follows manifest path strings. It reconstructs original
patch/build content IDs and coverage summaries; cross-checks the world,
coordinate frame, scene identity reference, planner profile, source geometry
hash and request bounds; confirms the entire polyline is inside one convex
request box; and verifies retained geometry, scene, prepared OBJ and Detour
bytes. This is an offline consistency review, not a full RiftWorld scene
validator, pipeline dependency audit, Detour decoder, live transform or
corridor clearance test. Only the scene-request-selection case with one
request box and explicit offline diagnostic permission is supported.

## Actual retained original check — LEGION, November 27, 11:19 PHT

Upstream reference checkout: 21379d48af770942174175cbb97457183f615903.
The earlier source file pins still match:
core.py bf62cb53abe8d39b4789af49fbc7037617613f3133c3113357ce9243f482d688;
navigation.py 0e5bad994f6dbae3f875070e61650b8fb0f342cd0ffaf1c153589c244eefc023.
These identify inspected source, not the actual historical producer revision.

| Original metadata | SHA-256 |
|---|---|
| destination-accepted.json | 08dde0ca8e28ae1e238ab6dc6bd74d7a251b4b61630e756bede1aad0386ae127 |
| patch.json | 19963d29ec9f3b53552f092723a8e0a7573b3f92275028ba6cce38160e2daa21 |
| navigation.json | 00587961ab6320ff541e0081c24d893fcd029a7a0905d99acac2897c3dc28fb5 |

| Retained payload | SHA-256 | Bytes |
|---|---|---:|
| scene.obj | 36c219e6e9026f9f388c2c0d3222e450df3d364b1d533d1c3997e14943b00ca3 | 420204 |
| scene.json | d540ef22451f3d78807b3d6ed060bba54843b2b8222676d98014354fc2d8a220 | 7779 |
| detour.bin | 009286a349e9912fedc8dc8c791a7a858cbd01c02f10b006e16863ae5bbfd470 | 57242 |
| navigation-input.obj | da031af0a84ac1055ccd172d39317b5c98ea3bc657a6f02201c0381f434f5878 | 979628 |

The 36-point candidate ID is
901218c9557673ba09f883758503ea4d084e8118c1dcc37f8d2c5904983ff296.
Patch ID is 4c76528b8120f998cca2c371c7efc0ce97ef9d12352e26313e1139418f7ad7cc;
build ID 3C0EC513DA22BFD9072AC4D227E47F64E86183D9AB6C252D0961EB287FACEA41.
Originals are in the retained November 22 watch archive and snap-limits
directories described in WORLD_REVIEW_PACKAGE.md. No original bytes were
changed or published.

The recomputed scene summary is partial: two available models, two selected
records, no represented transform conflict, no claim that all physical
geometry is represented. Request-box containment includes requested and
snapped endpoints. Candidate and scene coordinates declare unknown,
unqualified RR2 transform. Pipeline dependencies, scene full validation,
Detour compatibility and endpoint connectors remain unverified.

Receipt: artifacts/m4-world-review-20261127-1108/chain-review.json
SHA-256 85f33d71edff72bc3981a42e8d5c7d524efa9333910995266106a4ba3851d268.
All 17 world-focused tests pass on LEGION, including six new chain tests.
This is not a complete world bundle or M4 exit.

## CLI

Run from Taxi's checkout or installed package:

```powershell
python -B -m rift_taxi.world_chain_review candidate.json patch.json navigation.json --candidate-sha256 CANDIDATE_PIN --patch-sha256 PATCH_PIN --build-sha256 BUILD_PIN --source-commit SOURCE_COMMIT --geometry scene.obj --scene scene.json --navmesh detour.bin --preparedObj navigation-input.obj --out new-chain-review.json
```

Use explicit original paths and retained metadata pins. The referenced
source revision is not cryptographic authentication. Output must be new.
A failed review returns exit 2. No physical input is authorized.

## Next steps

Keep review-only route admission separate from executable routing.
Extend explicit local catalog/selection for stored reviewed packages only
after independently binding the expected IDs; never infer connectors,
cross-floor access or actual physical clearance from candidate completeness.
