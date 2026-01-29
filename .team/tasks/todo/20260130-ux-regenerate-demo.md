---
title: "🎭 Regenerate Demo Site Artifacts"
date: 2026-01-30
author: "Curator"
emoji: "🎭"
type: task
tags:
  - ux
  - infrastructure
  - cleanup
---

## 🎭 Regenerate Demo Site Artifacts

**Observation:**
The `docs/demo` directory in the repository contains outdated configuration (e.g., legacy `custom.css`) and files that do not match the current templates (e.g., `extra.css` in `mkdocs.yml`). This staleness causes confusion when verifying the UX vision, as it masks the true state of the codebase.

**Objective:**
Force regeneration of the `docs/demo` directory to ensure it reflects the latest templates and configuration.

### 1. Cleanup and Regenerate
**Scenario: Force Fresh Generation**
*   **Given** the `docs/demo` directory contains checked-in artifacts
*   **When** the cleanup is performed
*   **Then** `docs/demo` should be deleted.
*   **And** `egregora demo -o docs/demo --no-enable-enrichment` should be run to regenerate it.
*   **And** the new artifacts (including the correct `mkdocs.yml` and `extra.css`) should be committed.
*   **And** any orphaned files (like `docs/stylesheets/custom.css` if it is no longer generated) should be removed from git.

### 2. Verification
**Scenario: Verify Configuration**
*   **Given** the regenerated `docs/demo`
*   **When** `docs/demo/.egregora/mkdocs.yml` is inspected
*   **Then** `extra_css` should point to `stylesheets/extra.css`, NOT `stylesheets/custom.css`.
