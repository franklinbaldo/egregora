# Plan: Shepherd - Sprint 2

**Persona:** Shepherd 🧑‍🌾
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
<<<<<<< HEAD
<<<<<<< HEAD
My mission is to ensure the "Structure & Polish" sprint yields a robust, verifiable system. I will focus on testing the new configuration system, the decomposed runner, and critical database components.

- [ ] **Config Security Verification:** Create behavioral tests to verify that the new Pydantic configuration correctly masks secrets and handles environment variable overrides.
- [ ] **Runner Integration Tests:** Verify that the decomposed `runner.py` components interact correctly, mocking external API calls with `respx`.
- [ ] **Database Coverage Boost:** Increase test coverage for `DuckDBManager` and `EloStore` to >80%, focusing on error handling and edge cases.
- [ ] **Sprint Feedback:** Provide feedback on all Sprint 2 plans (Completed).

## Dependencies
- **Artisan:** I rely on the new `config` and `runner` implementations to be available for testing.
- **Sentinel:** I will align my config security tests with their requirements.

## Context
As the code structure changes significantly in Sprint 2, existing tests may break or become irrelevant. My role is to adapt the test suite to the new structure and ensure we don't lose coverage during the transition.

## Expected Deliverables
1. `tests/behavior/test_config_security.py`
2. `tests/behavior/test_runner_integration.py`
3. Increased coverage for `src/egregora/database/` (>80% for target files).
4. `shepherd-feedback.md`
=======
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
>>>>>>> origin/pr/2893
=======
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
>>>>>>> origin/pr/2874

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
<<<<<<< HEAD
| Refactor breaks many tests | High | High | I will prioritize fixing "behavioral" tests first, as they describe *what* the system does. Implementation tests can be deleted if they verify obsolete internal logic. |
=======
| Tests break due to API changes | High | Medium | I will focus on the public API of `DuckDBStorageManager` which should be stable. For `runner.py`, I will test the CLI entry point if the internal API is volatile. |

## Proposed Collaborations
- **With Bolt:** Coordinate on performance benchmarks to ensure my behavioral tests don't introduce performance regressions (e.g. by using heavy setups).
>>>>>>> origin/pr/2893
=======
| Tests tightly coupled to old implementation | High | Medium | Focus strictly on Input/Output verification (Behavioral Tests), ignoring internal state where possible. |
| Coverage drops during refactor | Medium | High | enforce coverage checks on every PR. If code moves, tests must move (or be rewritten). |

## Proposed Collaborations
- **With Simplifier:** Pair programming on TDD for ETL extraction.
- **With Artisan:** Reviewing `runner` refactor PRs for testability.
>>>>>>> origin/pr/2874
