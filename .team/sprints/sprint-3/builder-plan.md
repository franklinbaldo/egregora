# Plan: Builder - Sprint 3

**Persona:** Builder 🏗️
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to prepare the data layer for the "Real-Time" pivot and the "Egregora Mesh" (Federation).

- [ ] **Vector Search Optimization:** Implement specialized HNSW indexes on `documents` (embeddings) to support efficient semantic search for the Context Layer.
- [ ] **Async Database Access:** Investigate and prototype an async adapter pattern for DuckDB (using `trio` if aligned with Bolt) to prevent blocking the event loop in real-time scenarios.
- [ ] **Federation Schema (Mesh):** Design the initial schema for peer discovery and context sharing (RFC 028), ensuring secure identity and trust handling.
- [ ] **Data Partitioning Strategy:** Evaluate partitioning strategies for `messages` and `documents` if volume grows significantly with real-time ingestion.

## Dependencies
- **Bolt:** Async framework decision (Trio vs. asyncio) dictates the DB adapter strategy.
- **Visionary:** "Mesh" requirements will drive the Federation schema.

## Context
Sprint 3 is about "Symbiote" - the shift from a static generator to a living, reactive system. The database must evolve from a passive storage bin to a high-performance query engine capable of vector search and non-blocking I/O.

## Expected Deliverables
1.  **HNSW Index Implementation:** SQL/Ibis code to create optimized vector indexes.
2.  **Async DB Prototype:** A proof-of-concept wrapper for async DuckDB queries.
3.  **Mesh Schema Draft:** Initial tables for `peers`, `trust_scores`, etc.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| DuckDB Async limitations | High | High | Investigate alternative backends (Postgres/SQLite) or robust thread-pooling early. |
| Vector Search Performance | Medium | Medium | Benchmark HNSW parameters (M, efConstruction) with realistic data sizes. |

## Proposed Collaborations
- **With Bolt:** Deep dive into Async I/O for database drivers.
- **With Visionary:** defining the "Mesh" protocol data structures.
