# Plan: Artisan 🔨 - Sprint 3

**Persona:** Artisan 🔨
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High
**Reviewed:** 2026-01-26

## Objectives
My mission is to support the "Symbiote Shift" by ensuring the new Context Layer is built on a foundation of strict types and efficient protocols. I will also combine this with targeted performance optimizations and robustness improvements.

- [ ] **Protocol-First Context Layer:** Define strict `Protocols` for the new "Code Reference" and "Git History" components (introduced by Visionary). Ensure these components are decoupled and testable.
- [ ] **Performance Optimization:**
    - Optimize "hot paths" in the decomposed `runner` and `etl` pipelines (based on Bolt's Sprint 2 benchmarks).
    - Optimize `site_generator.py` using generator patterns to reduce memory usage during site generation.
- [ ] **Robust Error Handling:** Refactor `enricher.py` to standardize exception handling using custom exceptions in `src/egregora/agents/exceptions.py`, ensuring graceful degradation.
- [ ] **Strict Typing Coverage (80%):** Continue the crusade against `Any`. I will enforce `mypy --strict` on the entire `src/egregora/context_layer/` (or equivalent) directory and newly refactored components.

## Dependencies
- **Visionary:** I rely on the architectural vision for the Context Layer to define the right Protocols.
- **Bolt:** I need the benchmark results from Sprint 2 to know *where* to optimize in the runner/ETL.

## Context
Sprint 3 moves us from "Structure" to "Symbiosis". The system will start understanding its own code (Git History). My role is to ensure this new intelligence doesn't become a tangled mess. By enforcing Protocols early, we keep the "Context Layer" clean. Simultaneously, as we add "Discovery" features, keeping the build pipeline fast (via `site_generator` optimization) is crucial.

## Expected Deliverables
1.  **`src/egregora/protocols/context.py`**: New protocols defining the Context Layer contract.
2.  **Optimized Pipeline & Generator**: Measurable speedup in orchestration and reduced memory in site generation.
3.  **Robust `enricher.py`**: Standardized `try/except` blocks.
4.  **Strictly Typed Context Layer**: `mypy` passing with zero errors in new modules.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Over-abstraction with Protocols | Low | Medium | I will follow the "Rule of Three" before extracting a Protocol. |
| Optimization reduces readability | Medium | Medium | I will document optimizations heavily and use clear variable names. |
| Regression in Site Generation | Medium | High | Comprehensive regression testing comparing generated sites before and after optimization. |

## Proposed Collaborations
- **With Visionary:** Reviewing the `GitHistoryResolver` and defining its Protocol.
- **With Bolt:** Pair programming on optimization tasks.
