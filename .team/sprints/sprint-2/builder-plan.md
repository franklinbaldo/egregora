# Plan: Builder - Sprint 2

**Persona:** Builder (Data Architect)
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives

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

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| DuckDB Concurrency | Medium | High | Use the centralized `DuckDBStorageManager` for all writes. |
| Schema Evolution Conflicts | Low | Medium | Coordinate with other personas if they are adding new fields; use additive changes only. |

## Proposed Collaborations

- **With Curator:** Discuss if `RunStore` needs to track specific configuration parameters for reproducibility.
- **With Forge:** Ensure the `TaskStore` and `RunStore` APIs are ergonomic for the execution engine.
