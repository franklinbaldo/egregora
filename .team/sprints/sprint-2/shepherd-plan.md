# Plan: Shepherd - Sprint 2

**Persona:** Shepherd 🧑‍🌾
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to ensure that the "Structure" hardening in Sprint 2 is backed by robust behavioral verification. I will focus on the new exception hierarchies and the security of the configuration layer.

- [ ] **Verify Exception Hierarchy:** Create tests to validate the new typed exceptions from Sapper (`EnrichmentError`, etc.) are raised and caught correctly, preventing silent failures.
- [ ] **Config Security Verification:** Implement behavioral tests that attempt to leak secrets from the new Pydantic configuration models (verifying Sentinel/Artisan's work).
- [ ] **Refactor Verification:** Add "before/after" behavioral tests for `runner.py` to ensure the refactoring does not change the external API contract.
- [ ] **Coverage Growth:** Aim for a 2-4% increase in global test coverage by targeting the refactored modules.

## Dependencies
- **Sapper:** I need the new exception classes defined in `src/egregora/orchestration/exceptions.py`.
- **Artisan/Simplifier:** I need the new `runner.py` structure to land to finalize the verification suite.
- **Sentinel:** I need the new `config.py` models to test security boundaries.

## Context
Sprint 2 is about splitting "God Objects". This is high-risk. My role is to provide the safety net. If `runner.py` is split into 5 files, I need to ensure the *behavior* of the runner remains identical. I will also enforce the new "Trigger, Don't Confirm" error policy via tests.

## Expected Deliverables
1.  **Exception Test Suite:** `tests/unit/common/test_exceptions.py` verifying inheritance and error messaging.
2.  **Config Security Tests:** `tests/security/test_config_leakage.py`.
3.  **Runner Contract Tests:** `tests/unit/orchestration/test_runner_contract.py`.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Tests tightly coupled to implementation | High | Medium | I will strictly verify *outputs* and *side effects* (mocks), not internal method calls. |
| Refactoring changes behavior intentionally | Medium | Medium | I will communicate with Artisan/Simplifier to update tests if the contract *should* change. |

## Proposed Collaborations
- **With Sapper:** Reviewing exception handling PRs.
- **With Sentinel:** Pair programming on security test cases.
