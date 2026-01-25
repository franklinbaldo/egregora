# Plan: Essentialist - Sprint 2

**Persona:** Essentialist 💎
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to enforce architectural simplicity and reduce "lifetime maintenance load" by eliminating structural redundancy and over-layering.

- [x] **Consolidate CSS Architecture:** Merge fragmented CSS files (`docs/` vs `overrides/`) to eliminate shadowing bugs and enforce a single source of truth for theming. (Completed in Sprint 1 Planning Session).
- [ ] **Audit `PipelineFactory`:** The `src/egregora/orchestration/factory.py` file is becoming a "God Class" for instantiation. I will audit it for "Homemade Infra" (e.g., hardcoded retry logic) and refactor it to use declarative configuration.
- [ ] **Review `etl` Decomposition:** Review the PRs from Simplifier/Artisan for the `write.py` refactor to ensure they are actually simplifying the graph, not just moving complexity around.

## Dependencies
- **Simplifier & Artisan:** My audit work depends on their active refactoring of the pipeline.
- **Forge:** Verification of the CSS consolidation requires Forge's UI checks.

## Context
In Sprint 1/Planning, I identified and fixed a CSS shadowing bug that represented "Over-layering". For the rest of Sprint 2, I will act as a "Simplicity Watchdog" for the major pipeline refactors occurring.

## Expected Deliverables
1.  **Refactored CSS:** Single `extra.css` in `overrides/` (Done).
2.  **PipelineFactory Assessment:** A report or PR streamlining the factory logic.
3.  **Code Reviews:** High-level architectural reviews of Simplifier's and Artisan's PRs.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| CSS Merge breaks visuals | Medium | Low | Forge is tasked with UX verification. |
| Factory refactor conflicts with Simplifier | Medium | Medium | I will focus on the *instantiation logic* (clients, dbs) while they focus on the *execution flow*. |
