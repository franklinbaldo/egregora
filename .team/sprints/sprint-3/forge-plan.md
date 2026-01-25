# Plan: Forge - Sprint 3

**Persona:** Forge ⚒️
**Sprint:** 3
**Created:** 2026-01-24
**Priority:** Medium

## Objectives
Building on the "Portal" theme established in Sprint 2, Sprint 3 will focus on component richness and interactivity.

- [ ] **Interactive Components:** Introduce standard UI components for "Callouts", "Tabs", and "Data Tables" that match the Portal aesthetic.
- [ ] **Accessibility Audit:** Run a full automated accessibility audit (Lighthouse/Axe) and fix all WCAG AA violations.
- [ ] **Performance Optimization:** Optimize asset loading (fonts, images) to ensure a Lighthouse Performance score of >90.
- [ ] **Dark/Light Mode Polish:** While "Portal" is dark-first, ensure a credible "Light Mode" fallback exists if the user explicitly requests it.

## Dependencies
- **Curator:** Feedback on the component library visual design.
- **Visionary:** If the "Structured Data Sidecar" is ready, I may need to build components to visualize that data.

## Context
Sprint 2 fixed the "basics" (branding, layout, broken links). Sprint 3 is about "delight" and "inclusion" (performance, a11y, interactivity).

## Expected Deliverables
1.  **Component Library:** A set of reusable CSS classes/HTML patterns for blog authors.
2.  **Audit Report:** A passing accessibility and performance report.
3.  **Optimized Assets:** WebP conversion for images, font subsetting if needed.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Scope Creep on Components | Medium | Low | I will stick to standard MkDocs Material extensions first before building custom JS. |
