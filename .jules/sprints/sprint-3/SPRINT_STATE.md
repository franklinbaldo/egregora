# Sprint 3 - Final State

**Owner:** Maintainer
**Date:** 2026-01-16
**Status:** Planned

## Top Goals (ordered)
1.  **Fortify System Security:** Expand the security test suite to cover OWASP Top 10 vulnerabilities (Sentinel).
2.  **Enhance Code & Data Integrity:** Introduce schema validation for dataframes and eliminate dead code/type warnings (Artisan, Refactor).
3.  **Strategic Alignment:** Define the roadmap for "Egregora Symbiote" and address technical debt priorities (Steward).

## Commitments (Scope Locked)
-   **Sentinel:**
    -   **Deliverable:** Security tests for OWASP categories A04, A07, A08, A09, A10.
    -   **Acceptance Criteria:** Tests implemented in `tests/security/` and passing.
-   **Artisan:**
    -   **Deliverable:** Implement schema validation (e.g., Pandera) for core DataFrames.
    -   **Deliverable:** Refactor one input adapter for robustness.
    -   **Acceptance Criteria:** Schema checks run in pipeline; Adapter handles errors gracefully.
-   **Refactor:**
    -   **Deliverable:** Resolve remaining `vulture` and `ruff` warnings.
    -   **Acceptance Criteria:** Pre-commit hooks pass cleanly.
-   **Steward:**
    -   **Deliverable:** Updated Roadmap and "Egregora Symbiote" ADR.
    -   **Acceptance Criteria:** Documents committed to `docs/` and `.jules/adr/`.
-   **Visionary:**
    -   **Deliverable:** RFC for "Related Concepts API".
    -   **Deliverable:** "Friction Hunting" Report.
    -   **Acceptance Criteria:** RFC and Report committed to repository.
-   **Curator:**
    -   **Deliverable:** Accessibility Audit Report.
    -   **Acceptance Criteria:** Report detailing violations and remediation plan.

## Deferred Items
-   **Curator's UX Implementation (Typography, Navigation, Related Content):** Deferred due to absence of **Forge** (Frontend Developer).
-   **Visionary's Sidecar Analysis & Real-time Prototype:** Deferred due to absence of **Builder** (Data Architect) and **Architect**. The "Structured Data Sidecar" was deferred in Sprint 2, so there is no data to analyze yet.

## Dependencies & Sequencing
-   **`Visionary` -> `Steward`:** The "Related Concepts API" RFC will inform Steward's roadmap decisions.
-   **`Sentinel` -> `Curator`:** Sentinel to assist Curator with automated accessibility tools if applicable.

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Key Personas (`Forge`, `Builder`) Inactive | High | Scope has been aggressively reduced to "Paper Work" (RFCs, Audits) and "Internal Quality" (Refactoring, Tests) for features requiring these roles. |
| Mixed Timeline Contexts | Medium | Plans have dates ranging from 2024 to 2026. Prioritizing 2026 context where conflicts exist. |

## Persona Governance
The absence of `Forge` and `Builder` continues to block significant user-facing and architectural feature work. Recommendations for next roster update: **Activate Forge and Builder.**
