# Plan: Simplifier - Sprint 2

**Persona:** Simplifier 📉
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to reduce architectural complexity. My primary target is the massive `write.py` pipeline orchestration file.

- [ ] **Extract ETL Logic from `write.py`:** Create `src/egregora/orchestration/pipelines/etl/` and move setup/loading logic there.
- [ ] **Simplify `write.py` Entry Point:** Reduce the cognitive load of the main `write` function by delegating setup tasks.
- [ ] **Verify Pipeline Integrity:** Ensure the refactor introduces no regressions in the `egregora write` command.

## Dependencies
- **Artisan:** Coordination to ensure we don't refactor shared imports simultaneously.

## Context
`src/egregora/orchestration/pipelines/write.py` is over 1400 lines long, mixing ETL, orchestration, execution, and error handling. This violates the Single Responsibility Principle and makes the system brittle. The Architecture Analysis explicitly recommends breaking this file down.

## Expected Deliverables
1.  **New Package:** `src/egregora/orchestration/pipelines/etl/`
2.  **Refactored File:** `write.py` (reduced size)
3.  **Tests:** New unit tests for the extracted ETL functions.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Breaking the Pipeline | Medium | High | Strict TDD. I will write tests for the extraction *before* switching the main pipeline to use it. |
| Merge Conflicts with Artisan | Low | Medium | I will focus on `write.py`, Artisan on `runner.py`. |
