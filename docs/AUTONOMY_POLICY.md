# Rift_Taxi — AI-first autonomous execution policy

**Effective:** November 23, 2026  
**Source:** Explicit user direction: "i prefer that you the AI do as much automation as you can do, without manual intervention from me. make this durable policy."

This policy is part of the repo's durable working instructions in [AGENTS.md](../AGENTS.md). It applies to future M1–M6 development and cross-session handoffs.

## Default workflow

AI should take work to an actual verified outcome, not merely suggest commands or wait for the user to do routine steps. On each task:

1. Identify the exact local machine and project, examine repository status, source/handoff evidence, and existing tools.
2. Select the shortest high-impact, independently testable path to the acceptance criterion. Do not rebuild mature sibling utilities or add broad architecture without a demonstrated need.
3. Implement, inspect, test and diagnose the result on the user's machine with available connected tools; use parallel independent checks where useful.
4. Automate application interactions and bounded observation experiments when the environment permits. Distinguish physical observation, native candidate evidence, operating-system input acceptance and verified in-game response.
5. Preserve originals, establish hashes and source provenance, run focused and full regressions as appropriate, then commit/push and independently verify the actual remote state.
6. Publish a timestamped accurate SITREP with measured outcomes, limitations and the next genuine blocker. Do not promise work outside the current tool execution.

## User interaction policy

**Avoid manual intervention by default.** Do not reflexively tell the user to open RIFT, press a key, copy a file, fetch a hash, run a test, restart a program or inspect an image if the current tools can reasonably accomplish it. First investigate and use the available automation and source evidence.

Ask for user action only when an indispensable human-only step or permission cannot be safely substituted (for example, an unavailable login, a high-impact irreversible change, a uniquely human observation not capturable from the environment, or a significant authorization decision).

A missing assistant subagent or desktop capability is not a reason to abandon the task. Use independent local tools, deterministic test helpers, existing repository code and read-only source research as alternatives; report exact limitations rather than inventing automated work or worker counts.

## Live RIFT experiments

A physical game test must not be faked or confused with a synthetic one. The preferred autonomous sequence is:

- Verify the physical machine, precise PID/start timestamp, executable hash, game HWND/foreground, current actor and zone; refuse stale or mixed-session identifiers.
- Confirm the displayed world/gameplay state, available screen/telemetry evidence, loaded addon/API producer activity and whether the character is in a suitable bounded test condition.
- For read-only capture, collect pinned native XYZ/yaw/actor matrices and time evidence and return any temporarily changed window focus/state to its previous condition.
- For actual control experiments, use only a consciously bounded, explicitly scoped physical input with working release ownership, watchdog/external STOP, verified pre/post OS state and independent newer in-game evidence. If such a gate is not actually qualified, **continue automated offline/read-only preparation**; never fabricate a `LivePose` qualification or silently disable the gate.
- Verify keys were attempted/released separately from the question of whether the game consumed them. Keep original source-hashed evidence out of Git and capture precisely what failed.
- Do not modify RR2, RiftWorld, Telara Fly, installed addons, game settings, account data or other unrelated source code as an incidental shortcut.

## Current M1 success criteria

M1 is not complete until the client/actor/zone is properly pinned, position updates and body-facing direction are independently qualified, a short bounded real movement and release are recorded, and later post-release native/in-game state is observed without sibling runtime dependencies. A passing Python test suite or one stationary native burst is progress toward this milestone, not success by itself.

This policy does **not** change the autonomous Taxi application's architecture: the finished runtime must need no AI or connected service to steer from destination to destination.

**Maintainers' note:** When updating roadmap or README, preserve a link to this policy. If a requested action cannot be completed autonomously, document the specific blocker and the automated alternatives attempted, rather than asking the user to perform routine work.
