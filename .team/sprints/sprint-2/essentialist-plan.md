# Plan: Essentialist - Sprint 2

**Persona:** Essentialist 💎
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to enforce architectural simplicity and reduce "lifetime maintenance load" by eliminating structural redundancy and over-layering.

- [x] **Delete `PipelineFactory`:** I have preemptively executed this task (Sprint 1) to clear the path for Artisan and Simplifier. The `PipelineFactory` class was a "God Object" and has been replaced by focused functions in `resources.py` and `etl/setup.py`.
- [ ] **Audit `runner.py` Refactor:** Review Artisan's decomposition of `runner.py`. Ensure it doesn't introduce "Indirection inflation" (factories building factories).
- [ ] **Review `etl` Architecture:** Work with Simplifier to ensure the new `etl` package remains flat and composable, avoiding deep inheritance hierarchies.
- [ ] **Heuristic Scan:** Run a full heuristic scan on `src/egregora/config/` as Artisan refactors it to Pydantic.

## Dependencies
- **Simplifier & Artisan:** My audit work depends on their active refactoring of the pipeline.

## Context
In Sprint 1, I successfully deleted `PipelineFactory`, a major architectural smell. For Sprint 2, I shift to a "Guidance & Review" role to ensure the major refactors landing in `runner.py` and `write.py` adhere to the "Simple over Complex" philosophy.

## Expected Deliverables
1.  **Code Review Reports:** Feedback on Artisan's and Simplifier's PRs.
2.  **Architecture Guardrails:** Direct intervention if refactors introduce "Over-layering".

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Artisan creates complex class hierarchy in Runner | Medium | Medium | I will advocate for functional decomposition over class-based inheritance during review. |
| Config refactor becomes "Meta-config" hell | Low | Medium | I will review the Pydantic models to ensure they map 1:1 with reality and don't add unnecessary abstraction. |
