# Plan: Sapper - Sprint 2

**Persona:** Sapper 💣
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to ensure the system fails gracefully during the major refactoring efforts of this sprint. I will focus on defining exception boundaries for the new architectural components.

- [ ] **Refactor `src/egregora/agents/enricher.py`:** This module interacts with external APIs (Google, etc.) and is a prime candidate for specific exception handling (`EnrichmentError`, `QuotaExceededError`) replacing generic `Exception` catches.
- [ ] **Secure `runner.py` Refactor:** Collaborate with Artisan to ensure the decomposed `PipelineRunner` methods raise domain-specific exceptions (`RunnerExecutionError`, `StageFailedError`) rather than leaking low-level implementation details.
- [ ] **Config Error UX:** Work with Artisan/Sentinel to wrap the new Pydantic configuration loading in a user-friendly error handler that transforms `ValidationError` into actionable messages.

## Dependencies
- **Artisan:** I am directly depending on their refactor of `runner.py` and `config.py`. I will follow their lead but supply the exception handling logic.

## Context
Sprint 2 involves breaking up "God Objects" (`write.py`, `runner.py`). This is the most dangerous time for stability. If we split logic but forget to move the error handling with it, the application will become fragile. I am the safety net.

## Expected Deliverables
1.  **Refactored Enricher:** `src/egregora/agents/enricher.py` using a new `EnrichmentError` hierarchy.
2.  **Runner Exceptions:** A set of exception classes for the orchestration layer (`src/egregora/orchestration/exceptions.py`).
3.  **Config Error Handler:** A utility to formatting Pydantic errors for the CLI.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Refactor Collision | High | High | I will work on `enricher.py` (isolated) first, then pair with Artisan on `runner.py` once their structure is PR'd. |
| "Exception Fatigue" | Medium | Low | I will ensure we don't create *too* many exceptions. Grouping by domain (Enrichment, Orchestration, Config) is key. |

## Proposed Collaborations
- **With Artisan:** Reviewing their PRs specifically for `try/except` blocks and exception hierarchy.
