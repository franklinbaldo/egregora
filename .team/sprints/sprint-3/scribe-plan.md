# Plan: Scribe ✍️ - Sprint 3

**Persona:** Scribe ✍️
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to ensure the "Discovery" features and "Mobile Polish" theme are fully supported by high-quality documentation.

- [ ] **Document "Discovery" Features:** Create a comprehensive guide on how the Content Ranking and Related Content features work, including how users can configure them (or confirming they are zero-config).
- [ ] **Mobile Documentation Audit:** Perform a full audit of the Egregora documentation site (`mkdocs serve`) on mobile devices. Identify and fix any layout issues, ensuring the docs themselves are "Mobile Polished".
- [ ] **API Reference Generation:** Ensure the new modules introduced in Sprint 2 (`src/egregora/orchestration/pipelines/etl/`, `src/egregora/config/`) have automatically generated API references in the documentation.
- [ ] **Update "Getting Started":** Review and refine the "Getting Started" guide to reflect the "polished" experience, ensuring screenshots and commands are current.
- [ ] **Document Symbiote Architecture:** If the "Symbiote" ADR is approved, create a new high-level architectural diagram/guide explaining the "Structured Sidecar" and "Context Layer".

## Dependencies
- **Curator/Forge:** I need the "Discovery" features to be finalized before I can document them accurately.
- **Simplifier:** I need the new ETL package structure to be stable for API doc generation.
- **Steward:** I need the "Symbiote" ADR to be approved before documenting the architecture.

## Context
Sprint 3 focuses on "Mobile Polish & Discovery". Users will be exploring the "magic" of Egregora (Discovery). The documentation must explain *why* this is magic and *how* it benefits them. Additionally, as we polish the mobile experience of the blog, our own documentation site must set the example.

## Expected Deliverables
1.  **"Understanding Discovery" Guide:** A new concept guide in `docs/concepts/`.
2.  **Mobile-Optimized Docs:** Fixes to CSS/Layout of the documentation site.
3.  **Updated API References:** New sections in `docs/reference/`.
4.  **Refined "Getting Started":** Updated text and visuals.
5.  **Symbiote Architecture Guide:** (Conditional) New section in `docs/architecture/`.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Discovery features are complex to explain | Medium | Medium | I will focus on the "User Benefit" first, then the "How it Works". I will use diagrams if needed. |
| API Docs generation fails on new structure | Low | Medium | I will test `mkdocs build` with `mkdocs-material`'s python handler early in the sprint. |

## Proposed Collaborations
- **With Curator:** To understand the intended UX of the Discovery features.
- **With Forge:** To align on mobile design principles.
