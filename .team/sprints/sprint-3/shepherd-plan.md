# Plan: Shepherd - Sprint 3

**Persona:** Shepherd 🧑‍🌾
**Sprint:** 3
**Created:** 2026-01-26
<<<<<<< HEAD
<<<<<<< HEAD
**Priority:** High

## Objectives
My mission is to verify the "Symbiote Shift" features, specifically the Universal Context Layer API and real-time capabilities.

- [ ] **API Contract Testing:** Create comprehensive tests for the new Universal Context Layer API (RFC 026) using `respx` and schema validation.
- [ ] **Real-time Performance Benchmarks:** Add benchmarks for the new "Fetch-then-Compute" windowing logic to ensure it meets performance goals (O(1) slicing).
- [ ] **API Security Verification:** Verify authentication mechanisms and localhost binding for the new API.
- [ ] **Documentation Testing:** Verify that code examples in the new documentation are executable and correct.

## Dependencies
- **Visionary/Simplifier:** I need the API implementation (RFC 026) to be ready for testing.
- **Lore:** I will use the "Oral History" context to understand the expected behavior of legacy systems being replaced.

## Context
Sprint 3 introduces a new API surface area. This is the critical moment to establish a "Testing Contract" for external consumers (plugins, symbiotes).

## Expected Deliverables
1. `tests/api/test_context_layer.py`
2. `tests/performance/test_realtime_fetching.py`
3. `tests/security/test_api_auth.py`
=======
**Priority:** Medium

## Objectives
My mission is to expand verification into Performance, API, and Fuzzing domains to support the "Symbiote Shift".

- [ ] **Load Testing Framework:** Collaborate with Bolt to implement a load testing suite (using `locust` or custom scripts) for the new Async Ingestion Layer.
- [ ] **Context Layer API Tests:** Create a contract test suite for the new Context Layer API (defined by Visionary) to ensure it adheres to the OpenAPI spec.
- [ ] **Config Fuzzing:** Implement a fuzz testing strategy for the configuration loader to verify robustness against malformed inputs (supporting Sapper's crash handler work).
- [ ] **Mobile Verification:** Assist Scribe/Forge with automated checks for mobile responsiveness (e.g., viewport-specific snapshots).

## Dependencies
- **Bolt:** I rely on Bolt for the performance targets and async architecture.
- **Visionary:** I need the API spec for the Context Layer.
- **Sapper:** I need the new Config structure to target fuzzing.

## Context
Sprint 3 introduces real-time capabilities and external APIs. "Standard" unit tests are no longer enough. We need to verify *latency*, *concurrency*, and *robustness* against hostile inputs.

## Expected Deliverables
1.  **Load Test Suite:** `tests/load/`.
2.  **API Contract Tests:** `tests/api/`.
3.  **Fuzzing Script:** `tests/fuzz/test_config_fuzz.py`.
>>>>>>> origin/pr/2893
=======
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
>>>>>>> origin/pr/2874

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
<<<<<<< HEAD
| API spec changes frequently | Medium | Medium | I will write tests against the *interface* (OpenAPI spec/Pydantic models) to detect drift early. |
=======
| Fuzzing finds too many bugs | Medium | Medium | We will prioritize crashing bugs first, then validation errors. |
| API Spec instability | High | Medium | I will use contract testing tools (like `schemathesis`) that can adapt to changing specs. |

## Proposed Collaborations
- **With Bolt:** Jointly own the performance verification strategy.
- **With Visionary:** Ensure the API is testable by design.
>>>>>>> origin/pr/2893
=======
| Flaky Async Tests | High | Medium | Use `pytest-asyncio` strict mode and avoid `time.sleep()`. Use deterministic event loop control where possible. |
| Performance Noise in CI | High | Low | Set generous thresholds for CI, but strict thresholds for local benchmarks. |

## Proposed Collaborations
- **With Bolt:** Define "Latency Budget" and how to measure it reliably.
- **With Visionary:** Validate the Context Layer API contract.
>>>>>>> origin/pr/2874
