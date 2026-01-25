# Plan: Bolt - Sprint 2

**Persona:** Bolt ⚡
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to ensure the major refactors (Runner/Write pipeline) do not degrade performance, and to prepare the system for the "Real-Time" pivot.

- [ ] **Baseline Profiling:** Create a comprehensive benchmark suite for the current `write` pipeline (before Simplifier/Artisan refactors land) to detect regressions.
- [ ] **Ibis/DuckDB Optimization:** Audit `src/egregora/transformations/` for N+1 query patterns and optimize them using vectorized operations.
- [ ] **Cache Strategy:** Implement a caching strategy for "Social Card" generation (dependent on Forge's work) to prevent re-generation of static assets.
- [ ] **Review Refactors:** Actively review PRs from Simplifier and Artisan with a focus on import overhead and initialization latency.

## Dependencies
- **Simplifier/Artisan:** I need to coordinate with their refactors to ensure my benchmarks remain valid or are updated.
- **Forge:** My caching work depends on their implementation of social cards.

## Context
Sprint 2 is a "Refactor Sprint" for others. For me, it is a "Defense Sprint". I must ensure that cleaner code doesn't become slower code. Additionally, I will optimize the data layer to support the future real-time requirements.

## Expected Deliverables
1.  **Pipeline Benchmark Suite:** A new set of `pytest-benchmark` tests for the full pipeline.
2.  **Optimized Queries:** PRs to fix inefficient Ibis expressions.
3.  **Caching Logic:** Decorators or utility functions for asset caching.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Refactors break benchmarks | High | Medium | I will create modular benchmarks that test components (ETL, Windowing) in isolation, not just the full pipeline. |
| Social Card generation is too slow | Medium | High | I will enforce incremental generation (hashing) as a requirement for Forge's PR. |
