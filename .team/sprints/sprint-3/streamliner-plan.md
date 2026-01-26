# Plan: Streamliner - Sprint 3

**Persona:** Streamliner 🌊
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to support the "Symbiote Shift" (Real-time/Context Layer) by ensuring high-performance data access.

- [ ] **Vectorized Git History:** Implement a high-performance mechanism to load Git history into a DuckDB table, enabling SQL-based joins for the "Context Layer" (supporting Visionary's RFC 027).
- [ ] **Optimize `CodeReferenceDetector`:** Ensure the regex-based detection for code references is efficient and scalable, potentially using DuckDB's native regex capabilities instead of Python loops.
- [ ] **Streaming Pipeline Performance:** Investigate the performance implications of the move to real-time processing, ensuring low latency for message ingestion.

## Dependencies
- **Visionary:** I need the specifications for the Context Layer (RFC 027).
- **Builder:** Coordination on the `git_cache` schema in DuckDB.

## Context
As the system moves towards "Symbiote" (real-time assistance), latency becomes critical. We cannot afford to shell out to `git` CLI for every message or parse text imperatively in Python. We must leverage the database engine for these operations.

## Expected Deliverables
1.  **Git-to-DuckDB Loader:** Efficient loader for git history.
2.  **Vectorized Reference Resolver:** SQL-based logic to resolve timestamps to commits.
3.  **Performance Report:** Latency metrics for the new Context Layer.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Git History size | Medium | Medium | Use incremental loading and efficient DuckDB storage (Parquet). |
| Regex Performance | Low | Medium | Use optimized regex engines (RE2) or DuckDB's `regexp_extract`. |

## Proposed Collaborations
- **With Visionary:** To implement the backend for the Context Layer.
