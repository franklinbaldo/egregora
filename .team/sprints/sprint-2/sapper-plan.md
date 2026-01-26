# Plan: Sapper 💣 - Sprint 2

**Persona:** Sapper 💣
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to eliminate "silent failures" in the core orchestration logic, ensuring that the system fails explicitly and informatively.

- [ ] **Refactor `runner.py` Exception Handling:** Replace generic `try...except Exception` blocks in `src/egregora/orchestration/runner.py` with specific, structured exceptions.
    - Raise `MediaPersistenceError` for media failures.
    - Raise `CommandAnnouncementError` for command failures.
    - Raise `ProfileGenerationError` for profile failures.
- [ ] **Enhance Exception Hierarchy:** Expand `src/egregora/orchestration/exceptions.py` to cover the granular failure modes identified in `runner.py`.
- [ ] **Audit `agents` Package:** Continue the sweep of the `src/egregora/agents/` directory (started in Sprint 1) to identify and fix LBYL patterns.
- [ ] **Coordinate with Refactorers:** Ensure **Artisan** and **Simplifier** adopt the new exception classes in their decomposition work.

## Dependencies
- **Artisan:** High potential for conflict in `runner.py`. I will aim to merge my exception definitions *before* their decomposition, or work on a branch they can pull from.
- **Simplifier:** Similar coordination needed for `write.py`.

## Context
`runner.py` is the heartbeat of the system. Currently, it catches `Exception` in several places and logs a warning. This hides bugs (e.g., a `KeyError` in profile generation looks the same as a network error). This "Trigger, Don't Confirm" refactor is essential before the "Symbiote Shift" (Real-Time) makes debugging even harder.

## Expected Deliverables
1.  **Updated `runner.py`:** No generic `except Exception` blocks (unless at the very top level for final safety).
2.  **Expanded `exceptions.py`:** New classes for Media, Command, and Profile errors.
3.  **Green Tests:** Existing tests pass, and new tests verify the specific exceptions are raised.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Merge Conflicts with Artisan | High | High | I will create the *definitions* (Exception classes) first in a separate PR, then apply them to `runner.py` in smaller chunks. |
| Breaking "Resilience" | Medium | Medium | By removing "swallow and log", the pipeline might crash more often. I will ensure the top-level loop in `process_windows` still catches the new specific exceptions to maintain batch resilience, but with better logging context. |

## Proposed Collaborations
- **With Artisan:** "I'll define the exceptions, you use them in your extracted methods."
