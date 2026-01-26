# Plan: Forge ⚒️ - Sprint 2

**Persona:** Forge ⚒️
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to complete the "Portal" visual identity and ensure a polished user experience.

- [x] **Functional Social Cards:** Ensure `og:image` tags are generated correctly and do not return 404s. (Requires `pillow`, `cairosvg`).
- [x] **Custom Favicon:** Implement a unique favicon for the site.
- [x] **Refine "Empty State":** Polish the "Welcome" message on the homepage to be engaging even without content.
- [x] **Consolidate CSS and Assets:** Fix shadowing bug by moving all theme assets to `overrides/` and cleaning up scaffolding logic.
- [ ] **Accessibility Audit (Preliminary):** Run a basic accessibility check (Lighthouse/Axe) on the new "Portal" theme to catch low-hanging fruit (contrast, labels).

## Dependencies
- **Curator:** For approval of visual refinements.

## Context
Foundational theming was established in Sprint 1 (including the Portal theme and Feeds page). Sprint 2 is about "Finish and Polish".

## Expected Deliverables
1. Working Social Cards.
2. Custom Favicon.
3. Polished Empty State.
4. Consolidated CSS/Asset Architecture.
5. Accessibility Report.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Social Card generation fails in CI | Medium | Medium | I will ensure the necessary dependencies (CairoSVG, Pillow) are correctly handled in the environment or the generation logic degrades gracefully. |
| Custom CSS conflicts with Material updates | Low | Low | I will keep overrides minimal and scoped, as learned in Sprint 1. |

## Proposed Collaborations
- **With Curator:** Regular syncs (via tasks) to review visual changes.
