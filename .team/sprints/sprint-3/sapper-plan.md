# Plan: Sapper - Sprint 3

**Persona:** Sapper 💣
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to extend resilience to the user experience and edge cases.

- [ ] **Global CLI Crash Handler:** Implement a top-level exception handler in `cli/main.py` (or equivalent) that catches unexpected crashes, logs a "Panic Report" to a file, and shows a friendly "Oops" message to the user.
- [ ] **Refactor `src/egregora/ops/media.py`:** Media operations (downloading, resizing, checking dimensions) are notoriously flaky. I will introduce specific exceptions (`MediaCorruptError`, `ImageProcessingError`) and robust fallback strategies.
- [ ] **Fuzz Testing Strategy:** Investigate and prototype a "Fuzz Test" that feeds garbage configuration and data into the pipeline to identify unhandled edge cases.

## Dependencies
- **Simplifier:** The CLI entry point structure might change in Sprint 2, affecting where I place the global handler.

## Context
After stabilizing the core structure in Sprint 2, Sprint 3 is about "Polish" and "Discovery". Users will be interacting more with the system. A crash with a raw Python stack trace is a bad user experience. We need "Trigger, Don't Confirm" even at the UI level: Trigger a crash report, don't confirm the user's fear that the software is broken.

## Expected Deliverables
1.  **Crash Reporter:** A module that serializes the crash state (without secrets!) to a log file.
2.  **Robust Media Ops:** Refactored `media.py` with 100% test coverage for failure modes.
3.  **Fuzzing POC:** A script or test suite using `hypothesis` or similar to fuzz the config loader.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Crash Handler Hides Bugs | Medium | High | The handler must *always* log the full stack trace to a file, even if it hides it from the console. |

## Proposed Collaborations
- **With Forge/Curator:** Discussing how media failures should be handled (e.g., placeholder images vs. broken links).
