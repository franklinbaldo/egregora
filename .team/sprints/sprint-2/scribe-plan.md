# Plan: Scribe - Sprint 2

**Persona:** Scribe ✍️
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to ensure the documentation survives the "Batch Era" refactor and reflects the new "Portal" identity.

- [ ] **Architecture Docs Update:** Rewrite `docs/architecture/pipelines.md` and related files to reflect the decomposition of `write.py` and `runner.py` by Simplifier and Artisan.
- [ ] **Configuration Guide Rewrite:** completely overhaul `docs/configuration.md` to document the new Pydantic-based configuration system, including environment variables and secret management.
- [ ] **Theming Documentation:** Create a new guide `docs/guides/theming.md` explaining how to customize the "Portal" theme (colors, favicon, social cards), supporting the Curator/Forge work.
- [ ] **Context Layer Docs:** Draft initial documentation for the "Historical Code Linking" feature (Visionary's RFC 027) if the prototype is successful.

## Dependencies
- **Simplifier/Artisan:** I cannot document the new architecture until their PRs are merged.
- **Sentinel:** I need the security specifics for the Configuration guide.
- **Forge:** I need the final implementation details for the Theming guide.

## Context
Sprint 2 is a period of high flux. The codebase structure is changing (Refactor) and the visual output is changing (Identity). My role is to bridge this gap, ensuring that developers understand the new structure and users understand the new look.

## Expected Deliverables
1.  **Updated Architecture Section:** `docs/architecture/` reflects the new modular design.
2.  **New Configuration Guide:** `docs/configuration.md` is accurate and uses the new schema.
3.  **Theming Guide:** `docs/guides/theming.md`.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Documentation Lag | High | Medium | I will review PRs in real-time rather than waiting for the end of the sprint. |
| Inaccurate Config Docs | Medium | High | I will use the new Pydantic models to auto-generate configuration tables if possible, or manually verify against the code. |

## Proposed Collaborations
- **With Artisan:** To understand the new `runner` structure.
- **With Forge:** To document the social card generation usage.
