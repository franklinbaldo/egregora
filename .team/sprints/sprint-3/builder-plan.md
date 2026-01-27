<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
# Plan: Builder 🏗️ - Sprint 3
=======
# Plan: Builder - Sprint 3
>>>>>>> origin/pr/2901
=======
# Plan: Builder - Sprint 3
>>>>>>> origin/pr/2860

**Persona:** Builder 🏗️
**Sprint:** 3
**Created:** 2026-01-26
<<<<<<< HEAD
<<<<<<< HEAD
=======
# Plan: Builder - Sprint 3

**Persona:** Builder (Data Architect)
**Sprint:** 3
**Created:** 2026-01-26
>>>>>>> origin/pr/2841
**Priority:** Medium

## Objectives

<<<<<<< HEAD
My mission is to support the "Symbiote Shift" by enabling the storage of deep context and self-reflection data.

- [ ] **"Structured Sidecar" Schema:** Formalize the data model for "Structured Sidecars" (metadata accompanying source files) as defined by the Visionary.
- [ ] **Autopoiesis Data Support:** Create schemas to store agent "Self-Correction" logs (Critique -> Action -> Outcome) to enable the feedback loop.
- [ ] **Advanced Git Context:** Expand the Git schema to support finer-grained code references (potentially AST-level symbols) if required.

## Dependencies

- **Visionary:** Requirements for the "Structured Sidecar" and "Autopoiesis" loops.
- **Meta:** Requirements for storing system introspection data.

## Context

Sprint 3 is about the agent becoming a "Symbiote" that lives alongside the code. The database must evolve from a passive store of documents to an active memory of the codebase's history and the agent's own thought processes.

## Expected Deliverables

1.  **Sidecar Schema:** Definitions for storing/indexing sidecar data.
2.  **Feedback Loop Tables:** Schema for storing `agent_critiques` and `agent_actions`.
3.  **Expanded Git Schema:** If needed, tables for `code_symbols` linked to Git refs.
=======
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
>>>>>>> origin/pr/2841

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
| Schema complexity explosion | Medium | High | Maintain the "Structure Before Scale" philosophy. Only add tables that are strictly necessary and enforce them with constraints. |

## Proposed Collaborations

- **With Visionary:** Deep collaboration on the Symbiote data model.
- **With Meta:** On storing introspection data.
=======
**Priority:** High

## Objectives
My mission is to prepare the data layer for "Real-Time" and "Discovery" workloads, moving towards a unified "Pure DuckDB" architecture.

- [ ] **RAG Unification Strategy:** Investigate and propose migrating vector storage from LanceDB to DuckDB (`vss` extension). This would consolidate our "State" into a single file, greatly simplifying the "Symbiote" architecture.
- [ ] **Optimize for Real-Time:** Work with Bolt to tune DuckDB for higher concurrency (e.g., WAL configuration, batching strategies) to support the "Real-Time Adapter Framework".
- [ ] **Universal Context Schema:** Design the schema extensions needed for the Universal Context Layer API (RFC 026), potentially including API key management or session tracking if not stateless.

## Dependencies
- **Bolt:** I need their load testing results to know where to tune.
- **Visionary:** I need the RAG requirements to evaluate if DuckDB `vss` is performant enough.

## Context
Sprint 3 moves from "Structure" to "Capability". The database must support vector search (for Discovery) and real-time ingestion (for the Adapter Framework). Unifying the vector store into the main DB is a high-leverage move if feasible.

## Expected Deliverables
1.  **Architecture Decision:** "DuckDB VSS vs LanceDB" (likely an ADR).
2.  **Optimized Config:** Tuned `DuckDB` connection settings.
3.  **Schema Extensions:** For Context Layer API.
=======
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
>>>>>>> origin/pr/2860

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
| DuckDB VSS performance is poor | Medium | High | Benchmark early. If poor, we stick with LanceDB but document it as an explicit "Sidecar". |
| Real-Time writes lock the DB | High | High | Investigate `IMMEDIATE` vs `DEFERRED` transaction modes and potential use of an ingestion buffer (which we already have in `messages` table). |
>>>>>>> origin/pr/2901
=======
| Vector Index overhead | Medium | Medium | We will use HNSW indexes which are efficient, but verify storage impact. |
| Schema Migration Complexity | Medium | High | We will use the established "Create-Copy-Swap" pattern to safely add the embedding column. |

## Proposed Collaborations
- **With Bolt:** Performance tuning for real-time.
- **With Visionary:** Embedding schema definition.
>>>>>>> origin/pr/2860
=======
| Index Build Time | Medium | Medium | Run index creation in background or during maintenance windows. |
| Data Loss during Archival | Low | High | Implement "Copy-Verify-Delete" protocol for archival. |

## Proposed Collaborations

- **With Curator:** Define the specific query patterns needed for semantic search (e.g., k-NN vs. range search).
>>>>>>> origin/pr/2841
