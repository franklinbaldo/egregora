# Plan: Artisan 🔨 - Sprint 3

**Persona:** Artisan 🔨
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission shifts to performance and robustness to support the "Mobile Polish & Discovery" themes.

- [ ] **Optimize `site_generator.py`:** The author indexing logic in `get_profiles_data` has potential performance bottlenecks. I will optimize this using generator patterns to reduce memory usage during site generation.
- [ ] **Refactor `enricher.py` Error Handling:** The enrichment agent has complex failure modes. I will standardize exception handling to ensure graceful degradation (e.g., when Jina fetches fail).
- [ ] **Performance Profiling:** Run a profiler on the full generation pipeline to identify other bottlenecks for large sites.

## Dependencies
- **None:** These tasks can be executed independently.

## Context
As we add "Discovery" features (Related Content), the build time will increase. Optimizing the core generator loops is essential to keep the developer experience fast.

## Expected Deliverables
1.  **Optimized `get_profiles_data`:** Measurable reduction in memory usage/time for profile generation.
2.  **Robust `enricher.py`:** Standardized `try/except` blocks using custom exceptions defined in `src/egregora/agents/exceptions.py`.
3.  **Profiling Report:** A report in `.team/reports/` identifying top 3 performance bottlenecks.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Regression in Site Generation | Medium | High | Comprehensive regression testing comparing generated sites before and after optimization. |
| API Rate Limits during Profiling | Low | Medium | Use mocked data for performance profiling to avoid hitting external APIs. |

## Proposed Collaborations
- **With Bolt:** Discuss potential async optimizations for IO-bound tasks identified during profiling.
