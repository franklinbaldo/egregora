# Plan: Janitor - Sprint 2

**Persona:** Janitor 🧹
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to support the structural refactoring efforts by enforcing **Type Safety (Strategy B)**. I am explicitly avoiding Dead Code Removal to prevent overlap with the **Refactor** persona.

- [ ] **Reduce Mypy Errors:** Target a 10% reduction in `mypy` errors, focusing on modules unrelated to active dead-code removal.
- [ ] **Type-Safe Config Support:** Assist **Artisan** by ensuring existing configuration usages are type-safe, preparing the ground for the Pydantic migration.
- [ ] **Enricher Typing:** Resolve the high concentration of `union-attr` errors in `src/egregora/agents/enricher.py` identified in previous journals.

## Dependencies
- **Refactor:** I am stepping back from `vulture` tasks to let Refactor handle them.
- **Artisan:** My work on config typing complements their Pydantic refactor.

## Context
Sprint 2 is a heavy refactoring sprint. By enforcing strict types, I act as a safety net, ensuring that moving code around doesn't break data contracts.

## Expected Deliverables
1.  PRs fixing `mypy` errors in `src/egregora/agents/enricher.py`.
2.  PRs fixing `mypy` errors in `src/egregora/config/` and related files.
3.  A measurable decrease in the total `mypy` error count.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Merge Conflicts with Simplifier | Medium | Medium | I will avoid touching `write.py` logic directly, focusing instead on the types of the objects it uses. |
| Type fixes uncover logical bugs | Low | High | I will document any logical bugs found and either fix them (if small) or report them as Tasks. |
