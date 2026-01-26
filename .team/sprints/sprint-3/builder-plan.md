# Plan: Builder - Sprint 3

**Persona:** Builder 🏗️
**Sprint:** 3
**Created:** 2026-01-26
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

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| DuckDB VSS performance is poor | Medium | High | Benchmark early. If poor, we stick with LanceDB but document it as an explicit "Sidecar". |
| Real-Time writes lock the DB | High | High | Investigate `IMMEDIATE` vs `DEFERRED` transaction modes and potential use of an ingestion buffer (which we already have in `messages` table). |
