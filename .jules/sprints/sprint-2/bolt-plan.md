# Plan: Bolt ⚡ - Sprint 2

**Persona:** Bolt ⚡
**Sprint:** 2
**Created:** 2026-01-09 (during Sprint 1)
**Priority:** High

## Goals
My mission is to make the codebase faster, lighter, and more efficient. For Sprint 2, I will focus on identifying and optimizing the most significant performance bottlenecks in the data processing pipeline.

- [ ] **Profile the main `write` pipeline:** Conduct a thorough performance analysis of the `egregora write` command to identify the slowest operations from ingestion to output generation.
- [ ] **Investigate `get_opted_out_authors`:** This function performs file I/O and could be a bottleneck when the number of profiles grows. I will benchmark it and, if necessary, implement a caching or database-centric solution as hinted at in the source code.
- [ ] **Optimize media processing:** Analyze the performance of media handling, particularly the extraction and deduplication of media attachments.
- [ ] **Establish baseline benchmarks:** For any new area I investigate, I will create a new, permanent `pytest-benchmark` test to prevent future performance regressions.

## Dependencies
- **Refactor:** The Refactor persona's work on cleaning up the codebase might uncover or simplify areas that I can then optimize. I will monitor their progress.

## Context
My work in Sprint 1 successfully optimized the `sync_authors_from_posts` function, yielding a 1.6x speedup. This proves that significant gains can be found in I/O-bound operations. Sprint 2 will apply this same methodology to the broader data pipeline. The Visionary's proposed "Structured Data Sidecar" is on my radar, but I will wait for the technical specs before profiling it directly. My focus this sprint is on the existing, known code paths.

## Expected Deliverables
1.  **Pipeline Profile Report:** A journal entry detailing the performance profile of the `write` pipeline, with clear identification of the top 2-3 bottlenecks.
2.  **Optimized Code:** One or more pull requests with performance improvements for the identified bottlenecks.
3.  **New Benchmark Tests:** At least one new benchmark test added to the suite to cover a previously unmeasured area.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| No significant bottlenecks found | Low | Medium | The codebase is complex enough that there are almost certainly areas for improvement. If not, I will pivot to establishing more comprehensive benchmarks to safeguard against future regressions. |
| Optimization introduces subtle bugs | Medium | High | Adhere strictly to the **PROFILE → RED → GREEN → BENCHMARK** workflow. All changes will be validated against the existing correctness test suite. |
| Profiling tools are difficult to set up or inaccurate | Low | Medium | Start with `pytest-benchmark` which is already integrated. Use standard, well-documented tools like `cProfile` if deeper analysis is needed. |
