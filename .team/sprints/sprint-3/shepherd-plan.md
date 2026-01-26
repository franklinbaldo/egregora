# Plan: Shepherd - Sprint 3

**Persona:** Shepherd 🧑‍🌾
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to support the "Symbiote Shift" and the move toward real-time processing by introducing performance regression testing and integration verification.

- [ ] **Latency Regression Framework:** Establish a baseline for message processing time and add automated checks (supporting Bolt).
- [ ] **Context Layer Verification:** Create integration tests for the new Universal Context Layer API (supporting Visionary).
- [ ] **Async Testing:** Implement `pytest-asyncio` patterns to verify the new async ingestion layer without race conditions.
- [ ] **Coverage Milestone:** Target **65%** global test coverage.

## Dependencies
- **Bolt:** I need the new Async Architecture and Latency Budget definitions.
- **Visionary:** I need the API spec for the Context Layer.

## Context
Sprint 3 shifts focus from Structure to Performance and Integration. The risks change from "breaking logic" to "introducing latency" or "race conditions". My testing strategy must adapt to measure time and concurrency, not just correctness.

## Expected Deliverables
1.  **Performance Tests:** `tests/perf/` suite using `pytest-benchmark` or custom latency assertions.
2.  **Async Tests:** Concurrency-safe tests for the new ingestion layer.
3.  **Integration Tests:** End-to-end verification of the Context API.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Flaky Async Tests | High | Medium | Use `pytest-asyncio` strict mode and avoid `time.sleep()`. Use deterministic event loop control where possible. |
| Performance Noise in CI | High | Low | Set generous thresholds for CI, but strict thresholds for local benchmarks. |

## Proposed Collaborations
- **With Bolt:** Define "Latency Budget" and how to measure it reliably.
- **With Visionary:** Validate the Context Layer API contract.
