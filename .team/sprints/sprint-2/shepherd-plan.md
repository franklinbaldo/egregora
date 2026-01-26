# Plan: Shepherd - Sprint 2

**Persona:** Shepherd 🧑‍🌾
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to build robust verification suites that protect the system during the "Structure & Polish" phase.

- [ ] **Data Layer Verification:** Implement a comprehensive behavioral test suite for `DuckDBStorageManager` (`tests/unit/database/test_duckdb_manager_behavior.py`). This ensures that despite orchestration changes, the data persistence contract remains violated.
- [ ] **Runner Safety Net:** Add behavioral tests for `PipelineRunner` that treat it as a black box, verifying that valid inputs produce expected database states, regardless of internal refactoring by Artisan.
- [ ] **Refactor Support:** Monitor `Simplifier` and `Artisan` PRs to ensure new components (like `pipelines/etl/`) have associated behavioral tests, not just unit tests.

## Dependencies
- **Artisan & Simplifier:** My testing of `runner.py` and `write.py` depends on their refactoring schedule. I will aim to test the *current* behavior first to establish a baseline.

## Context
Sprint 2 involves major surgery on the orchestration layer. The risk of regression is high. By solidifying the tests for the *Data Layer* (DuckDB) and the *Runner Interface*, I provide a stable foundation for the refactoring work.

## Expected Deliverables
1.  `tests/unit/database/test_duckdb_manager_behavior.py`: 100% behavioral coverage of storage operations.
2.  `tests/unit/orchestration/test_runner_behavior.py`: Baseline tests for pipeline execution.
3.  Coverage report showing maintained or improved metrics despite refactoring.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Tests break due to API changes | High | Medium | I will focus on the public API of `DuckDBStorageManager` which should be stable. For `runner.py`, I will test the CLI entry point if the internal API is volatile. |

## Proposed Collaborations
- **With Bolt:** Coordinate on performance benchmarks to ensure my behavioral tests don't introduce performance regressions (e.g. by using heavy setups).
