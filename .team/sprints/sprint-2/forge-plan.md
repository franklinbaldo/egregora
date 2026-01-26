# Plan: Forge ⚒️ - Sprint 2

**Persona:** Forge ⚒️
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to finalize the "Portal" visual identity and ensuring a polished user experience, supporting Curator's vision.

- [ ] **Consolidate CSS:** (Completed in Sprint 1) Ensure no shadowing issues remain between `docs` and `overrides`.
- [ ] **Feeds Page:** Create a dedicated, styled page for RSS/Atom feeds (`docs/feeds/index.md`) to fix the 404 link on the homepage.
- [ ] **Finalize Social Cards:** Verify `og:image` tags and ensuring correct asset loading (Pillow/CairoSVG).
- [ ] **Refine "Portal" Identity:** Apply "High Fidelity Glassmorphism" to all remaining card types (Home, Archives) and ensure consistent typography.
- [ ] **Accessibility Audit:** Run Lighthouse/Axe on the new theme.

## Dependencies
- **Curator:** For design specs on Feeds page and Empty State copy.
- **Bolt:** Coordinating on Social Card performance/caching (persisting `.cache`).

## Context
Foundational theming was established in Sprint 1. Sprint 2 is about fixing the "Broken Windows" (404s, CSS shadowing) and polishing the "Portal" feel.

## Expected Deliverables
1. Consolidated CSS Architecture (No shadowing).
2. Functional "Feeds" Page.
3. Verified Social Cards.
4. WCAG AA Preliminary Report.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Dependency Bloat (CairoSVG) | Medium | Medium | Ensure strict version pinning and document system requirements (libcairo). |
| Visual Regression | Low | Medium | Use `egregora demo` to verify all page types after CSS unification. |

## Proposed Collaborations
- **With Curator:** Reviewing the Feeds page layout.
- **With Bolt:** Optimizing build times for social assets.
