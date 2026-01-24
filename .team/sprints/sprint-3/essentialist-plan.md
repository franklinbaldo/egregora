# Plan: Essentialist - Sprint 3

**Persona:** Essentialist 💎
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
Focus on simplifying the Agent interactions and data flow.

- [ ] **Simplify Agent Inputs:** Ensure agents receive simple DTOs/Pydantic models instead of complex runtime objects. "Data over logic".
- [ ] **Consolidate Output Sinks:** Review `OutputSink` protocol and implementations. If `MkDocsAdapter` is the only real one, consider simplifying the abstraction ("Interfaces over implementations" is good, but "Duplication over premature abstraction" warns against YAGNI).
- [ ] **Review Database Abstractions:** Check if `DuckDBStorageManager` and `Ibis` usage is consistent and efficient.

## Dependencies
- **Builder:** Alignment on data structures.

## Context
After stabilizing the pipeline orchestration in Sprint 2, the next layer of complexity is the data flow between the pipeline and the agents/storage.

## Expected Deliverables
1.  Simplified Agent signatures.
2.  Review and potential simplification of `OutputSink`.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Over-simplification | Low | Medium | Ensure extensibility points remain where actually needed (e.g. for future different output formats). |
