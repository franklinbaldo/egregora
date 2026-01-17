# Refactor Knowledge Profiles Module

**Status:** TODO
**Priority:** Medium
**Created:** 2026-01-16
**Persona:** Refactor

## Context
The `src/egregora/knowledge/profiles.py` module contains logic for managing author profiles, but it has accumulated some technical debt. Several areas show duplicated logic, fragile parsing, and mixed responsibilities.

## Identified Issues

1.  **Fragile Frontmatter Parsing**
    -   **Location:** `src/egregora/knowledge/profiles.py` around line 717 (`_parse_frontmatter`).
    -   **Issue:** The code manually splits strings to extract YAML frontmatter. This is brittle and inconsistent with other parts of the codebase that use the `frontmatter` library.
    -   **Task:** Replace manual parsing with `python-frontmatter` (or `frontmatter` lib) for robustness and consistency.

2.  **Duplicated Avatar Logic**
    -   **Location:** `src/egregora/knowledge/profiles.py` around lines 598 (`update_profile_avatar`) and `remove_profile_avatar`.
    -   **Issue:** Both functions share significant logic for reading, parsing, modifying, and saving profile files.
    -   **Task:** Consolidate the shared logic into a helper function (e.g., `_modify_profile_metadata`) that accepts the modification logic as a callback or parameter.

3.  **Complex Sync Logic**
    -   **Location:** `src/egregora/knowledge/profiles.py` inside `sync_all_profiles` (around line 1004).
    -   **Issue:** The function iterates over directories and contains inline logic for processing each author, making the function long and harder to test.
    -   **Task:** Extract the logic for syncing a single author into a `_sync_single_author` helper method.

4.  **Fragile Active Authors Query**
    -   **Location:** `src/egregora/knowledge/profiles.py` around line 132 (`get_active_authors`).
    -   **Issue:** The function handles multiple potential return types from `ibis` execution (`pandas.DataFrame`, `pandas.Series`, `list`, `numpy.array`) in a brittle `if/elif` chain.
    -   **Task:** Investigate the `ibis` return types and refactor this to be more deterministic or strictly typed.

## Definition of Done
- All identified refactoring tasks are completed.
- Existing tests pass.
- New helper functions are covered by tests if applicable.
- Code is cleaner and more maintainable.
