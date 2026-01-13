---
id: "20240729-1501-ux-fix-social-cards"
title: "Fix Broken Social Media Card Images (404s)"
status: "todo"
author: "curator"
priority: "high"
tags: ["#ux", "#bug", "#social", "#seo"]
created: "2024-07-29"
---

## 🎭 Curator's Report: Fix Broken Social Media Card Images

### 🔴 RED: The Problem
When the site is built, the build log is filled with 404 errors for social media card images (e.g., `https://example.com/assets/images/social/posts/index.png`). This means that when a link to the blog is shared on platforms like Twitter, Slack, or Facebook, it will appear without a preview image, looking unprofessional and reducing engagement. The root cause is a combination of a placeholder `site_url` and a likely misconfiguration of the `social` plugin.

### 🟢 GREEN: Definition of Done
- The `site_url` in `mkdocs.yml` is updated to a valid, non-placeholder URL. For local testing, `http://localhost:8000` is acceptable, but the template should be fixed to use a configurable value.
- The `social` plugin is correctly configured to generate images without causing 404 errors. This may involve specifying a default card or ensuring the generation path is correct.
- The `mkdocs build` command runs without any 404 errors related to social card images.

### 🔵 REFACTOR: How to Implement
1.  **Locate the Configuration:** The `site_url` and `plugins` are defined in `demo/.egregora/mkdocs.yml`.
2.  **Fix the Root Cause:** The `site_url` is a placeholder. This is the primary reason the links are broken. You must trace this back to the template that generates `mkdocs.yml` (`src/egregora/output_adapters/mkdocs/scaffolding.py`) and modify the Jinja template to use a configurable and valid URL. For the `demo` site specifically, you can hardcode a more realistic placeholder like `https://egregora.dev/demo`.
3.  **Configure Social Plugin:** Review the documentation for the `mkdocs-material` social card plugin. You may need to add a `card` or `cards_layout_options` section to the `theme` configuration to specify how cards are generated. A simple solution is to create a default social card image and configure the plugin to use it.
4.  **Verify:** Run `cd demo && uv run mkdocs build -f .egregora/mkdocs.yml`. The build log must be clean of any 404 errors for social card images.

### 📍 Where to Look
- **Configuration File:** `demo/.egregora/mkdocs.yml`
- **Template Source:** `src/egregora/output_adapters/mkdocs/scaffolding.py` (This is the most important place to fix the `site_url`).