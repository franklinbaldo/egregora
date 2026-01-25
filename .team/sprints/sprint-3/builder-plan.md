# Plan: Builder - Sprint 3

**Persona:** Builder (Data Architect)
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives

- [ ] **Advanced Vector Indexing:** Implement HNSW indexes for embedding columns in `documents` to support semantic search.
- [ ] **Data Retention & Archival:** Design and implement policies for moving old `messages` or `runs` to cold storage (e.g., Parquet files on S3/GCS) to keep the hot DuckDB database lean.
- [ ] **Performance Optimization:** Optimize the `_window_by_bytes` logic by pre-computing cumulative byte counts in the database (Fetch-then-Compute pattern).

## Dependencies

- **Curator:** Needs semantic search capabilities for better content discovery.
- **Forge:** Needs performant windowing for large document processing.

## Context

With the schema stable (V3 Pure) and lineage established (Sprint 2), Sprint 3 focuses on **Performance and Scale**. As the dataset grows, linear scans for windowing or search will become bottlenecks. We need to introduce proper indexing and data lifecycle management.

## Expected Deliverables

1.  **HNSW Index Migration:** Migration script to add vector indexes to `documents`.
2.  **Archival Service:** A service or script that moves data older than X days to external storage.
3.  **Windowing Optimization:** Refactored `Windowing` logic that leverages database-side aggregation where possible.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Index Build Time | Medium | Medium | Run index creation in background or during maintenance windows. |
| Data Loss during Archival | Low | High | Implement "Copy-Verify-Delete" protocol for archival. |

## Proposed Collaborations

- **With Curator:** Define the specific query patterns needed for semantic search (e.g., k-NN vs. range search).
