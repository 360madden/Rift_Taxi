# November 27, 2026 — desktop evidence dependency diagnosis

LEGION, 03:45–03:46 PHT. Taxi research branch base 9ec24bd. This is a read-only dependency investigation and documentation checkpoint, not a Workbridge deployment or a live movement experiment.

## Regression and repository checkpoint

The outstanding post-hardening suite completed 654/654 tests, exit 0, in 182.625 seconds (job rt-20261127-0342-strict-full; the baseline-byte-hash rejection is expected negative-test output). The remote branch was independently queried and matched local 9ec24bd48cc822d703cdddc3cd71cacdd3118882 before this documentation update.

## Exact current process metadata

A fresh OS inventory on LEGION at 2026-11-26T19:45:14–19:45:19Z returned PID 24992, start UTC ticks 639313044653553067, HWND 4198144, session 4, responding=true, executable C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe, SHA-256 df954b798331e18359be62a31cc74b49fc3f50b87385ebb080a5448256322c01. This is a point-in-time metadata check, not a new native pose observation, actor/zone admission or foreground/scene proof.

## Concrete deployment gap

The active LEGION Workbridge metadata reports 0.16.4-dev, local service PID 24528, root C:\work, state C:\work\workbridge-mcp\.local. A read-only process metadata check confirmed that this Node process's command line refers to the checkout's dist directory. No full process command line, credentials, or unrelated desktop titles were retained.

The existing compiled dist/desktop-cli-runner.js resolves desktop prototype scripts relative to its own dist directory (lines 3–10). It launches the fixed prototype with the Node executable and treats a failed wrapper/uncertain child-tree termination as DESKTOP_TREE_UNSETTLED (lines 120–127). The existing scripts/stage-desktop-runtime.mjs explicitly declares a six-file build-time staging closure and its desktop-runtime-manifest.json (lines 1–19). This stager explicitly warns against running it against an active installation.

A new read-only file-presence inventory (job rt-20261127-0346-desktop-stage-inventory, exit 0) found:

| File | scripts/ | active checkout dist/ |
| --- | --- | --- |
| desktop-ui.mjs | present | absent |
| desktop-capture.mjs | present | absent |
| vmware-host-capture.mjs | present | absent |
| desktop-probe-act.mjs | present | absent |
| desktop-turn-admission.mjs | present | absent |
| Check-DesktopWindowHandle.ps1 | present | absent |
| desktop-runtime-manifest.json | not applicable | absent |

No .desktop-runtime-stage.lock was present. Absence of that staging lock is not proof that any GUI turn/quarantine or prior descendant process is cleared.

This verifies a concrete missing runtime dependency that is sufficient to explain a prototype-launch failure. It is consistent with the earlier DESKTOP_TREE_UNSETTLED refusal and RR2 dependency audit. No fresh desktop prototype was invoked; do not assert that this is the sole underlying cause, that a capture was repaired, or that desktop quarantine has been resolved.

## Recovery ownership and next order

The proper fix belongs to the separately owned Workbridge deployment workflow, WB-001, not Taxi. Use its existing isolated build/stage/validation and rollback gates, establish a suitable quiet window and explicit service-update authorization, then activate the sealed release and verify the live tool owner and a fresh read-only desktop smoke. Never copy scripts directly into active dist, execute source prototypes around the deployed admission gate, delete quarantine/locks, restart the service as an incidental Taxi action, or infer permission from a healthy terminal connector.

After the dependency is repaired through its owner workflow, obtain a new exact physical session/window/foreground pin and legitimate scene evidence. Then prioritize independent current-session changed-state position/body-heading observations, clock and producer provenance, and the remaining release gates. The prior static Telemetry and native receipts remain historical evidence; do not refresh their authority by matching a PID alone.

No Workbridge files or services, RR2/RiftWorld/Telara Fly, game files, addons, or settings changed in this cycle. No game input, screenshot, live native read, or physical qualification. Taxi production navigation remains disarmed. No Python source changed; 654/654 remains the verified code baseline.
