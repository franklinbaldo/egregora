# Plan: Curator 🎭 - Sprint 3

**Persona:** Curator 🎭
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
With the visual identity established in Sprint 2, Sprint 3 shifts focus to the core "Reading Experience" and "Content Discovery".

- [ ] **Reading Experience Polish:** Deep dive into typography (line-height, measure, font-weight) and mobile responsiveness. Ensure long-form content is comfortable to read on any device.
- [ ] **Content Discovery UI:** Design and specify the UI for "Related Content" and the "Code References" feature (collaborating with Visionary).
- [ ] **100% Lighthouse Accessibility:** Aim for a perfect accessibility score. Move from "audit" to "fix".
- [ ] **Search Experience:** Evaluate and refine the search UI (standard MkDocs vs specialized implementation).

## Dependencies
- **Forge:** To implement the CSS tweaks for reading experience.
- **Visionary:** To provide the backend data for "Code References" so we can style them.

## Context
A pretty blog is useless if it's hard to read or if users can't find relevant content. Sprint 3 is about utility and depth.

## Expected Deliverables
1. **Typography Style Guide:** A section in `docs/ux-vision.md` defining the exact typographic scale and rules.
2. **"Code Reference" UI Spec:** A clear design for how code links should appear.
3. **Lighthouse Score Report:** Showing 100 (or near 100) on Accessibility.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Mobile layout is neglected | Medium | High | I will perform all my validations primarily on mobile viewports. |
| "Code References" are noisy | Medium | Medium | We will design them to be unobtrusive (e.g., sidenotes or tooltips) rather than interrupting the flow. |

## Proposed Collaborations
- **With Visionary:** To finalize the "Code Reference" UI.
- **With Forge:** To implement the detailed typographic refinements.
