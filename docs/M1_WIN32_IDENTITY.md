# M1 read-only Windows identity inspection — November 23, 2026

**Repository:** RIFT Taxi on LEGION · **Component:** `rift_taxi/win32_identity.py`  
**Proof:** 11 tests in `tests/test_win32_identity.py`, included in **74/74 passing tests** on Python 3.14 / Windows 11.

## Purpose and scope

This Taxi-owned, standard-library Windows adapter establishes a **candidate operating-system process/window identity** before any future read-only RIFT pose reader is admitted. It does not discover an actor, identify a zone, read RIFT memory, launch RIFT, send input, or independently qualify a game session.

The design was informed by RR2's source-pinned `WindowsControlDesktop.cs` identity checks, but does not import RR2 code or depend on its running binaries. RR2, RiftWorld and Telara Fly are untouched.

## What is implemented

- **Explicit PID only.** No automatic process search, silent rebind, or arbitrary candidate selection.
- **Pinned executable.** The caller provides an absolute expected Windows executable path and a trusted SHA-256 of bytes on disk. Incorrect path/hash is refused.
- **Process-creation epoch.** Win32 `GetProcessTimes` FILETIME is converted to .NET UTC ticks (`FILETIME + 504911232000000000`), matching the epoch form used in RR2 research.
- **Window qualification.** Enumerate visible, non-minimized, unowned top-level windows belonging to the PID. One unpinned window must be unique; multiple windows require an explicit HWND.
- **Foreground and ownership.** A controller-oriented check rejects background state by default and verifies HWND ownership again before returning. A diagnostic caller may choose `require_foreground=False` but still cannot qualify an actor.
- **Race rejection.** Re-read the PID's start epoch/path after hashing and again after window inspection to detect changed process identity.
- **Monotonic timestamp.** Record the local OS observation time; this is not yet a live actor-pose timestamp.

### Minimal Python API

`inspect_desktop(pid, expected_executable_path=..., expected_executable_sha256=..., expected_start_utc_ticks=..., expected_window_handle=..., expected_host=...)` returns an immutable `DesktopCandidate` or raises `IdentityUnavailable`.

An initial path/hash-qualified inspection can omit the start/window pins, but its result is **only a candidate**. Subsequent observations must pin the exact PID, start epoch, HWND and host. Actor/zone and calibrated XYZ/yaw acquisition must still be independently qualified.

Windows calls are limited to `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)`, `GetProcessTimes`, `QueryFullProcessImageNameW`, and read-only user32 window enumeration/ownership/foreground queries. No `ReadProcessMemory`, `WriteProcessMemory`, or `SendInput` call exists in the module.

## Reproducible verification

From PowerShell in `C:\work\Rift_Taxi`:

```powershell
python -B -m unittest discover -s tests -p test_win32_identity.py -v
python -B -m unittest discover -s tests -v
```

**11/11 new identity tests** exercise expected identity, hash/path/epoch mismatch, PID reuse after two inspection phases, missing/ambiguous windows, wrong owner, background window, wrong machine/clock, invalid inputs, and **a real Win32 metadata read of the test runner's own Python process**. All passed on LEGION on November 23, 2026.

The whole suite passed **74/74**. No test read, launched or steered RIFT.

## Still needed for live M1

1. Source-verify a current-build RIFT native actor XYZ and **actor yaw** reader, including unique actor/zone identity and measured sample freshness.
2. Bind every pose to the same exact OS candidate, RIFT build, actor and window. Distinguish actor-facing yaw from camera yaw.
3. Build a bounded Windows input backend with independently supervised release; fake-backend acceptance is not game response.
4. Prove a short physically observed controlled movement and settled release, including restart/focus-loss failure cases, before declaring M1 complete.

This module is intentionally **not** a process scanner, runtime RR2 adapter or substitute for a fresh native observation.
