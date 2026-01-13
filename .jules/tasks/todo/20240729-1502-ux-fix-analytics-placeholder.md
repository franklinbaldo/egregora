---
id: "20240729-1502-ux-fix-analytics-placeholder"
title: "Remove or Fix Placeholder Google Analytics Key"
status: "todo"
author: "curator"
priority: "medium"
tags: ["#ux", "#privacy", "#bug"]
created: "2024-07-29"
---

## 🎭 Curator's Report: Remove or Fix Placeholder Google Analytics Key

### 🔴 RED: The Problem
The `mkdocs.yml` configuration contains a placeholder value for the Google Analytics property: `__GOOGLE_ANALYTICS_KEY__`. This represents a broken feature and is misleading. Egregora champions a privacy-first approach, and having a non-functional or placeholder analytics integration contradicts this principle. It clutters the configuration and could cause script errors in the browser.

### 🟢 GREEN: Definition of Done
- The `extra.analytics` section is completely removed from the default `mkdocs.yml` template.
- The generated `demo/.egregora/mkdocs.yml` file no longer contains the `analytics` configuration block.
- The feature should be implemented in a way that is explicitly opt-in, rather than being present by default with a broken key.

### 🔵 REFACTOR: How to Implement
1.  **Locate the Template:** The `mkdocs.yml` file is generated from a Jinja2 template located in `src/egregora/output_adapters/mkdocs/scaffolding.py`.
2.  **Remove the Configuration:** Find the section in the Jinja template that generates the `extra.analytics` block. Delete this entire section. Analytics should not be included by default. If a user wants to add it, they can do so manually. This aligns with a privacy-first and minimal-configuration philosophy.
3.  **Verify:** After your change, run `uv run egregora demo` to regenerate the demo site. Then, inspect the new `demo/.egregora/mkdocs.yml` and confirm that the `extra.analytics` block is no longer present.

### 📍 Where to Look
- **Template Source:** `src/egregora/output_adapters/mkdocs/scaffolding.py` (This is where the change must be made).
- **Configuration File (for verification):** `demo/.egregora/mkdocs.yml`