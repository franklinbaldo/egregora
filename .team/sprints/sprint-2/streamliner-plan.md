# Plan: Streamliner - Sprint 2

<<<<<<< HEAD
**Persona:** Streamliner
**Sprint:** 2
**Created on:** 2026-01-07
**Priority:** High

## Goals

Describe the main goals for this sprint:

- [ ] Profile the full `egregora` pipeline to identify new performance bottlenecks.
- [ ] Investigate `src/egregora/transformations/enrichment.py` for potential vectorization opportunities.
- [ ] Optimize any remaining iterative metadata queries in the orchestration layer.

## Dependencies

List work dependencies from other personas:

- **None** currently identified.

## Context

Explain the context and reasoning behind this plan:

During Sprint 1, I successfully optimized the `_window_by_bytes` function, achieving a ~16x speedup. The windowing module is now largely optimized (count, time, and bytes). The next logical step is to move upstream to the enrichment phase or downstream to the formatting phase to find similar inefficiencies.

## Expected Deliverables

1. **Profiling Report:** A document detailing the performance profile of the main pipeline.
2. **Optimization Plan:** An updated `docs/data-processing-optimization.md` with new targets.
3. **Refactored Enrichment:** If inefficiencies are found, initial refactoring of `enrichment.py`.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| No obvious bottlenecks found | Low | Medium | Focus on micro-optimizations or database configuration (DuckDB tuning). |

## Proposed Collaborations

- **With Bolt:** Coordinate on overall system latency measurements.

## Additional Notes

Focus remains on "Calculate, Don't Iterate".
=======
**Persona:** Streamliner 🌊
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My focus is on ensuring the major refactors in progress do not degrade data processing performance, while continuing targeted optimizations.

- [ ] **Enricher Optimization:** Audit and optimize `src/egregora/agents/enricher.py` to ensure batch processing is truly vectorized and minimizes API round-trips.
- [ ] **Refactor Review:** Review Simplifier's `write.py` refactor to prevent data path regressions.
- [ ] **Documentation:** Update `docs/data-processing-optimization.md` with new findings and benchmarks.

## Dependencies
- **Simplifier:** My review work depends on their PRs.
- **Bolt:** Coordination on performance benchmarks.

## Context
With `windowing.py` optimized in Sprint 1, the next bottleneck is likely the Enrichment phase, which involves external API calls. Optimizing how we batch these calls and handle the data flow is critical.

## Expected Deliverables
1.  **Enricher Optimization PR:** Improvements to `Enricher` class if inefficiencies are found.
2.  **Review Comments:** On Simplifier's PRs.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| API Latency masking code perf | High | Medium | Use mocks for API calls to measure pure code overhead. |
>>>>>>> origin/pr/2836
