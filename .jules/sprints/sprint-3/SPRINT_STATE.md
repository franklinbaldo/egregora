# Sprint 3 - Final State

**Owner:** Maintainer 🧭
**Date:** 2026-01-12
**Status:** Planned

## Top Goals
1. **Enhance Core Stability & Type Safety:** Refactor `runner.py` with BDD and introduce Pydantic models for configuration to improve robustness. (Artisan, Refactor)
2. **Implement "Portal" UX Foundation:** Execute the visual identity defined in Sprint 2, focusing on the blog and task automation. (Curator)
3. **Expand Security Posture:** Harden the system against SSRF and introduce fuzzing capabilities. (Sentinel)
4.  **Strategic Alignment:** Update roadmap and ADRs, adjusting for the deferral of the "Structured Data Sidecar". (Steward)

## Commitments (Scope Locked)
- **Artisan:**
  - **Deliverable:** Type-safe `config.py` using Pydantic.
  - **Deliverable:** Refactored `runner.py` (collaborative with Refactor).
  - **Acceptance Criteria:** Configuration is validated at startup; `runner.py` passes new BDD specs.
- **Refactor:**
  - **Deliverable:** Refactored `issues` module to enable Curator's automation.
  - **Deliverable:** BDD test coverage for `runner.py`.
  - **Acceptance Criteria:** `issues` module has a clean, documented API; `runner.py` has high test coverage.
- **Curator:**
  - **Deliverable:** Implementation of "Portal" visual branding (Colors/Typography) in MkDocs templates.
  - **Deliverable:** Automated task creation using the new `issues` module API.
  - **Acceptance Criteria:** Blog reflects new branding; automated tasks are correctly generated.
- **Sentinel:**
  - **Deliverable:** SSRF protection tests and implementation.
  - **Deliverable:** Basic fuzzing framework setup.
  - **Acceptance Criteria:** SSRF tests pass; fuzzing framework can run basic inputs.
- **Steward:**
  - **Deliverable:** Updated Roadmap and ADRs reflecting current state (including handling deferred items).
  - **Acceptance Criteria:** Roadmap explicitly addresses the delay in "Symbiote" features.

## Deferred / Blocked Items
- **Visionary - "Related Concepts API":** **BLOCKED**. Depends on the "Structured Data Sidecar" which was deferred in Sprint 2.
- **Visionary - Real-time Adapter Prototype:** **BLOCKED**. Depends on `Architect` who is not active.
- **Steward - "Egregora Symbiote" Decision:** **PARTIAL BLOCK**. The data required for this decision (from Sidecar) is missing. Steward to focus on replanning/deferring this decision.

## Dependencies & Sequencing
- **[CRITICAL] Refactor -> Curator:** The `issues` module update is a prerequisite for Curator's automation tasks.
- **Artisan <> Refactor:** Both are targeting `runner.py`. **Strict coordination required.** Refactor should likely write the BDD specs *before* Artisan applies structural changes.

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Conflict in `runner.py` between Artisan and Refactor | High | Explicit coordination: Refactor defines BDD specs first; Artisan implements config changes. |
| Visionary has no viable work | Medium | Visionary should pivot to research or assisting Steward with replanning. |
| Missing `Forge` for UX implementation | Medium | Curator is taking on implementation, but `Forge` would be better. Maintainer will vote for `Forge` in next sprint. |

## Persona Governance
- **Observation:** The absence of `Builder`, `Architect`, and `Forge` has blocked key strategic initiatives (Visionary's work) and creates load on Curator.
- **Next Steps:** Maintainer will prioritize these personas for the Sprint 4 roster.
