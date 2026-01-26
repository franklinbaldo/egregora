# Plan: Builder - Sprint 2

**Persona:** Builder 🏗️
**Sprint:** 2
**Status:** In Progress
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to support the "Structure" sprint by finalizing the schema for the unified architecture and enabling new features like the Code Reference Detector.

- [ ] **Implement `git_cache` Schema:** Create a new table to support Visionary's Code Reference Detector (RFC 027). This table will map file paths and timestamps to commit SHAs.
- [x] **Indexing Strategy:** Add missing indexes to the `documents` table (`doc_type`, `slug`, `created_at`) in `src/egregora/database/init.py` to ensure query performance as the table grows.
- [ ] **Verify ContentRepository:** Run a verification script to confirm that the refactored `ContentRepository` correctly handles all document types and persistence in the unified `documents` table.
- [ ] **Audit Migrations:** Ensure the `migrate_documents_table` function is robust and handles the addition of new columns or constraints gracefully.

## Dependencies
- **Visionary:** I am unblocking their work by providing the `git_cache` schema.

## Context
Sprint 2 is about solidifying the foundation. A robust database schema with proper indexes and constraints is critical for the performance and integrity of the refactored pipeline.

## Expected Deliverables
1.  **New Table:** `git_cache` in `schemas.py` and `init.py`.
2.  **Optimized Schema:** `documents` table with indexes.
3.  **Verification Report:** Confirmation that `ContentRepository` works as expected.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Index creation slows down startup | Low | Low | DuckDB index creation is fast; we check `IF NOT EXISTS`. |
| Repository bugs | Medium | High | Integration verification script will catch issues before they affect the main pipeline. |

## Proposed Collaborations
- **With Visionary:** To finalize the columns needed for `git_cache`.
- **With Bolt:** To review index effectiveness.
