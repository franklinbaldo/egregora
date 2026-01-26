# Plan: Absolutist - Sprint 2

**Persona:** Absolutist 💯
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to simplify the codebase by removing legacy code and backward compatibility layers based on rigorous evidence.

- [ ] **Audit `prompts.py` Compatibility:** Investigate `src/egregora/resources/prompts.py` for "API compatibility with the old prompt_templates.py" and remove if unused.
- [ ] **Verify `extra.css` Removal:** Ensure no `docs/stylesheets/extra.css` files have crept back in, enforcing the new theme asset management.
- [ ] **Investigate Media Legacy Markers:** Begin auditing `src/egregora/ops/media.py` to identify which specific "attachment markers" are truly obsolete versus active legacy support.

## Dependencies
- **Simplifier:** I will avoid touching `write.py` while they extract ETL logic.
- **Steward:** I will rely on new ADRs to justify removing superseded architectural patterns.

## Context
The removal of `DuckDBStorageManager.execute` (completed in Sprint 1) was a good start. Now I focus on the prompt system and ensuring the visual identity transition (CSS) is clean.

## Expected Deliverables
1.  Report on `prompts.py` usage and potential for removal.
2.  Clean bill of health for CSS assets.
3.  List of media markers targeted for Sprint 3 removal.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Breaking Implicit Dependencies | Medium | High | Rigorous `grep` usage and test execution before deletion. |
| Deleting "Planned" Code | Low | Medium | Check with Steward/Architect if code marked "legacy" is actually "future". |
