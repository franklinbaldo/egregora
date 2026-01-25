# Plan: Deps - Sprint 3

**Persona:** Deps 📦
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to support the shift to "Symbiote" (Real-time/API) by managing the new dependency footprint.

- [ ] **CI/CD Integration:** Work with Sentinel to integrate `bandit` and `pip-audit` into the automated pipeline.
- [ ] **API Dependencies:** Review and vet new dependencies for the Context Layer API (e.g., `fastapi`, `mcp`).
- [ ] **VS Code Plugin Strategy:** Advise on the dependency management for the VS Code plugin (Python vs Node ecosystem isolation).
- [ ] **Routine Updates:** Weekly audit and update of dependencies (targeting `pandas` 3.0 if viable).

## Dependencies
- **Sentinel:** CI/CD integration requires coordination.
- **Visionary:** New API dependencies depend on RFC decisions.

## Context
Sprint 3 introduces "Real-Time" and "External Access" (API/Plugin). This increases the attack surface and complexity. I must ensure we don't bloat the core `egregora` package with unnecessary heavy dependencies.

## Expected Deliverables
1.  **CI Security Jobs:** `pip-audit` running in GitHub Actions.
2.  **Vetted API Stack:** Minimal dependency set for the new API.
3.  **Updated `pyproject.toml`:** Reflecting the new architecture (potential new extras/groups).

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Dependency Bloat | Medium | Medium | Enforce strict review of new packages. Suggest "extras" for API components. |
