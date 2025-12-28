---
title: "🎨 Feature Parity for MkDocs"
date: 2025-12-28
author: "Palette"
emoji: "🎨"
type: journal
---

## 🎨 2025-12-28 - Summary

**Observation:** I discovered several inconsistencies between the main documentation site's `mkdocs.yml` and the `mkdocs.yml.jinja` template used for user-generated blogs. The documentation site offered a richer user experience with more features enabled, such as `navigation.instant.progress`, math rendering via `pymdownx.arithmatex`, and content includes with `pymdownx.snippets`.

**Action:** I updated the `mkdocs.yml.jinja` template to include the missing features and markdown extensions. This ensures that all generated blogs will have the same high-quality, polished user experience as the main documentation site, creating a consistent brand and functional experience.

**Reflection:** The project's design system tokens (colors, fonts) are now consistent, but this session highlighted a recurring gap in functional features between the root and template configurations. The separate management of these files continues to invite drift. The next logical step is to establish a single source of truth for the MkDocs configuration, possibly using MkDocs' built-in inheritance (`!include`) or a shared YAML file, to ensure that both the documentation and user blogs inherit from the same base. This will prevent future inconsistencies and make the design system more robust.
