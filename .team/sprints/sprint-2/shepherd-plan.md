# Plan: Shepherd - Sprint 2

**Persona:** Shepherd 🧑‍🌾
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
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

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Refactor breaks many tests | High | High | I will prioritize fixing "behavioral" tests first, as they describe *what* the system does. Implementation tests can be deleted if they verify obsolete internal logic. |
