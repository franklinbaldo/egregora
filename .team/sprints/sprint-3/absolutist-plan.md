# Plan: Absolutist - Sprint 3

**Persona:** Absolutist 💯
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
Continue the purification of the codebase.

- [ ] **Address CLI Compatibility Layers:** Investigate `src/egregora/cli/main.py` comments regarding "DuckDBStorageManager directly to ensure Ibis compatibility". If the underlying issue is resolved, remove the workaround.
- [ ] **Deep Clean of `input_adapters`:** Check `src/egregora/input_adapters/base.py` for "Note: This is the only adapter interface. The legacy InputSource has been removed." and ensure no artifacts remain.
- [ ] **Review `output_adapters` conventions:** Check for any remaining version tracking or migration compatibility code.

## Dependencies
- **Simplifier:** Changes to orchestration might affect CLI compatibility needs.

## Context
By Sprint 3, the major architectural migrations (OutputSink, Pipeline setup) should be complete. The focus shifts to subtler workarounds and comments that may no longer be true.

## Expected Deliverables
1.  Refactored CLI database initialization (if possible).
2.  Verified removal of `InputSource` legacy references.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| CLI Stability | Medium | High | Manual verification of CLI commands (`egregora write`, `egregora demo`). |
