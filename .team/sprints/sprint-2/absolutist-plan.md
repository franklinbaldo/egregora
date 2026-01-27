# Plan: Absolutist - Sprint 2

**Persona:** Absolutist 💯
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to enforce the "One Way" principle during the massive structural refactoring of this sprint. I will ensure that old patterns are removed, not just deprecated.

<<<<<<< HEAD
- [ ] **Remove `DuckDBStorageManager` Compatibility Shim:** The `src/egregora/database/duckdb_manager.py` file contains a backward compatibility layer for callers expecting a direct connection. I will investigate usage and remove this if confirmed obsolete.
- [ ] **Audit `prompts.py` Compatibility:** Investigate `src/egregora/resources/prompts.py` for "API compatibility with the old prompt_templates.py" and remove if unused.
- [ ] **Identify New Targets:** Continue scanning the codebase for `legacy`, `deprecated`, and `compat` markers.

## Dependencies
- None specific, but I must coordinate with **Refactor** and **Simplifier** to ensure I don't delete code they are actively modifying.
=======
- [ ] **Audit `write.py` Refactor:** Monitor `Simplifier`'s work. Ensure the old monolithic `write` function is completely removed after the new pipeline is established.
- [ ] **Audit `runner.py` Refactor:** Monitor `Artisan`'s work. Ensure deprecated methods in `PipelineRunner` are deleted, not kept "for compatibility".
- [ ] **Purge Legacy Config:** Once `Artisan` migrates `config.py` to Pydantic, I will remove the dictionary-based configuration loading logic.
- [ ] **Remove Legacy Aliases:** Remove `get_embedding_router` and `index_documents` aliases in RAG modules (already identified).
- [ ] **Clean `pyproject.toml`:** Audit dependencies after refactors (e.g., if `google-ai-generativelanguage` is truly unused, ensure it's gone).

## Dependencies
- **Simplifier:** I depend on their refactor of `write.py` to identify what can be deleted.
- **Artisan:** I depend on their Pydantic refactor to delete the old config system.
>>>>>>> origin/pr/2897

## Context
Sprint 2 is a "Structure" sprint. This is the prime opportunity to reduce technical debt. If we refactor without removing the old code, we double the complexity. I am the garbage collector for this sprint.

## Expected Deliverables
<<<<<<< HEAD
1.  Removal of `DuckDBStorageManager` legacy accessors.
2.  Cleaned up `prompts.py` if safe.
3.  Updated `absolutist-plan.md` for Sprint 3.
=======
1.  **Refactor PRs:** Removal of legacy aliases in `src/egregora/rag/`.
2.  **Config Cleanup PR:** Removal of legacy dict config (post-Artisan merge).
3.  **Audit Report:** Feedback on `write.py` and `runner.py` PRs ensuring no dead code remains.
>>>>>>> origin/pr/2897

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Refactors keep compatibility layers "just in case" | High | Medium | I will rigorously comment on PRs requesting removal of shims unless a specific migration plan exists. |
| Deleting code breaks obscure tests | Medium | High | I will run the full test suite (`uv run pytest`) before any removal. |

## Proposed Collaborations
- **With Simplifier:** Verify removal of `write.py` legacy logic.
- **With Artisan:** Verify removal of `config.py` dict logic.
