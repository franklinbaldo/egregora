# Plan: Sapper 💣 - Sprint 3

**Persona:** Sapper 💣
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to harden the new "Async Core" and "Discovery" pipelines against specific failure modes, supporting the transition to the "Symbiote" architecture.

- [ ] **Async Exception Handling:** Define and implement patterns for handling exceptions in `asyncio` streams (supporting Bolt's work). Ensure exceptions are propagated or handled gracefully without crashing the event loop or being swallowed.
- [ ] **Discovery Pipeline Hardening:** Work with Visionary and Simplifier to ensure the new RAG/Discovery pipeline has explicit failure modes (e.g., `EmbeddingGenerationError`, `VectorSearchError`).
- [ ] **Input Adapter Audit:** Continue the audit of input adapters to ensure they follow "Trigger, Don't Confirm", especially as they are refactored for async ingestion.
- [ ] **API Error Standardization:** Establish standard error response patterns (HTTP 4xx/5xx mapped from internal exceptions) for the new Context Layer API.

## Dependencies
- **Bolt:** I need the initial Async Core implementation to audit/refactor.
- **Visionary:** I need the Context Layer API design to define error mappings.

## Context
Sprint 3 introduces "Real-Time" and "Discovery". These features add significant complexity. A silent failure in a real-time stream is disastrous (data loss). A silent failure in Discovery means bad recommendations. Explicit exceptions are critical here.

## Expected Deliverables
1.  **Async Exception Patterns:** Documented patterns or utility decorators for safe async execution.
2.  **Hardened RAG Pipeline:** Exception hierarchy for the Discovery module.
3.  **API Error Middleware:** Middleware or utility to map `EgregoraError` subclasses to HTTP responses.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Async errors swallowed | High | High | Use `task.add_done_callback` or specific exception handlers in the main loop. |
| API exposes stack traces | Medium | High | Implement a global exception handler that sanitizes errors for the API response. |

## Proposed Collaborations
- **With Bolt:** Reviewing async code for error handling.
- **With Visionary:** defining API error contracts.
