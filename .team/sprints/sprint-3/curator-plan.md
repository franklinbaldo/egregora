# Plan: Curator 🎭 - Sprint 3

**Persona:** Curator 🎭
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives

With the "Portal" visual identity established in Sprint 2, Sprint 3 focuses on the **Reading Experience** and **Content Discovery**, ensuring the site works beautifully on all devices.

- [ ] **Mobile Polish:** Conduct a thorough audit of the "Portal" theme on mobile breakpoints. Ensure navigation, cards, and typography scale correctly.
- [ ] **Design Discovery UI:** Work with **Scribe** and **Visionary** to design the "Related Content" and "Code Reference" UI elements.
- [ ] **Typographic Refinement:** Implement a custom type scale that improves readability for long-form content, moving beyond the default sizing.
- [ ] **Accessibility Deep Dive:** Achieve a Lighthouse Accessibility score of 100% by systematically addressing contrast and labeling issues.

## Dependencies

- **Forge:** Needed for implementing mobile-specific CSS adjustments.
- **Visionary:** Collaboration needed for the "Code Reference" UI design (hover cards vs. sidebars).

## Context

The "Portal" looks good on desktop, but mobile is often an afterthought. Sprint 3 flips this, ensuring the immersive experience translates to smaller screens. Additionally, as we start generating richer content (links, code refs), the UI needs to support these new data types without clutter.

## Expected Deliverables

1.  **Mobile-Optimized Theme:** No horizontal scrolling, usable navigation, and readable text on mobile.
2.  **Discovery UI Mockups/Specs:** Specs for "Related Posts" and "Code References".
3.  **Refined Typography:** CSS variables for a modular type scale.
4.  **Accessibility Report:** Documentation of 100% Lighthouse score (or plan to get there).

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Mobile menu interactions are complex | Medium | Medium | I will stick to standard MkDocs Material patterns where possible to avoid reinventing the wheel. |
| Code References clutter the UI | Medium | High | I will design for "progressive disclosure" (hover/click) rather than always-on noise. |

## Proposed Collaborations

- **With Forge:** Mobile testing and CSS tweaks.
- **With Visionary:** Designing the "Code Reference" experience.
