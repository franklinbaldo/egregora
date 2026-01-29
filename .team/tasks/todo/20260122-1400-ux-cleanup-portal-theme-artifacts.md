---
title: "🎭 Cleanup Portal Theme Artifacts"
date: 2026-01-22
author: "Curator"
emoji: "🎭"
type: task
---

## 🎭 Cleanup Portal Theme Artifacts

**Observation:**
The "Portal" theme scoping has been successfully implemented (via `index.md.jinja` frontmatter and CSS consolidation in `overrides`). However, the original shadowing CSS file `src/egregora/rendering/templates/site/docs/stylesheets/extra.css` still exists in the source tree. While it is not being copied to the generated site (making the site functionally correct), its presence in the source is confusing and represents technical debt.

**Context:**
We have moved away from global CSS overrides that shadow `docs/` files. All custom styles are now in `overrides/stylesheets/extra.css`. The file in `docs/stylesheets/extra.css` is orphaned.

**Objectives:**

### 1. Remove Orphaned CSS File
**Scenario: Clean Source Tree**
*   **Given** `src/egregora/rendering/templates/site/docs/stylesheets/extra.css` exists but is not used in the build
*   **When** we clean up the project
*   **Then** this file should be deleted.

**Action:**
*   Delete `src/egregora/rendering/templates/site/docs/stylesheets/extra.css`.

### 2. Verification
**Scenario: Verify No Regressions**
*   **Given** the file is deleted
*   **When** `egregora demo` is run
*   **Then** the generated site should still look correct (Portal theme active, no shadowing issues).
*   **And** `demo/docs/stylesheets/extra.css` should NOT exist (it didn't before, so this is just a sanity check).

**Verification:**
1.  Run `egregora demo`.
2.  Verify the site generates without errors.
3.  Confirm `src/egregora/rendering/templates/site/docs/stylesheets/extra.css` is gone.
