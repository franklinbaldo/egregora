# Plan: Streamliner - Sprint 2

**Persona:** Streamliner 🌊
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to eliminate imperative bottlenecks in the data processing pipeline, specifically focusing on windowing and the upcoming ETL extraction.

- [x] **Refactor `_window_by_bytes`:** Replace the imperative "scan loop" with a "Fetch-then-Compute" pattern using prefix sums and `bisect` for O(log N) efficiency and cleaner code. (Completed in Sprint 1/Early Sprint 2).
- [ ] **Audit `write.py` ETL:** Analyze the `write.py` pipeline (currently being refactored by Simplifier) to identify row-by-row operations that can be converted to vectorized Ibis expressions.
- [ ] **Benchmark `runner.py`:** Establish performance baselines for the orchestration runner before it is decomposed, ensuring we can measure regression/improvement.

## Dependencies
- **Simplifier:** I will work closely with Simplifier as they extract logic from `write.py` to ensure the new `pipelines/etl/` modules are vectorized by design.

## Context
The system uses imperative Python loops for data processing in several critical paths (`windowing`, `write.py` transformations). As we scale to larger chat histories, these loops will become bottlenecks. Transitioning to "Let the Database Do the Work" (Ibis/DuckDB) is essential.

## Expected Deliverables
1.  **Optimized `windowing.py`:** Code committed and verified.
2.  **Optimization Audit Report:** A section in `docs/data-processing-optimization.md` listing candidates for vectorization in the new ETL layer.
3.  **Benchmark Suite:** Scripts to measure pipeline throughput.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Simplifier's refactor changes logic | Medium | High | I will write tests for existing behavior before optimizing. |
| Performance regression | Low | High | Use `bench_windowing.py` and similar tools to verify every change. |

## Proposed Collaborations
- **With Simplifier:** Reviewing the new ETL structure.
