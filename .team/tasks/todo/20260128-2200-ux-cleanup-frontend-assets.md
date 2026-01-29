---
title: "🎭 Cleanup Frontend Assets"
date: 2026-01-28
author: "Curator"
emoji: "🎭"
type: task
---

## 🎭 Cleanup Frontend Assets

**Observation:**
During an audit of the `demo` site output, we discovered a file named `test.txt` in the `overrides/stylesheets` directory. Additionally, a `favicon.png` file exists in the same directory, but the site configuration (`mkdocs.yml`) points to `assets/images/favicon.svg`. These files appear to be leftovers from development and should be removed to maintain a professional codebase.

**Context:**
-   `src/egregora/rendering/templates/site/overrides/stylesheets/test.txt`: Likely a debug artifact.
-   `src/egregora/rendering/templates/site/overrides/stylesheets/favicon.png`: Likely unused (replaced by SVG).

**Objectives:**

### 1. Delete Artifacts
**Scenario: Remove Garbage Files**
*   **Given** `test.txt` and `favicon.png` exist in `overrides/stylesheets`
*   **When** we run the cleanup task
*   **Then** these files should be deleted.

**Action:**
*   Delete `src/egregora/rendering/templates/site/overrides/stylesheets/test.txt`.
*   Delete `src/egregora/rendering/templates/site/overrides/stylesheets/favicon.png`.

### 2. Verification
**Scenario: Clean Build**
*   **Given** the files are deleted
*   **When** `egregora demo` is run
*   **Then** the `demo/overrides/stylesheets/` directory should NOT contain `test.txt` or `favicon.png`.
*   **And** the site icon should still load correctly (from `assets/images/favicon.svg`).

**Verification:**
1.  Run `egregora demo`.
2.  Check `demo/overrides/stylesheets/` content.
3.  Serve the site and ensure the favicon still appears in the browser tab.
