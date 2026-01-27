<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
# Plan: Builder 🏗️ - Sprint 2
=======
# Plan: Builder - Sprint 2
>>>>>>> origin/pr/2901

**Persona:** Builder 🏗️
**Sprint:** 2
=======
# Plan: Builder - Sprint 2

**Persona:** Builder 🏗️
**Sprint:** 2
**Status:** In Progress
>>>>>>> origin/pr/2860
=======
# Plan: Builder - Sprint 2

**Persona:** Builder (Data Architect)
**Sprint:** 2
>>>>>>> origin/pr/2841
**Created:** 2026-01-26
**Priority:** High

## Objectives
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD

My mission is to provide the data foundation for the new "Context Layer" and ensure the "Batch Era" pipeline remains performant during its refactor.

- [ ] **Implement Git Context Schema:** Design and implement the database schema (`git_commits`, `git_refs`) to support Visionary's "Time Machine" capabilities (RFC 027).
- [ ] **Optimize for Read Performance:** Collaborate with Bolt to identify and implement necessary indexes on the unified `documents` table to eliminate N+1 query bottlenecks.
- [ ] **Support Pipeline Refactor:** Assist Simplifier and Artisan in ensuring their new "ETL" and "Runner" modules interact correctly with the `documents` table, avoiding legacy table usage.
- [ ] **Enforce Strictness:** Ensure all new schemas (Git, Sidecars) launch with comprehensive `CHECK` constraints and Foreign Keys from Day 1.

## Dependencies

- **Visionary:** I need the specific query patterns for the Git Context layer to design the optimal schema (Key-Value vs. Relational).
- **Bolt:** I rely on Bolt's profiling to identify which specific columns need indexing.

## Context

Sprint 2 is "Structure & Polish". While others are refactoring code, I am expanding the data model to include "Time" (Git History). This is a critical enabler for the "Symbiote Shift" in Sprint 3. I am also acting as a guardian to ensure the "Pure" V3 architecture isn't violated during the massive refactors of `write.py` and `runner.py`.

## Expected Deliverables

1.  **New Schemas:** `GIT_COMMITS_SCHEMA` and `GIT_REFS_SCHEMA` in `src/egregora/database/schemas.py`.
2.  **Migration Script:** Migration to create the new Git tables.
3.  **Indexes:** `create_index` calls added to `init.py` for high-traffic columns identified by Bolt.
4.  **Updated Documentation:** `docs/schema-evolution-plan.md` updated with the Git Context layer details.
=======

- [ ] **Implement RunStore in DuckDB:** Replace the placeholder `RunStore` with a persistent DuckDB implementation to track pipeline execution metadata (start/end time, config hash, status).
- [ ] **Audit and Enforce Foreign Keys:** Ensure `annotations` table strictly references `documents(id)` via database-level FK constraints.
- [ ] **Data Lineage Foundations:** Ensure all new records in `documents` and `messages` can be traced back to a specific `run_id` (requires `RunStore`).

## Dependencies

- **Orchestrator/TaskMaster:** Will need to integrate with the new `RunStore` API.
- **Writer/Enricher:** Will need to pass `run_id` context when creating documents.

## Context

We have successfully migrated to the V3 "Pure" architecture with a unified `documents` table. The next critical layer of structural integrity is **Lineage**. We need to know *when* and *by what process* every piece of data was created. This requires a persistent `RunStore`. Additionally, we need to tighten the relational integrity between secondary tables (like `annotations`) and the core `documents` table.

## Expected Deliverables

1.  **`src/egregora/database/run_store.py`**: Fully implemented class with `start_run()`, `end_run()`, `get_run()` methods backed by a `runs` table in DuckDB.
2.  **`src/egregora/database/schemas.py`**: Updated `RUNS_SCHEMA` definition.
3.  **Migration Script**: Logic to create the `runs` table if it doesn't exist.
4.  **Foreign Key Verification**: Tests confirming `annotations` cannot point to non-existent documents.
>>>>>>> origin/pr/2841

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
| Git Cache grows too large | Medium | Medium | Implement specific "Time To Live" (TTL) or "Least Recently Used" (LRU) eviction policies in the schema design (e.g., `last_accessed` column). |
| Refactors bypass `documents` table | Medium | High | I will review Simplifier's and Artisan's PRs to check for legacy table usage. |

## Proposed Collaborations

- **With Visionary:** To finalize the `git_cache` schema.
- **With Bolt:** To review query plans and apply indexes.
- **With Simplifier:** To guide data access patterns in the new ETL module.
=======
My mission is to support the "Structure" sprint by providing the necessary data schemas for the new Context Layer features while maintaining strict data integrity.

- [ ] **Implement `git_commits` Schema:** Create a new table to cache git commit history, supporting Visionary's `GitHistoryResolver`. This will allow fast "What was the SHA of this file at time T?" queries.
- [ ] **Enforce Schema Hygiene:** Remove unused legacy schema definitions (e.g., `MEDIA_SCHEMA`) to prevent confusion during the Refactor persona's work.
- [ ] **Verify Unified Constraints:** Continuously monitor the `documents` table usage to ensure the new conditional constraints are working as intended.

## Dependencies
- **Visionary:** My `git_commits` table is a direct dependency for their `GitHistoryResolver`.

## Context
Sprint 2 is about laying the foundation. The `git_commits` table is a key piece of infrastructure for the "Universal Context" vision. It effectively turns our database into a "Time Machine" for code references.

## Expected Deliverables
1.  **New Table:** `git_commits` in `src/egregora/database/schemas.py` and `init.py`.
2.  **Migration:** (Implicit) New databases will include this table.
3.  **Clean Code:** Removal of dead schema code.
=======
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
>>>>>>> origin/pr/2860

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
| Index overhead on `git_commits` | Low | Medium | I will ensure the index is optimized for the specific access pattern `(path, timestamp DESC)`. |

## Proposed Collaborations
- **With Visionary:** To confirm the exact columns needed for the Git History Resolver.
>>>>>>> origin/pr/2901
=======
| Index creation slows down startup | Low | Low | DuckDB index creation is fast; we check `IF NOT EXISTS`. |
| Repository bugs | Medium | High | Integration verification script will catch issues before they affect the main pipeline. |

## Proposed Collaborations
- **With Visionary:** To finalize the columns needed for `git_cache`.
- **With Bolt:** To review index effectiveness.
>>>>>>> origin/pr/2860
=======
| DuckDB Concurrency | Medium | High | Use the centralized `DuckDBStorageManager` for all writes. |
| Schema Evolution Conflicts | Low | Medium | Coordinate with other personas if they are adding new fields; use additive changes only. |

## Proposed Collaborations

- **With Curator:** Discuss if `RunStore` needs to track specific configuration parameters for reproducibility.
- **With Forge:** Ensure the `TaskStore` and `RunStore` APIs are ergonomic for the execution engine.
>>>>>>> origin/pr/2841
