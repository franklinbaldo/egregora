# Plan: Absolutist - Sprint 2

**Persona:** Absolutist 💯
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to simplify the codebase by removing legacy code and backward compatibility layers based on rigorous evidence.

- [ ] **Remove `DuckDBStorageManager` Compatibility Shim:** The `src/egregora/database/duckdb_manager.py` file contains a backward compatibility layer for callers expecting a direct connection. I will investigate usage and remove this if confirmed obsolete.
- [ ] **Audit `prompts.py` Compatibility:** Investigate `src/egregora/resources/prompts.py` for "API compatibility with the old prompt_templates.py" and remove if unused.
- [ ] **Post-Migration Cleanup (Config):** Coordinate with **Artisan** to remove legacy dictionary-based configuration loading logic after their Pydantic migration is complete.
- [ ] **Identify New Targets:** Continue scanning the codebase for `legacy`, `deprecated`, and `compat` markers.

## Dependencies
- **Artisan:** I will wait for their Pydantic migration before touching `config.py` cleanup.
- **Refactor:** Coordinate to ensure I don't delete code they are actively modifying.

## Context
The codebase still contains several "shims" introduced during previous refactors (e.g., Ibis migration, Prompt management changes). These shims incur maintenance debt and obscure the true architecture.

## Expected Deliverables
1.  Removal of `DuckDBStorageManager` legacy accessors.
2.  Cleaned up `prompts.py` if safe.
3.  Removal of legacy configuration loading (if Artisan completes their task).
4.  Updated `absolutist-plan.md` for Sprint 3.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Breaking Implicit Dependencies | Medium | High | Rigorous `grep` usage and test execution before deletion. |
| Deleting "Planned" Code | Low | Medium | Check with Steward/Architect if code marked "legacy" is actually "future". |

## Proposed Collaborations
- **With Artisan:** Ensure that the old configuration logic is fully identified and safe to remove once the new Pydantic models are in place.
