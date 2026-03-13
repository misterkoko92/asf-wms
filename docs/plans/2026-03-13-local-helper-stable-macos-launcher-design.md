# Local Helper Stable macOS Launcher Design

## Goal

Reduce repeated macOS permission prompts during local Excel-to-PDF rendering by giving the helper a stable user-level launcher identity on macOS.

## Current Problem

The local helper installer currently points the LaunchAgent directly at the repository virtualenv Python binary:

- `repo/.venv/bin/python -m tools.planning_comm_helper.server`

That ties the running helper identity to the current checkout and virtualenv path. When the repo or worktree changes, macOS may treat the helper as a different requester for Automation permissions.

## Chosen Approach

Install a stable helper app bundle under the user account:

- `~/Applications/ASF Planning Communication Helper.app`

The LaunchAgent will point to the executable inside that app bundle instead of the repository virtualenv Python path. The executable inside the app bundle will remain a small launcher script that changes into the repository root and starts the existing helper server with the repository virtualenv.

## Why This Approach

- The visible macOS launcher path becomes stable across worktrees and updates.
- The current helper server implementation stays unchanged.
- The installer remains simple and local-only.
- This is achievable without introducing a separate packaging pipeline in this iteration.

## Rejected Alternatives

### Keep LaunchAgent on repo Python

Rejected because it preserves the unstable path problem.

### Auto-click macOS consent dialogs

Rejected because system consent dialogs are intentionally user-mediated and would require brittle UI scripting with additional permissions.

### Ship a fully packaged signed desktop app now

Rejected for this iteration because it adds a packaging and signing pipeline that is larger than the immediate need.

## Scope

In scope:

- macOS autostart path model
- macOS app bundle generation during helper install
- LaunchAgent plist generation
- installer messaging/tests/docs

Out of scope:

- changing the PDF render protocol
- Windows behavior beyond preserving existing tests
- code signing or notarization

## Testing Strategy

- Unit tests for macOS path generation
- Unit tests for LaunchAgent plist rendering
- Unit tests for app bundle file generation during install
- Targeted regression tests for helper installer payload behavior
