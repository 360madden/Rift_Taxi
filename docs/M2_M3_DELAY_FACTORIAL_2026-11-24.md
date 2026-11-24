# Matched synthetic command-delay factor study — November 24, 2026

**Scope:** Offline model research only. LEGION, Python 3.14.10.
**Starting commit:** `f0291077070837b0adf695268ecc3567ff10736b`.
**No controller change:** The four existing policies, original V3 cases and all prior reports remain frozen.

## Why this experiment exists

The V3 high-delay misses occurred in a profile that simultaneously increased nominal speed, yaw-rate cap, timestep and nominal FIFO delay. That observation alone could not distinguish the factors. This experiment crosses speed (2.2/3.4 synthetic units/s), yaw-rate cap (65/140 degrees/s), timestep (55/110 ms), and nominal delay (0/110/330 ms) across the original six geometries, two offsets and three heading offsets. The timestep is halved rather than reusing V3's 70 ms value, so both timesteps can represent exactly the same nominal delays using the bounded whole-step FIFO. It changes sampling and integration together, not a separate sensor delay. All 864 runs are retained, including failures. The original high-profile hashes and outcome values match the V3 reference in all 108 matching runs.

## Run and evidence

From the repository root, use a new report filename each time:

```powershell
python -B -m rift_taxi study-delay-factors --out artifacts/m2-m3-delay-factorial-NEW.json
```

Actual original report: `artifacts/m2-m3-delay-factorial-20261124-1326.json`, 667,969 bytes, SHA-256 `83c749b68236c62a8a3e85c94f9349016298eb3e53e2b9cd6971b18cc81cb65f`. Independent repeat `artifacts/m2-m3-delay-factorial-20261124-1327-recheck.json` has identical bytes (same length and SHA-256). Original frozen V3 report retained its pinned digest `e5d967cc062d6a4000c37880d27f829756a4a925d939d214663da81e74a19684`. Artifacts are local ignored files, not part of Git.

## Results

| Nominal delay | Runs | Geometric arrivals | Settled inside tolerance | Arrival + >=95% modeled forward duty |
|---|---:|---:|---:|---:|
| 0 ms | 288 | 288 | 288 | 104 |
| 110 ms | 288 | 288 | 288 | 89 |
| 330 ms | 288 | 263 | 225 | 32 |

At 330 ms, 25 timeouts and 38 additional out-of-tolerance settled endpoints remain. For each parameter, compare 144 matched pairs with all other factors fixed. Gains and losses are directional (lower to higher value):

| Factor increase | Geometric gains / losses | Settled gains / losses |
|---|---:|---:|
| Speed 2.2 -> 3.4 | 0 / 23 | 15 / 40 |
| Yaw cap 65 -> 140 | 0 / 25 | 9 / 42 |
| Timestep 55 -> 110 ms | 0 / 1 | 4 / 29 |

The high-speed/high-yaw configuration times out on the same 12 initial conditions at either timestep (narrow-return and double-crossing). Settled-inside counts for this configuration increase from 11/36 to 22/36 when timestep is halved, with geometric arrivals unchanged at 24/36. The low-speed/low-yaw/55 ms profile settles inside tolerance for 36/36 but only 12/36 meet the combined arrival/duty target. This is not an acceptable substitute for smooth navigation; selecting a single profile from observed cases would be development tuning.

## Next research gate

Prioritize a separately opt-in latency-aware synthetic control experiment that anticipates delayed commands, with distinct approach and settling tests. Preserve the original reports and compare against the same cases before introducing fresh geometry. Evaluate lost arrivals, forward duty and terminal error together. The fixed simulator default and prior experimental policies remain unchanged. None of these deterministic ideal-plant outcomes identify actual RIFT latency, safe traversal, real heading, or game-consumed STOP; M1 live qualification remains incomplete.
