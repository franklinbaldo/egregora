---
id: "20240729-1500-ux-fix-navigation"
title: "Fix Missing and Broken Navigation Links"
status: "todo"
author: "curator"
priority: "high"
tags: ["#ux", "#bug", "#navigation"]
created: "2024-07-29"
---

## 🎭 Curator's Report: Fix Missing and Broken Navigation Links

### 🔴 RED: The Problem
The main site navigation is incomplete and misleading. The build logs clearly show that the `Journal` and `Profiles` sections exist but are not included in the top-level navigation. Additionally, the "Media" link points to a page with broken relative links. This creates a confusing and broken user experience.

### 🟢 GREEN: Definition of Done
- The `Journal` and `Profiles` sections are added to the main navigation in `mkdocs.yml`.
- The navigation hierarchy is logical and easy for users to understand.
- The broken links on the `posts/media/index.md` page are fixed or the page is updated to reflect the correct content structure.
- The `mkdocs build` command runs without any warnings related to navigation or unrecognized links on the media page.

### 🔵 REFACTOR: How to Implement
1.  **Locate the `nav` configuration:** The navigation is defined in the `nav:` section of `demo/.egregora/mkdocs.yml`.
2.  **Update the Navigation:** Add entries for `Journal` (pointing to `journal/index.md`) and `Profiles` (pointing to `posts/profiles/index.md`). Consider a logical grouping, perhaps placing `Profiles` under the `Blog` section.
3.  **Investigate Media Page:** Examine `demo/docs/posts/media/index.md`. The warnings suggest it contains links like `images/` and `videos/`. These directories do not exist. You must either:
    - Create the necessary directories and placeholder files.
    - Or, more likely, correct the markdown content on that page to not link to non-existent locations.
4.  **Verify:** Run `cd demo && uv run mkdocs build -f .egregora/mkdocs.yml` and ensure there are no more warnings about missing navigation or broken relative links.

### 📍 Where to Look
- **Configuration File:** `demo/.egregora/mkdocs.yml`
- **Content File:** `demo/docs/posts/media/index.md`
- **Template Source (if needed):** The `mkdocs.yml` is generated from a template in `src/egregora/output_adapters/mkdocs/scaffolding.py`. The root cause may be in the Jinja template that generates the `nav` section. Please investigate and fix the source.