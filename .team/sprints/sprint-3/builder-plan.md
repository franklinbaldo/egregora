# Plan: Builder - Sprint 3

**Persona:** Builder 🏗️
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to evolve the schema to support "Discovery" (Vector Search) and "Real-Time" requirements.

- [ ] **Vector Search Schema:** Add `embedding` column (array of floats) and HNSW index to the `documents` table to enable "Related Content" features.
- [ ] **Real-Time Database Support:** Collaborate with Bolt to audit the `messages` table and `input_adapters` for async safety and high-throughput stream ingestion.
- [ ] **Schema Evolution for Discovery:** Design and implement any additional schema changes needed for the "Context Layer" API (e.g., tagging, relationships).
- [ ] **Clean Up Legacy Artifacts:** Assist Absolutist in removing any database-level legacy supports (like the `media` table migration code) once confirmed obsolete.

## Dependencies
- **Bolt:** I need their input on the async data access patterns.
- **Visionary/Curator:** I need the embedding dimensions (e.g., 768 for Gemini/Vertex) to define the schema correctly.

## Context
Sprint 3 introduces "Discovery", which relies on vector embeddings. This requires a schema update to support vector operations in DuckDB/Ibis. Additionally, the move to "Real-Time" requires a check on our ingestion buffer schema.

## Expected Deliverables
1.  **Vector Schema:** `documents` table updated with `embedding` column and index.
2.  **Async-Ready Schema:** Confirmation or updates to `messages` table for stream processing.
3.  **Cleaned Codebase:** Removal of obsolete migration logic.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Vector Index overhead | Medium | Medium | We will use HNSW indexes which are efficient, but verify storage impact. |
| Schema Migration Complexity | Medium | High | We will use the established "Create-Copy-Swap" pattern to safely add the embedding column. |

## Proposed Collaborations
- **With Bolt:** Performance tuning for real-time.
- **With Visionary:** Embedding schema definition.
