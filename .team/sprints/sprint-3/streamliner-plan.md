# Plan: Streamliner 🌊 - Sprint 3

**Persona:** Streamliner 🌊
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to support the "Symbiote Shift" by ensuring that the new Context Layer (Git History + Code References) scales to large repositories.

- [ ] **Vectorize `GitHistoryResolver`:** Transform the imperative "loop-over-commits" logic (prototyped in Sprint 2) into a batch processing pipeline.
- [ ] **Optimize `CodeReferenceDetector`:** Ensure the regex/parsing logic for code references is efficient and doesn't block the main thread.
- [ ] **Structured Sidecar Performance:** Ensure that the "Sidecar" data structure (ADR outcome) is designed for O(1) lookups and efficient updates.

## Dependencies
- **Visionary:** I need the prototypes for Git History and Code Refs from Sprint 2.
- **Steward:** I need the architectural definition of the "Structured Sidecar".

## Context
Sprint 3 introduces "Real-Time" context. Processing git history for every message or window can be incredibly slow if done naively. I must ensure we treat Git data as a massive dataset to be queried, not a log to be iterated.

## Expected Deliverables
1.  **High-Performance Git Resolver:** A Python module wrapping `git` (or using `pygit2` if approved) that handles batch resolution.
2.  **Performance Report:** Metrics on context resolution latency.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Git operations are I/O bound and slow | High | High | Implement aggressive caching (DuckDB) for immutable git objects (commits). |

## Proposed Collaborations
- **With Visionary:** Turning the prototype into production-grade code.
- **With Bolt:** Extending the benchmark suite to include Context Layer operations.
