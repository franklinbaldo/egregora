# Plan: Typeguard - Sprint 2

**Persona:** Typeguard 🔒
**Sprint:** 2
**Created:** 2026-01-24
**Priority:** High

## Objectives

My mission is to enforce strict type safety across the codebase. For Sprint 2, I will focus on the agentic core and supporting the structural refactoring.

- [ ] **Fortify Agent Modules:** Apply strict typing to `src/egregora/agents/writer.py` and `src/egregora/agents/enricher.py`. These are complex files with high logic density.
- [ ] **Support Configuration Refactor:** Collaborate with Sentinel/Artisan to ensure the new Pydantic configuration models are strictly typed and leverage type validation for security.
- [ ] **Strict Typing for Runner:** Ensure the refactored `runner.py` (and its decomposed parts) maintains 100% type coverage.
- [ ] **Dependency Stubs:** Audit missing stubs for third-party libraries (like `ibis`, `google-genai`) and add suppressions or stubs where needed.

## Dependencies

- **Artisan:** I depend on the stability of the new `runner` decomposition to apply typing.
- **Sentinel:** I need the new config structure to be settled before I can fully type-check it.

## Context

In Sprint 1, I fortified `write.py` (pipeline orchestration), uncovering several potential bugs (like async/sync mismatches). In Sprint 2, as the team focuses on "Structure", I will ensure that this structure is rigid and reliable through type safety.

## Expected Deliverables

1.  **Strictly Typed Agents:** `writer.py` and `enricher.py` passing `mypy --strict`.
2.  **Typed Config:** Verified type safety of the new configuration module.
3.  **Typed Runner:** Verified type safety of the new runner module.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Refactoring Flux | High | Medium | Fast-moving refactors might break my type fixes. I will coordinate closely with Artisan to apply fixes *after* structure settles or *during* PR review. |
| Missing Stubs | Medium | Low | Third-party libs (like `ibis`) often lack stubs. I will use `cast` and explicit ignores responsibly. |

## Proposed Collaborations

- **With Artisan:** To ensure the runner refactor is typed from day one.
- **With Sentinel:** To verify that strict typing is supporting the security goals of the config refactor.
