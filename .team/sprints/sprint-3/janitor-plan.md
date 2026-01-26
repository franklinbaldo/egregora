# Plan: Janitor - Sprint 3

**Persona:** Janitor 🧹
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission in Sprint 3 is to support the "Symbiote Shift" by ensuring the new Context Layer is type-safe and stable. I will also support the Refactor persona by stabilizing the test suite.

- [ ] **Type-Safe Context Layer:** Enforce strict type checking on the new "Universal Context Layer" APIs (RFC 026) and "Code Reference Detector" (RFC 027) being built by the Visionary.
- [ ] **Flaky Test Stabilization (Strategy D):** Identify and fix intermittent test failures to improve CI reliability, supporting the Refactor persona's test suite review.
- [ ] **Zero Regression:** Maintain the improved `mypy` baseline achieved in Sprint 2.

## Dependencies
- **Visionary:** I will be auditing their new code for type safety.
- **Refactor:** I will coordinate with them on which tests to target for stabilization.

## Context
As the codebase evolves towards the "Symbiote" vision, complex interactions between the agent and the git history will emerge. Strict typing is crucial here to prevent runtime errors in these new, data-heavy pathways.

## Expected Deliverables
1.  PRs adding type hints to new Context Layer modules.
2.  PRs fixing identified flaky tests (using `pytest` repetition to verify).
3.  Continued reduction in overall `mypy` error count.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| New Context Layer APIs change rapidly | High | Medium | I will focus on the stable core interfaces first and work closely with the Visionary. |
| Flaky tests are hard to reproduce | Medium | Medium | I will use the `loop-testing` strategy (Strategy D) to reliably reproduce failures before fixing. |
