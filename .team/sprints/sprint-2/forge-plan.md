# Plan: Forge - Sprint 2

**Persona:** Forge ⚒️
**Sprint:** 2
**Created:** 2026-01-26 (during Sprint 1)
**Priority:** High

## Objectives
My mission is to transform the Egregora blog into a polished, distinct product ("The Portal") by implementing the Curator's visual identity requirements and fixing critical frontend bugs.

- [ ] **Fix Social Cards:** Resolve the issue where generated social cards are missing CSS or returning 404s.
- [ ] **Implement "Portal" Palette:** Hardcode the custom color palette (Deep Blue `#2c3e50` / Yellow `#f9d423`) into the theme configuration, replacing the default Material colors.
- [ ] **Custom Favicon:** Add a unique favicon to the template to replace the MkDocs default.
- [ ] **Refine "Empty State":** Improve the "Welcome to Egregora" message on the homepage to be more engaging when no content has been generated yet.

## Dependencies
- **Curator:** I rely on the Curator for final approval of visual changes and any specific copy for the "Empty State".

## Context
Sprint 1 focused on basic functionality and "Graceful Degradation" of the demo command. Sprint 2 is about **Identity**. The current site looks like a generic MkDocs template. By the end of this sprint, it should look like a bespoke "Portal" into the Egregora collective.

## Expected Deliverables
1.  **Functional Social Cards:** `og:image` tags point to valid, generated images.
2.  **Themed Site:** The site uses the specific `#2c3e50` and `#f9d423` colors.
3.  **Favicon:** A custom `.ico` or `.png` is served.
4.  **Polished Homepage:** The initial landing page is visually distinct and welcoming.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Social Card generation fails in CI | Medium | Medium | I will ensure the necessary dependencies (CairoSVG, Pillow) are correctly handled in the environment or the generation logic degrades gracefully. |
| Custom CSS conflicts with Material updates | Low | Low | I will keep overrides minimal and scoped, as learned in Sprint 1. |

## Proposed Collaborations
- **With Curator:** Regular syncs (via tasks) to review visual changes.
