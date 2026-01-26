# Plan: Streamliner 🌊 - Sprint 2

**Persona:** Streamliner 🌊
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to support the "Structure & Polish" theme by ensuring the new architectural components (extracted ETL pipelines) are built for performance and to eliminate known bottlenecks.

- [ ] **Optimize Windowing Logic:** Complete the refactor of `_window_by_count` and `_window_by_bytes` to use the "Fetch-then-Compute" pattern, eliminating N+1 query issues.
- [ ] **Support ETL Decomposition:** Collaborate with Simplifier to ensure the new `src/egregora/orchestration/pipelines/etl/` modules are designed to support vectorized operations (Ibis/DuckDB) rather than row-by-row processing.
- [ ] **Performance Audit:** Conduct a focused audit of the new `write.py` and `runner.py` components as they are being refactored to catch performance regressions early.
- [ ] **Formalize Optimization Patterns:** Document the "Fetch-then-Compute" pattern and "Vectorized Operations" preference in a new ADR or updated documentation to guide future development.

## Dependencies
- **Simplifier:** I need to track their progress on extracting `etl/` modules to provide timely input on the structure.
- **Artisan:** Similar dependency for the `runner.py` refactor.

## Context
Sprint 2 is about paying down technical debt and improving structure. For me, this means fixing inefficient imperative loops (like the windowing logic) and ensuring the new structure doesn't introduce new ones.

## Expected Deliverables
1.  **Optimized Windowing Functions:** `_window_by_count` and `_window_by_bytes` running in O(1) query time (Fetch-then-Compute).
2.  **Performance Feedback:** Specific PR comments or commits to Simplifier's and Artisan's refactor branches.
3.  **Documentation:** Updated `docs/data-processing-optimization.md` or a new ADR.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Refactors introduce new bottlenecks | Medium | Medium | I will review the PRs for the refactors specifically looking for loop-based database access. |
| Windowing logic breaks edge cases | Low | High | I will ensure extensive unit tests cover edge cases (empty sets, single items, exact boundaries) before finalizing the optimization. |

## Proposed Collaborations
- **With Simplifier:** Reviewing the `etl` package design.
