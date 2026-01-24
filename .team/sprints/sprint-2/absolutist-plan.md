# Plan: Absolutist - Sprint 2

**Persona:** Absolutist 💯
**Sprint:** 2
**Created:** 2026-01-26 (during Sprint 1)
**Priority:** High

## Objectives
My mission is to clear the path for the major refactors planned by Simplifier and Artisan. I will aggressively identify and remove legacy code that would otherwise complicate their work.

- [ ] **Purge Legacy Config:** Audit `src/egregora/config/` for dictionary-based fallbacks and deprecated settings, removing them before Artisan's Pydantic migration.
- [ ] **Cleanse Pipeline Artifacts:** Review `write.py` and `runner.py` for unused execution paths or legacy compatibility layers (e.g., old "V1" pipeline logic) and remove them.
- [ ] **Eliminate Dead Utilities:** Coordinate with Refactor to permanently delete unused functions in `src/egregora/utils/` rather than just ignoring them.

## Dependencies
- **Simplifier:** I need to know which parts of `write.py` are definitely "legacy" versus just "messy".
- **Refactor:** I rely on their `vulture` scan to identify candidates for deletion.

## Context
Sprint 2 is a heavy refactoring sprint. The most effective thing I can do is reduce the surface area of the code *before* it is refactored. Less code means easier refactoring and fewer bugs.

## Expected Deliverables
1. **PRs:** Removal of legacy config logic.
2. **PRs:** Removal of unused pipeline paths.
3. **Journal:** Documented evidence for every deletion.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Deleting code that is secretly used | Medium | High | Rigorous searching (`grep`) and running tests. If tests are missing, I will verify manually or defer deletion. |
| Conflict with active refactors | Medium | Medium | I will prioritize files *before* Simplifier/Artisan start their heavy work, or coordinate via GitHub. |

## Proposed Collaborations
- **With Simplifier:** "Pre-refactor cleanup" of `write.py`.
- **With Artisan:** "Pre-migration cleanup" of `config.py`.
