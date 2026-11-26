# November 27, 2026 — fresh LEGION native candidate series and offline receipt audit

Base commit 308975f, branch research/journey-automation-reporting. Local PHT date November 27, corresponding to November 26 UTC. This is a fresh read-only acquisition and stored-evidence audit, not M1 acceptance or a movement experiment.

## Current process acquisition

At 16:57 UTC the PowerShell process inventory and Taxi's own OS identity inspection agreed on LEGION, PID 24992, HWND 4198144, executable C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe, start UTC ticks 639313044653553067 (2026-11-26T15:41:05.355Z), and on-disk SHA-256 df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01. The window was foreground at the identity observation. This is a new epoch; never reuse these pins as current without rechecking. Doctor reported Python 3.14.10, stdlib, offline-replay-ready, gameInputEnabled=false, nativeReaderImplemented=false and nativeCandidateQualifiedForMovement=false.

At 16:58:04–16:58:07 UTC, the existing observe-native-series command completed an explicitly pinned, foreground, read-only 24-sample series at requested 100 ms start spacing and 15-second maximum budget. All optional matrix, guard, translation, raw zone and passive W/A/D key observation fields were enabled. No input, focus change, restart, native write or addon change was performed. The report asserts two full OS/build admissions, one read-only handle and per-sample process/window checks.

| Measurement | Observed candidate result |
| --- | --- |
| Owner key | 239816685251645959 throughout |
| XYZ | One unique candidate: 7213.65771484375, 871.9497680664062, 3026.804443359375 |
| Player-system bearing | -63.031956793166614 degrees |
| Actor matrix planar angle | +63.03195978443172 degrees |
| Matrix raw-bit agreement | 24/24 |
| Raw zone key | 0x487C9102 throughout |
| Refresh guard handle/flag | 0 / 0 throughout |
| Sampled W/A/D polls | 48 per key, all UP |
| Observed sample gap min / median / max | 90.228 / 100.348 / 122.100 ms |
| Actual start spacing min / median / max | 100.096 / 100.514 / 107.458 ms |
| Max per-sample capture bracket | 25.446 ms |
| Total including admissions | 2.679150 s |

The historical November 23 raw-zone series (PID 424, separate epoch) has the same owner and raw zone candidate. Original `artifacts/m1-raw-self-zone-series-20261123-1410.json`, SHA-256 846451c6405e239a4327c7184666373d872e32c529b09db26e4065fc0de7a948. Cross-epoch agreement is candidate continuity, not identity authority. Its older schema revision lacks the newer capture-start cadence declaration; do not synthesize missing time brackets to make it compatible with the new strict audit.

A metadata-only inventory of installed addon SavedVariables found Atank Telemetry and RRECollector files last written 2026-11-24T18:05:56Z, before the current process started. This is not a comprehensive search for all possible producer receipts, but those files do not qualify as current-session API evidence. No saved-variable contents or account identifiers are included here. The desktop window enumeration refused with DESKTOP_TREE_UNSETTLED; no fresh screenshot or scene clearance was obtained. Do not proceed to a physical movement probe on this evidence alone.

## New reusable offline verifier

`python -B -m rift_taxi.verify_native_series` consumes an original bounded JSON file with exact expected SHA-256 and explicit expected host/PID/start/path/executable hash/HWND/owner pin. It rejects ambiguous JSON, pin mismatches, incomplete counts, unqualified flag promotion, malformed optional evidence, timing/bracket/cadence contradictions, changed owners or zones, inconsistent matrix bit equality/angle, and inconsistent key/change/gap summaries. It reuses existing pure matrix decoding and key-summary logic after validating their raw inputs. No live game, process, input, network, or sibling dependency. Outer admission elapsed time is bounded against the stored sample span rather than inventing unrecorded outer clock stamps. Reports are written to a new path only.

Example historical replay (from Taxi root; these are archived pins, NOT a new live admission):
```powershell
python -B -m rift_taxi.verify_native_series artifacts/m1-20261127-current-session-series-01.json --expected-sha256 3fea0fef655be1b434d2b3039c35aade37f397bd1ad33524a976c1d0fc9546f7 --host LEGION --pid 24992 --start-ticks 639313044653553067 --exe-path "C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe" --exe-sha256 df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01 --hwnd 4198144 --owner 239816685251645959 --out artifacts/NEW-series-audit.json
python -B -m unittest discover -s tests -p test_verify_native_series.py -v
```

Original `artifacts/m1-20261127-current-session-series-01.json`, 69,453 bytes, SHA-256 3fea0fef655be1b434d2b3039c35aade37f397bd1ad33524a976c1d0fc9546f7. Separate audit outputs `artifacts/m1-20261127-current-session-series-audit-01.json` and `-02.json`, each 1,835 bytes, identical SHA-256 a575a2c2de144e6a37716f63911d7fce68505611c0656b755ebd7f547b761bc6. Both exited 0 and reported stored-candidate-consistent. Full LEGION regression suite passed 642/642 in 96.865 seconds (exit 0); the baseline-byte-hash rejection is expected negative-test output. Eight focused tests passed, including rehashed tampering, wrong pins, timing and candidate-only flags, optional evidence and exclusive output. All original artifacts remain local ignored files.

## M1 decision

OS identity and fresh candidate acquisition succeeded in this session. Stored-receipt consistency is not authentication, physical pose freshness or current state verification. The stationary series cannot show producer update latency, causal response, independently authoritative actor/body yaw, public zone/world instance, or actual game-consumed key release. Existing historical physical calibration/fault tests remain useful but do not transfer authority to a new process. Production input stays disarmed. Next prioritize an independent current-session source-timestamped game/API observation and authoritative body-heading/freshness evidence; verify current scene and all gates before any separately authorized physical experiment.
