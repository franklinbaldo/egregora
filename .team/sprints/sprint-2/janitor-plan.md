# Plan: Janitor - Sprint 2

**Persona:** Janitor 🧹
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to support the structural refactoring efforts by enforcing **Type Safety (Strategy B)**. I am explicitly avoiding Dead Code Removal to prevent overlap with the **Refactor** persona.

- [ ] **Enricher Typing:** Resolve the high concentration of `union-attr` errors in `src/egregora/agents/enricher.py`. This is the primary target to avoid conflicts with Artisan's config refactor.
- [ ] **Reduce Mypy Errors:** Target a 10% reduction in `mypy` errors overall.
- [ ] **Pydantic Migration Support:** Once Artisan lands the Pydantic refactor for `config.py`, I will audit it for type safety (if time permits in this sprint, otherwise moving to Sprint 3).

## Dependencies
- **Refactor:** I am stepping back from `vulture` tasks to let Refactor handle them.
- **Artisan:** I am avoiding deep changes to `config.py` until their Pydantic refactor is complete.

## Context
Sprint 2 is a heavy refactoring sprint. By enforcing strict types, I act as a safety net, ensuring that moving code around doesn't break data contracts. I have pivoted my focus to `enricher.py` to allow Artisan to freely refactor the configuration module.

## Expected Deliverables
1.  PRs fixing `mypy` errors in `src/egregora/agents/enricher.py` (specifically `PipelineContext` vs `EnrichmentRuntimeContext` issues).
2.  A measurable decrease in the total `mypy` error count.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Merge Conflicts with Simplifier | Medium | Medium | I will avoid touching `write.py` logic directly, focusing instead on the types of the objects it uses. |
| Type fixes uncover logical bugs | Low | High | I will document any logical bugs found and either fix them (if small) or report them as Tasks. |
