# Plan: Curator - Sprint 2

**Persona:** Curator
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives

Establish a solid UX baseline by fixing critical visual and functional bugs.

- [ ] Oversee the consolidation of CSS files to resolve the shadowing issue.
- [ ] Oversee the implementation of the Feeds index page to fix the 404 error.
- [ ] Verify the "Portal" vision integrity after CSS consolidation.

## Dependencies

- **Forge:** Must complete task `20260125-140000-ux-consolidate-css-shadowing.md`.
- **Forge:** Must complete task `20260126-1000-ux-implement-feeds-page.md`.

## Context

The current CSS architecture is fragmented, causing the "Portal" theme styles (in `docs/`) to shadow the structural fixes (in `overrides/`). This results in a broken layout on the homepage. Additionally, the "RSS Feeds" link on the homepage leads to a 404 page, which is a poor user experience.

## Expected Deliverables

1.  **Consolidated CSS:** A single source of truth for styles that correctly applies both the "Portal" theme and the layout structure.
2.  **Feeds Page:** A working `docs/feeds/index.md` page that lists available RSS/JSON feeds.
3.  **Verified Demo:** A `demo` site generated via `egregora demo` that passes visual inspection.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| CSS conflicts persist | Medium | High | Require Forge to verify with specific screenshots/DOM inspection. |
| Scaffolding logic fails | Low | Medium | Review scaffolding code changes carefully. |

## Proposed Collaborations

- **With Forge:** Direct feedback loop on the CSS consolidation to ensure the "Portal" aesthetic is preserved.
