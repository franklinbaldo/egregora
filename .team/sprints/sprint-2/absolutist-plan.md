# Plan: Absolutist - Sprint 2

**Persona:** Absolutist 💯
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to enforce the "One Way" principle during the massive structural refactoring of this sprint. I will ensure that old patterns are removed, not just deprecated.

- [x] **Remove `DuckDBStorageManager` Compatibility Shim:** (Completed in Sprint 1) The removal of `DuckDBStorageManager.execute` was successful.
- [ ] **Audit `prompts.py` Compatibility:** Investigate `src/egregora/resources/prompts.py` for "API compatibility with the old prompt_templates.py" and remove if unused.
- [ ] **Post-Migration Cleanup (Config):** Coordinate with **Artisan** to remove legacy dictionary-based configuration loading logic after their Pydantic migration is complete.
- [ ] **Identify New Targets:** Continue scanning the codebase for `legacy`, `deprecated`, and `compat` markers.
- [x] **Remove `read_document` Alias:** Removed backward-compatible alias from `BaseOutputSink` (Completed in Sprint 1).

## Dependencies
- **Artisan:** I will wait for their Pydantic migration before touching `config.py` cleanup.
- **Refactor:** Coordinate to ensure I don't delete code they are actively modifying.

## Context
Sprint 2 is a "Structure" sprint. This is the prime opportunity to reduce technical debt. If we refactor without removing the old code, we double the complexity. I am the garbage collector for this sprint.

## Expected Deliverables
1.  Cleaned up `prompts.py` if safe.
2.  Removal of legacy configuration loading (if Artisan completes their task).
3.  Updated `absolutist-plan.md` for Sprint 3.
4.  Report on any new legacy code found during the sprint.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Refactors keep compatibility layers "just in case" | High | Medium | I will rigorously comment on PRs requesting removal of shims unless a specific migration plan exists. |
| Deleting code breaks obscure tests | Medium | High | I will run the full test suite (`uv run pytest`) before any removal. |

## Proposed Collaborations
- **With Simplifier:** Verify removal of `write.py` legacy logic.
- **With Artisan:** Verify removal of `config.py` dict logic.
