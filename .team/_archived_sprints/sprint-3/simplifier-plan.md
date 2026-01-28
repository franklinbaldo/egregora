# Plan: Simplifier - Sprint 3

**Persona:** Simplifier 📉
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
Continue the simplification of the orchestration layer.

- [ ] **Extract Execution Logic from `write.py`:** Create `src/egregora/orchestration/pipelines/execution/` for window processing logic.
- [ ] **Extract Coordination Logic:** Move background task management and checkpointing to `src/egregora/orchestration/pipelines/coordination/`.
- [ ] **Consolidate Configuration Defaults:** If not completed by Artisan in Sprint 2, centralize default values to remove magic numbers.

## Dependencies
- **Simplifier (Sprint 2):** Depends on the successful extraction of ETL logic.

## Context
After handling the ETL/Setup phase in Sprint 2, the next biggest chunk of complexity in `write.py` is the execution loop and coordination of background tasks.

## Expected Deliverables
1.  **New Packages:** `execution/` and `coordination/` under `pipelines/`.
2.  **Significantly Smaller `write.py`:** Targeting < 200 LOC for the main entry point.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Logic Drift | Medium | High | Ensure that moving logic doesn't subtly change execution order or error handling. |
