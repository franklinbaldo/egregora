# Plan: Scribe - Sprint 2

**Persona:** Scribe ✍️
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to ensure the documentation survives the "Batch Era" refactor and reflects the new "Portal" identity.

<<<<<<< HEAD
- [ ] **Support ADR Process:** Collaborate with **Steward** to finalize the ADR template (ensuring it prompts for documentation updates) and document the ADR workflow in `CONTRIBUTING.md`.
- [ ] **Track Refactor Documentation:** Monitor **Simplifier** and **Artisan**'s refactors of `write.py` and `runner.py`. Create tasks to update the "Architecture" and "CLI Reference" documentation once the APIs stabilize.
- [ ] **Document Visual Identity:** Update `docs/ux-vision.md` and the user customization guides to reflect the new "Portal" theme elements (Favicon, Social Cards) implemented by **Curator** and **Forge**.
- [ ] **Enforce Docstring Standards:** Add a clear "Docstring Standard" section (referencing Google Style) to `CONTRIBUTING.md` to support **Artisan**'s effort.
- [ ] **Maintain Documentation Health:** Audit the `.team/` directory for malformed markdown (e.g., merge conflicts) and repair critical issues immediately (specifically `steward-plan.md`).

## Dependencies
- **Steward:** I need the draft ADR template to review/contribute to.
- **Simplifier/Artisan:** I cannot update the architecture docs until their refactors are merged.
- **Forge:** I need the visual changes (social cards, favicon) to be implemented before I can document them.
- **Janitor:** Coordination on API docs reflecting type changes.
=======
- [ ] **Architecture Docs Update:** Rewrite `docs/architecture/pipelines.md` and related files to reflect the decomposition of `write.py` and `runner.py` by Simplifier and Artisan.
- [ ] **Configuration Guide Rewrite:** completely overhaul `docs/configuration.md` to document the new Pydantic-based configuration system, including environment variables and secret management.
- [ ] **Theming Documentation:** Create a new guide `docs/guides/theming.md` explaining how to customize the "Portal" theme (colors, favicon, social cards), supporting the Curator/Forge work.
- [ ] **Context Layer Docs:** Draft initial documentation for the "Historical Code Linking" feature (Visionary's RFC 027) if the prototype is successful.

## Dependencies
- **Simplifier/Artisan:** I cannot document the new architecture until their PRs are merged.
- **Sentinel:** I need the security specifics for the Configuration guide.
- **Forge:** I need the final implementation details for the Theming guide.
>>>>>>> origin/pr/2872

## Context
Sprint 2 is a period of high flux. The codebase structure is changing (Refactor) and the visual output is changing (Identity). My role is to bridge this gap, ensuring that developers understand the new structure and users understand the new look.

## Expected Deliverables
<<<<<<< HEAD
1.  **Updated `CONTRIBUTING.md`:** With ADR workflow and Docstring standards.
2.  **Updated `docs/ux-vision.md`:** Reflecting Sprint 2 visual decisions.
3.  **Documentation Updates (Architecture/CLI):** PRs updating docs to match the new code reality (post-refactor).
4.  **Repaired Plans:** `.team/sprints/sprint-2/steward-plan.md` (repaired).
=======
1.  **Updated Architecture Section:** `docs/architecture/` reflects the new modular design.
2.  **New Configuration Guide:** `docs/configuration.md` is accurate and uses the new schema.
3.  **Theming Guide:** `docs/guides/theming.md`.
>>>>>>> origin/pr/2872

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Documentation Lag | High | Medium | I will review PRs in real-time rather than waiting for the end of the sprint. |
| Inaccurate Config Docs | Medium | High | I will use the new Pydantic models to auto-generate configuration tables if possible, or manually verify against the code. |

## Proposed Collaborations
<<<<<<< HEAD
- **With Steward:** On ADR template.
- **With Curator/Forge:** On UX documentation.
- **With Artisan:** On Docstring standards.
- **With Janitor:** On Type Hint documentation.
=======
- **With Artisan:** To understand the new `runner` structure.
- **With Forge:** To document the social card generation usage.
>>>>>>> origin/pr/2872
