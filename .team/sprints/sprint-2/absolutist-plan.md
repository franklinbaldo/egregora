# Plan: Absolutist - Sprint 2

**Persona:** Absolutist 💯
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to simplify the codebase by removing legacy code and backward compatibility layers based on rigorous evidence.

- [ ] **Remove `DuckDBStorageManager` Compatibility Shim:** The `src/egregora/database/duckdb_manager.py` file contains a backward compatibility layer for callers expecting a direct connection. I will investigate usage and remove this if confirmed obsolete.
- [ ] **Audit `prompts.py` Compatibility:** Investigate `src/egregora/resources/prompts.py` for "API compatibility with the old prompt_templates.py" and remove if unused.
- [ ] **Clean up Commented Code:** Remove any commented-out code blocks identified by the Refactor persona during their sweep.

## Dependencies
- **Simplifier:** I will avoid touching `write.py` while they extract ETL logic.
- **Steward:** I will rely on new ADRs to justify removing superseded architectural patterns.

## Context
The codebase still contains several "shims" introduced during previous refactors (e.g., Ibis migration, Prompt management changes). These shims incur maintenance debt and obscure the true architecture.

## Expected Deliverables
1.  Removal of `DuckDBStorageManager` legacy accessors.
2.  Cleaned up `prompts.py` if safe.
3.  Confirmation that no `docs/stylesheets/extra.css` files have crept back in.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Breaking Implicit Dependencies | Medium | High | Rigorous `grep` usage and test execution before deletion. |
| Deleting "Planned" Code | Low | Medium | Check with Steward/Architect if code marked "legacy" is actually "future". |
