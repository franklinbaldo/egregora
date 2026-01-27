# Plan: Janitor - Sprint 3

**Persona:** Janitor 🧹
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
Following the structural changes of Sprint 2, my mission for Sprint 3 is **Modernization (Strategy C)**. I will polish the newly refactored code to ensure it meets modern Python standards.

- [ ] **Ruff Modernization:** Run `ruff check --select UP,SIM` on the codebase, specifically targeting the new modules created in Sprint 2 (`pipelines/etl/`, new `runner.py`).
- [ ] **Import Sorting:** Ensure all new files comply with `isort` / `ruff` import ordering.
- [ ] **Flaky Test Elimination:** If the heavy refactoring introduced flaky tests, I will switch to **Strategy D** to stabilize them.

## Dependencies
- **Simplifier & Artisan:** I can only polish their code after it is merged.

## Context
After major surgery (Sprint 2), the patient (codebase) will have scars (inconsistent styles, old patterns copied over). Sprint 3 is about healing those scars.

## Expected Deliverables
1.  Modernized code using Python 3.12+ features (via `UP` rules).
2.  Simplified control flow (via `SIM` rules).
3.  Green and stable CI pipeline.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Aggressive linting breaks behavior | Low | High | Verification via the full test suite after every automated fix. |
