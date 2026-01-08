# Curator Plan - Sprint 3

**Persona:** Curator
**Sprint:** 3
**Date:** 2024-07-27
**Priority:** Medium

## Goals

Sprint 3 will focus on improving the content experience and information architecture of the generated blog. Assuming the baseline branding and styling issues from Sprint 2 are resolved, this sprint will tackle how users interact with and navigate the content.

- [ ] **Improve Empty State:** Redesign the empty state message to be more engaging and helpful for new users.
- [ ] **Optimize Navigation:** Restructure the site navigation for better information hierarchy, including adding the missing "Journal" section.
- [ ] **Enhance Typography:** Define and document a consistent typography scale to improve readability and visual hierarchy.
- [ ] **Develop Site Branding:** Propose a distinctive site name to replace the generic "demo".

## Dependencies

- **Forge:** I will depend on Forge to implement the navigation changes in the `mkdocs.yml` template and any template changes required for the new empty state.

## Context

With the foundational branding and technical issues addressed in Sprint 2, Sprint 3 can focus on the user's journey through the content. The current navigation is suboptimal, and the empty state is uninviting. These are medium-priority tasks from `TODO.ux.toml` that will significantly improve the user experience.

## Deliverables

1.  **New Empty State Design:** A mockup or description of the new empty state in `docs/ux-vision.md`.
2.  **Optimized Navigation Structure:** A revised `nav` structure documented in `docs/ux-vision.md`.
3.  **Typography Scale:** A defined typography scale in `docs/ux-vision.md`.
4.  **Site Name Proposal:** A proposal for a new site name, with rationale.
5.  **Updated TODO List:** `TODO.ux.toml` updated to reflect the completed and in-progress tasks.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Navigation changes are complex | Low | Medium | I will clearly document the desired navigation structure and provide the exact YAML configuration to Forge. |
| Site name decision is subjective | Medium | Low | I will propose several options with clear rationale, and if necessary, suggest a data-driven approach for Egregora to generate the name. |
