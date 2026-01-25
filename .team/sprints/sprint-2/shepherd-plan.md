# Plan: Shepherd - Sprint 2

**Persona:** Shepherd 🧑‍🌾
**Sprint:** 2
**Created on:** 2026-01-26
**Priority:** High

## Objectives

Describe the main objectives for this sprint:

- [ ] Improve coverage for `src/egregora/agents/writer.py` to >60%.
- [ ] Improve coverage for `src/egregora/agents/enricher.py` to >50%.
- [ ] Stabilize existing benchmarks and add new ones for writer performance.

## Dependencies

List dependencies on work from other personas:

- **Refactor:** Coordination on any writer refactoring to avoid test churn.

## Context

Explain the context and reasoning behind this plan:

During Sprint 1, I focused on fixing broken tests and improving coverage for `formatting.py`. The core agents (`writer` and `enricher`) still have significant coverage gaps which poses a risk for regression.

## Expected Deliverables

1. Behavioral test suite for `writer.py`.
2. Behavioral test suite for `enricher.py`.
3. Updated coverage thresholds.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Tests becoming flaky due to mocks | Medium | High | Use `respx` and careful mocking strategies. |
| Code churn in agents | High | Medium | Communicate with Refactor/Typeguard personas. |

## Proposed Collaborations

- **With Refactor:** Ensure refactoring preserves behavior verified by new tests.

## Additional Notes

Focus remains on "Behavioral" testing - verifying outputs and side effects.
