---
title: "🎨 Feature Parity for Blog Template"
date: 2024-07-29
author: "Palette"
emoji: "🎨"
type: journal
---

## 🎨 2024-07-29 - Summary

**Observation:** I identified a functional inconsistency between the project's main documentation site and the theme for user-generated blogs. The root `mkdocs.yml` enabled `pymdownx.arithmatex` for rendering mathematical formulas, but this was missing from the blog template in `src/egregora/rendering/templates/site/mkdocs.yml.jinja`.

**Action:** I updated the `mkdocs.yml.jinja` template to include the missing `pymdownx.arithmatex` markdown extension. This ensures a consistent, high-quality user experience across all generated sites.

**Reflection:** The project's design system is maturing, but a more robust inheritance model for configuration is needed. The root and template configurations are managed in separate files, which has led to drift. A future improvement would be to establish a single source of truth for the MkDocs configuration, perhaps using MkDocs' built-in inheritance (`!include`) or a shared YAML file, to ensure that both the documentation and user blogs inherit from the same base. This would prevent future inconsistencies and strengthen the design system.
