# Plan: Visionary - Sprint 2

**Persona:** Visionary
**Sprint:** 2
**Created:** 2026-01-22
**Priority:** High

## Objectives
Describe the main objectives for this sprint:

- [ ] Prototype `CodeReferenceDetector` for path and SHA detection in chat messages (RFC 027).
- [ ] Implement POC of `GitHistoryResolver` to map Timestamp -> Commit SHA (RFC 027).
- [ ] Validate feasibility of integration with Writer agent's Markdown.

## Dependencies
- **builder:** Support for Git Lookups cache schema in DuckDB.
- **scribe:** Documentation update to include new historical links feature.

## Context
After approval of the Quick Win (RFC 027), the focus is to validate the core technology (Regex + Git CLI) before fully integrating into the pipeline. We need to ensure that detection is precise and commit resolution is fast.

## Expected Deliverables
1. Python script `detect_refs.py` that extracts references from a text file.
2. Python script `resolve_commit.py` that accepts date/time and returns SHA from local repo.
3. Performance report (time per lookup).

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Slow Git Lookup | High | Medium | Implement aggressive caching (DuckDB/Redis) |
| Path ambiguity | Medium | Low | Link to tree root or display warning if file does not exist |

## Proposed Collaborations
- **With builder:** Define `git_cache` table schema.
- **With artisan:** Review resolver code for optimization.

## Additional Notes
Total focus on "Foundation" for the Context Layer.
