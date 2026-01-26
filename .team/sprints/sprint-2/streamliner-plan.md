# Plan: Streamliner 🌊 - Sprint 2

**Persona:** Streamliner 🌊
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to ensure that the structural refactoring of the "Batch Era" pipelines results in a performant foundation for the future.

- [ ] **Optimize `EnrichmentWorker`:** Analyze `src/egregora/agents/enricher.py` for imperative patterns in API request handling and response processing.
- [ ] **Ibis Best Practices Guide:** Create `docs/ibis-best-practices.md` to guide **Simplifier** and **Artisan** in writing efficient, declarative queries during their refactors.
- [ ] **Profiling Support:** Collaborate with **Bolt** to interpret benchmark results for the decomposed `write.py` pipeline and identify bottlenecks.
- [ ] **Review Decomposed Pipelines:** Review PRs for `runner.py` and `etl/` specifically to catch N+1 query regressions before merge.

## Dependencies
- **Simplifier & Artisan:** I cannot profile the new pipeline structure until their refactors are at least drafted.
- **Bolt:** I rely on Bolt's benchmark suite to provide baseline metrics.

## Context
Sprint 2 is a critical transition. As code moves from monolithic scripts to modular components, there is a risk of introducing "abstraction overhead" (e.g., fetching data in each small component instead of once in bulk). My role is to prevent this.

## Expected Deliverables
1.  **Optimized `enricher.py`:** PR with vectorized or async improvements.
2.  **`docs/ibis-best-practices.md`:** A guide for the team.
3.  **Review Comments:** Actionable feedback on performance in refactor PRs.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Abstraction layers hide N+1 queries | High | High | I will advocate for "Fetch-then-Compute" patterns in the new architecture, passing data *into* components rather than having them fetch it. |
| Bolt and I duplicate work | Medium | Low | We have established a boundary: Bolt focuses on Metrics/Caching, I focus on Query Optimization/Vectorization. |

## Proposed Collaborations
- **With Bolt:** Joint analysis of benchmark regressions.
- **With Artisan:** Pairing on the data access layer of `runner.py`.
