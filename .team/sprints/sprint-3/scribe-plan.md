# Plan: Scribe ✍️ - Sprint 3

**Persona:** Scribe ✍️
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to ensure the "Discovery" features and "Mobile Polish" theme are fully supported by high-quality documentation, and to prepare for the "Real-Time" shift.

- [ ] **Document "Discovery" Features:** Create a comprehensive guide on how the "Related Content" (Discovery) features work, including how users can configure them (or confirming they are zero-config).
- [ ] **Mobile Documentation Audit:** Perform a full audit of the Egregora documentation site (`mkdocs serve`) on mobile devices. Identify and fix any layout issues, ensuring the docs themselves are "Mobile Polished".
- [ ] **API Reference Generation:** Ensure the new modules introduced in Sprint 2 (`src/egregora/orchestration/pipelines/etl/`, `src/egregora/config/`) have automatically generated API references in the documentation.
- [ ] **Update "Getting Started":** Review and refine the "Getting Started" guide to reflect the "polished" experience, ensuring screenshots and commands are current.
- [ ] **Document Real-Time Architecture:** (Placeholder) Work with **Bolt** and **Visionary** to create initial architectural documentation for the "Real-Time Adapter Framework" if the RFC is approved and implementation begins.

## Dependencies
- **Curator/Forge:** I need the "Related Content" features to be finalized before I can document them accurately.
- **Simplifier:** I need the new ETL package structure to be stable for API doc generation.
- **Bolt:** I need the Real-Time architecture to be defined.

## Context
Sprint 3 focuses on "Mobile Polish & Discovery". Users will be exploring the "magic" of Egregora (Discovery). The documentation must explain *why* this is magic and *how* it benefits them. Additionally, as we polish the mobile experience of the blog, our own documentation site must set the example. The shift to "Real-Time" is a major architectural change that will require immediate documentation coverage.

## Expected Deliverables
1.  **"Understanding Discovery" Guide:** A new concept guide in `docs/concepts/`.
2.  **Mobile-Optimized Docs:** Fixes to CSS/Layout of the documentation site.
3.  **Updated API References:** New sections in `docs/reference/`.
4.  **Refined "Getting Started":** Updated text and visuals.
5.  **Draft Real-Time Architecture Doc:** A new section in `docs/architecture/` (if applicable).

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Discovery features are complex to explain | Medium | Medium | I will focus on the "User Benefit" first, then the "How it Works". I will use diagrams if needed. |
| API Docs generation fails on new structure | Low | Medium | I will test `mkdocs build` with `mkdocs-material`'s python handler early in the sprint. |

## Proposed Collaborations
- **With Curator:** To understand the intended UX of the Discovery features.
- **With Forge:** To align on mobile design principles.
- **With Bolt:** On Real-Time Architecture documentation.
