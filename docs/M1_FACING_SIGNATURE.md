# M1 facing signature comparison — offline evidence, not yet body yaw

**November 23, 2026 · Rift_Taxi / LEGION · Python 3.14**

## Scope

RIFT Taxi now collects an optional **matrix-enabled candidate burst** and compares five **separately saved** bursts in the exact order:

1. **Baseline** — settled stationary reference.
2. **Camera-only** — operator-declared camera adjustment, intended as a negative control.
3. **Turn-left** — operator-declared A/left-turn phase.
4. **Turn-right** — operator-declared D/right-turn phase.
5. **Forward** — operator-declared forward travel phase.

The labels are just **operator descriptions**. Taxi neither generates those actions nor observes their occurrence from this data. A strong-looking numerical signature is **not sufficient to qualify actor heading**, passive XYZ freshness, game input consumption, or successful movement. Independent visual/game-API evidence and real input/action receipts must be correlated separately.

This is M1 research to identify promising orientation sources, **not** a runtime heading provider.

## Two new capabilities

### 1. Matrix-enabled multi-sample bursts

Add `--include-matrix-candidate` to the existing `inspect-native-burst` command. Each of 2–8 separate captures performs the same exact-process and HWND bracket, obtains the player-system yaw candidate plus XYZ candidate, and optionally acquires two source-pinned 3×3 matrices from the **same owner**:

- Position-secondary matrix at player position component `+0x94`
- Actor matrix at self actor component `+0x398`

Every observation records both original nine-`uint32` arrays, whether they match bit-for-bit, two independent **candidate** planar angles (or `null`), and matrix interpretation status. Inconsistencies such as out-of-range bits, a forged equality flag, contradicting interpretations of identical bits, changed process/window/player owner, missing matrix evidence, or unexpected qualification flags abort the whole burst.

The summary includes whether **any** position or actor matrix bits changed across samples, whether both sources matched in every sample, and a wrapped first-to-last **candidate** actor-matrix angular delta if both endpoints have structural angles. All source-freshness and heading verification flags stay **false**.

The old burst invocation, without the flag, still reads only its normal XYZ/yaw candidates and reports no matrix data.

### 2. Five-phase offline comparison

`compare-facing-phases` accepts five already saved, complete, matrix-enabled `taxi.native-candidate-burst/1` JSON files. It does **not** inspect running processes, call the native reader, or send game input.

It refuses missing/duplicate or oversized inputs; malformed JSON; nonfinite numbers; broken raw-bit evidence; incomplete, reversed, or overlapping observations; changes in host/PID/start-ticks/HWND/executable/player owner across phases; and any claim that game response, input actions, body heading, or freshness were already verified. It records the SHA-256 of each exact input file.

For each adjacent phase, it reports candidate XYZ displacement, X/Z travel bearing, player-system yaw delta, actor and position matrix angle deltas, raw-bit changes, and the endpoint cross-source equality state. The result is `taxi.facing-signature-comparison/1` with `status=offline-candidate-comparison-only` and explicit false verification flags.

## PowerShell usage

**Prerequisite:** RIFT must be running on the physical Windows host, with a freshly identified exact PID, executable SHA, process start ticks, HWND and host. See [the read-only native capture setup](M1_NATIVE_READONLY.md#explicit-pinned-candidate-capture-cli-m1-diagnostic-only). The game window **must be foreground during each native capture**. If launching from PowerShell retains console focus, use `--start-delay-seconds 5` and switch the foreground back to the RIFT window during that delay. The CLI waits before the first read; it never focuses RIFT automatically. Captures still correctly fail if RIFT is not foreground. Existing output filenames are rejected before the delay or native access.

Run a pinned burst after each *separately documented* phase, using unique file names:

```powershell
cd C:\work\Rift_Taxi

# Example: baseline only. The other four phases use the same exact
# pins with unique filenames after independently recorded manual changes.
python -B -m rift_taxi inspect-native-burst `
  --pid $rift.Id --start-ticks $startTicks `
  --exe-path $exe --sha256 $exeHash --hwnd $hwnd --host $computer `
  --samples 4 --interval-ms 250 --include-matrix-candidate `
  --start-delay-seconds 5 `
  --out .\artifacts\baseline-unique.json

# Offline, after all five phase files exist. No RIFT client required:
python -B -m rift_taxi compare-facing-phases `
  --baseline .\artifacts\baseline-unique.json `
  --camera-only .\artifacts\camera-only-unique.json `
  --turn-left .\artifacts\turn-left-unique.json `
  --turn-right .\artifacts\turn-right-unique.json `
  --forward .\artifacts\forward-unique.json `
  --out .\artifacts\facing-comparison-unique.json
```

A phase must have independently documented action/event context before a person can interpret its numerical results as a camera-only or A/D/W experiment. The comparator **never claims to have verified that context**. It intentionally requires all five phases on the **same exact process epoch**, not a cross-restart blend; a future separate restart study must be explicitly designed.

## Source provenance and limits

The matrix selectors and field offsets were independently adapted from the read-only RR2 research, as pinned in [M1 matrix diagnostic](M1_MATRIX_CANDIDATE.md). The installed LEGION RIFT executable's on-disk hash matched the supported updated build on November 23, but **RIFT was not running for this development slice**. All new burst and phase-comparison tests used synthetic candidate data and require actual game observations for real-world validation.

**Validation:** 154/154 regression tests passed on LEGION with Python 3.14; 6 matrix-burst tests, 12 five-phase comparator tests (including forged-summary rejection), and 4 foreground-delay/output-preflight tests were added beyond the previously published 132. The comparison is deterministic offline analysis, not actuator code or a working autopilot.

**Next live proof:** independently label the same-process phase action timeline and capture/game visually observed motion. Compare camera-only invariance and opposite A/D turns with at least two forward travel headings, fresh XYZ readbacks and exact input-release receipts, before the project promotes any heading source into `HeldInputController.LivePose`.
