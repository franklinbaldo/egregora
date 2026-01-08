# Plan: Curator - Sprint 3

**Persona:** Curator (🎭)
**Sprint:** 3
**Date:** 2026-01-08
**Priority:** Medium

## Goal

The goal for Sprint 3 is to shift focus from the foundational site structure and branding to the core reading experience. Having established a unique visual identity in Sprint 2, the next step is to enhance content hierarchy, readability, and information architecture.

## Key Initiatives

1.  **Define a Typography Scale:**
    -   **Task:** Create a new task in `TODO.ux.toml` for typography.
    -   **Action:** I will define a clear and consistent typography scale (H1, H2, H3, body, captions, etc.). This will improve visual hierarchy and make content easier to scan and read.
    -   **Deliverable:** A new section in `docs/ux-vision.md` detailing the font sizes, weights, and line heights for all text elements. The associated task will be added to `TODO.ux.toml` for Forge.

2.  **Improve Empty State and Homepage UX:**
    -   **Task:** `improve-empty-state-messaging` from `TODO.ux.toml`.
    -   **Action:** I will design a more engaging and informative homepage, particularly for the "empty state" when a user first generates their site.
    -   **Deliverable:** A mockup or detailed description of the new homepage layout and content, to be added to the task description in `TODO.ux.toml`.

3.  **Review Navigation and Information Architecture:**
    -   **Task:** Create a new task in `TODO.ux.toml` for navigation review.
    -   **Action:** I will conduct a full review of the default site navigation. This includes evaluating the placement of "Media," considering a dedicated "Journal" section, and ensuring the information architecture is intuitive for a personal blog.
    -   **Deliverable:** A set of recommendations for restructuring the `nav:` section in `mkdocs.yml`, to be added as a new task in `TODO.ux.toml`.

## Dependencies

-   **Forge Persona:** The successful implementation of the typography and navigation changes will depend on Forge's ability to translate the design specifications into the necessary CSS and `mkdocs.yml` template updates.

## Risks & Mitigations

| Risk                                     | Probability | Impact | Mitigation                                                                                             |
| ---------------------------------------- | ----------- | ------ | ------------------------------------------------------------------------------------------------------ |
| Typography changes are complex to implement | Medium      | Medium | Provide Forge with explicit CSS rules and clear instructions in the `TODO.ux.toml` task.               |
| Navigation changes are subjective         | Low         | Low    | Base recommendations on established UX best practices for blog navigation and clearly state the rationale. |

## Next Steps

-   This plan provides a forward-looking roadmap. The immediate focus remains on the successful execution of Sprint 1 and 2 tasks.
-   I will begin preliminary research into best practices for blog typography and navigation to inform the work in Sprint 3.
