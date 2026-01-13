---
id: "20260110-1000-ux-comprehensive-improvements"
title: "Comprehensive UX Improvements for MkDocs Blog"
status: "todo"
author: "curator"
priority: "high"
tags: ["#ux", "#bug", "#design", "#frontend"]
created: "2026-01-10"
---

## 🎭 Curator's Report: Comprehensive UX Improvements

This task consolidates several outstanding UX issues into a single, actionable set of instructions for the Forge persona. Please address all of the following issues.

### 🔴 RED: The Problems

1.  **Broken Social Card Images:** The `mkdocs build` process is generating 404 errors for the social card preview images. This degrades the experience of sharing links to the blog on social media.
2.  **Analytics Placeholder:** The `mkdocs.yml` file contains a placeholder for a Google Analytics key (`__GOOGLE_ANALYTICS_KEY__`). This is not a privacy-first approach and should be removed.
3.  **Inconsistent Color Palette:** The `mkdocs.yml` file specifies the default `teal` and `amber` color palette, but the `extra.css` file overrides this with a custom blue and yellow palette. This inconsistency should be resolved.
4.  **Missing Favicon:** The site is missing a favicon, which makes it look unprofessional in browser tabs and bookmarks.

### 🟢 GREEN: Definition of Done

1.  **Social Cards:** The `mkdocs build` command runs without any 404 errors related to social card images.
2.  **Analytics:** The `analytics` section is completely removed from the `mkdocs.yml` file.
3.  **Color Palette:** The `palette` section in `mkdocs.yml` is updated to use `primary: custom` to match the custom palette defined in `extra.css`. The `accent` color should also be updated to `yellow`.
4.  **Favicon:** A favicon is added to the site. A simple, placeholder favicon is acceptable for now.

### 🔵 REFACTOR: How to Implement

1.  **Social Cards:** Investigate the `social` plugin configuration in `mkdocs.yml` and the build process to identify the root cause of the 404 errors. This may involve debugging the plugin or the way it's configured.
2.  **Analytics:** In `src/egregora/output_adapters/mkdocs/scaffolding.py`, remove the `extra.analytics` section from the `MKDOCS_YML_TEMPLATE` string.
3.  **Color Palette:** In `src/egregora/output_adapters/mkdocs/scaffolding.py`, modify the `theme.palette` section in the `MKDOCS_YML_TEMPLATE` string. Change `primary: teal` to `primary: custom` and `accent: amber` to `accent: yellow`.
4.  **Favicon:** In `src/egregora/output_adapters/mkdocs/scaffolding.py`, add a `favicon` key to the `theme` section of the `MKDOCS_YML_TEMPLATE` string, pointing to a new favicon file (e.g., `assets/images/favicon.png`). You will need to create a placeholder favicon image and ensure it's copied to the correct location during the build process.

### 📍 Where to Look

-   **Template Source:** `src/egregora/output_adapters/mkdocs/scaffolding.py`
-   **Configuration File:** `demo/.egregora/mkdocs.yml`
-   **Build Logs:** Output of `cd demo && uv run mkdocs build -f .egregora/mkdocs.yml`
