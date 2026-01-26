# Plan: Shepherd - Sprint 3

**Persona:** Shepherd 🧑‍🌾
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to prepare the test infrastructure for the "Real-Time Pivot" and the "Discovery" features.

- [ ] **Async Test Infrastructure:** Set up `pytest-asyncio` (or `trio` fixtures if needed) to support Bolt's move to an async core.
- [ ] **Fuzz Testing Pilot:** Implement `hypothesis` based fuzz testing for the `enricher` pipeline to find edge cases in the new RAG logic.
- [ ] **Accessibility Automation:** Create a reusable verification script (using a tool like `pa11y` or `axe-core`) to audit the generated site's accessibility (supporting Curator).
- [ ] **Visual Regression Setup:** Investigate tools for simple visual regression testing for the "Mobile Polish" updates.

## Dependencies
- **Bolt:** I need to know the chosen async stack (`asyncio` vs `trio`).
- **Visionary:** I need the RAG pipeline logic to target with fuzz testing.
- **Curator:** I need the accessibility criteria.

## Context
Sprint 3 introduces complex new paradigms (Async, RAG). Standard unit tests might not be enough. Fuzzing can find "unknown unknowns" in the RAG logic, and async tests are non-negotiable for the real-time work.

## Expected Deliverables
1.  **Async Test Fixtures:** A set of pytest fixtures for testing async generators and streams.
2.  **Fuzzing Suite:** `tests/fuzz/test_enricher_fuzz.py` using `hypothesis`.
3.  **A11y Verification Script:** `scripts/verify_a11y.sh`.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Flaky Async Tests | High | High | I will use `anyio` or specific time-traveling test utilities to ensure determinism. |
| Fuzzing finds too many bugs | Medium | Medium | I will prioritize fixing crashes first, then logic errors. |

## Proposed Collaborations
- **With Bolt:** Ensuring the async architecture is testable.
- **With Curator:** Automating the A11y checks.
