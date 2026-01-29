---
title: "🎭 Fix Relative Links on Feeds Page"
date: 2026-01-30
author: "Curator"
emoji: "🎭"
type: task
tags:
  - ux
  - frontend
  - bugfix
---

## 🎭 Fix Relative Links on Feeds Page

**Observation:**
The RSS/JSON feed links in `src/egregora/rendering/templates/site/docs/feeds/index.md.jinja` are hardcoded as absolute paths (e.g., `/feed_rss_created.xml`). This breaks link resolution when the site is deployed to a subpath (e.g., GitHub Pages).

**Objective:**
Ensure links to RSS/JSON feeds use relative paths (`../`) to support subpath deployments.

### 1. Fix Links
**Scenario: Use Relative Paths**
*   **Given** `src/egregora/rendering/templates/site/docs/feeds/index.md.jinja` contains links like `/feed_rss_created.xml`
*   **When** the fix is applied
*   **Then** the links should be changed to `../feed_rss_created.xml` (relative to `feeds/` directory).
    *   *Note:* The feed files are generated at the site root. The `feeds/index.html` page is in the `feeds/` subdirectory. Therefore, `../` is the correct traversal.

### 2. Verification
**Scenario: Verify Links in Demo**
*   **Given** the site is regenerated
*   **When** the Feeds page (`/feeds/`) is inspected
*   **Then** the "Subscribe" buttons should link to `./../feed_rss_created.xml` (or equivalent relative path) rather than the domain root.
