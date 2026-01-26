# Plan: Shepherd - Sprint 2

**Persona:** Shepherd 🧑‍🌾
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to build a safety net for the major refactoring ("Structure & Polish") occurring this sprint. I aim to raise behavioral test coverage and ensure no regressions in critical pipelines.

- [ ] **Coverage Milestone:** Increase global test coverage to **60%** (currently ~58-59%).
- [ ] **Verify ETL Extraction:** Create behavioral tests for the new `src/egregora/orchestration/pipelines/etl/` module (supporting Simplifier).
- [ ] **Verify Runner De-composition:** Create behavioral tests for the refactored `runner.py` components (supporting Artisan).
- [ ] **Scaffolding Stability:** Ensure the `scaffolding.py` module (Project Init) is fully covered (completed in Sprint 1/Early Sprint 2).

## Dependencies
- **Simplifier:** I need the interface definitions for the new ETL module to write tests.
- **Artisan:** I need the new `runner` component structure to design appropriate test suites.

## Context
Sprint 2 involves breaking down the `write.py` monolith and the `runner.py` complex. These are the highest-risk changes in the codebase. If we break the pipeline, the system stops working. My role is to verify *behavior* so they can change *implementation* safely.

## Expected Deliverables
1.  **Test Suite:** New tests in `tests/unit/orchestration/pipelines/etl/`.
2.  **Test Suite:** New tests in `tests/unit/orchestration/runner/`.
3.  **Config:** Updated `pyproject.toml` with `fail_under = 60`.
4.  **CI:** Green CI pipeline throughout the refactor.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Tests tightly coupled to old implementation | High | Medium | Focus strictly on Input/Output verification (Behavioral Tests), ignoring internal state where possible. |
| Coverage drops during refactor | Medium | High | enforce coverage checks on every PR. If code moves, tests must move (or be rewritten). |

## Proposed Collaborations
- **With Simplifier:** Pair programming on TDD for ETL extraction.
- **With Artisan:** Reviewing `runner` refactor PRs for testability.
