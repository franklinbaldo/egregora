# Plan: Absolutist - Sprint 3

**Persona:** Absolutist 💯
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
In Sprint 3, I will focus on cleaning up the "long tail" of legacy comments and minor artifacts that don't block major refactors but confuse developers.

- [ ] **Clean `enricher.py`:** Remove misleading deprecation comments about `UrlContextTool` and ensure the code is clean.
- [ ] **Audit `windowing.py`:** Investigate the "deprecated" comments in `windowing.py` regarding checkpoints. Ensure no dead code remains.
- [ ] **General Sweep:** Run a full codebase scan for `TODO: Remove` and `legacy` tags and process them.

## Dependencies
- None specific.

## Context
Sprint 3 is likely to be a "Optimization" or "Feature" sprint. My role is to ensure that the code we are optimizing is the *right* code, not legacy paths.

## Expected Deliverables
1.  Cleaned `enricher.py`.
2.  Audit report (or removal PR) for `windowing.py`.
3.  A "Legacy Code Inventory" report for the next major refactor cycle.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Removing comments that explain *why* something is done a certain way | Medium | Low | I will read the code carefully to distinguish between "history lesson" (keep) and "misleading trash" (delete). |

## Proposed Collaborations
- **With Scribe:** Ensure that removed deprecated features are also removed from documentation.
