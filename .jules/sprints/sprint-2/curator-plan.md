# Plan: Curator - Sprint 2

**Persona:** Curator
**Sprint:** 2
**Created:** 2026-01-08 (during Sprint 1)
**Priority:** High

## Goals

The primary goal for Sprint 2 is to address the most critical baseline UX issues identified in the initial audit. This will establish a stable, professional foundation upon which further improvements can be built. The focus is on moving from a generic, broken template to a distinctive and functional one.

- [ ] **Establish Visual Identity:** Move beyond the default Material for MkDocs look.
- [ ] **Fix Critical Errors:** Eliminate 404s and broken features that degrade the user experience.
- [ ] **Improve Information Architecture:** Ensure all generated content is discoverable.

## Key Deliverables

1.  **New Color Palette:** A custom, accessible color palette will be designed and documented in `docs/ux-vision.md`.
2.  **Functional CSS & Favicon:** The site will have a working custom CSS file and a branded favicon.
3.  **Corrected Navigation:** All key pages, including the Journal and Profiles, will be accessible from the main navigation.
4.  **Cleaned Configuration:** The analytics placeholder will be removed, and social card image generation will be functional.

## Tasks from TODO.ux.toml

This sprint will prioritize the following high-priority tasks:

- **`generic-color-palette` (curator):** I will design a new color palette that reflects the "collective consciousness" theme and meets accessibility standards.
- **`analytics-placeholder` (curator):** I will make the decision to remove the Google Analytics placeholder entirely, aligning with a privacy-first approach. I will then create a task for Forge to implement this removal.
- **`missing-custom-css` (forge):** Guide Forge to create the missing CSS file.
- **`missing-favicon` (forge):** Guide Forge to add the favicon assets.
- **`social-card-images-404` (forge):** Guide Forge to debug and fix the 404 errors for social sharing images.
- **`unlinked-pages-in-nav` (forge):** Guide Forge to update the navigation to include the Journal and Profiles pages.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Forge cannot resolve template complexity | Medium | High | My updates to `docs/ux-vision.md` and the detailed tasks in `TODO.ux.toml` provide clear guidance on where and how to modify the Python-embedded templates. |
| API rate limiting continues to block full site generation | High | Low | My focus is on the static scaffold. As long as `egregora demo` generates the site structure, I can validate the UX changes without AI-generated content. |

## Collaborations

- **Forge:** I will be the primary stakeholder for the tasks assigned to Forge, reviewing the implementation of the new CSS, favicon, and navigation structure. Clear acceptance criteria are defined in each task in `TODO.ux.toml`.
