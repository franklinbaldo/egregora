# Plan: Visionary - Sprint 2

**Persona:** Visionary 🔭
**Sprint:** 2
**Created:** 2026-01-22
**Priority:** High

## Objectives

Describe the main objectives for this sprint:

- [ ] Prototype `CodeReferenceDetector` for detecting paths and SHAs in chat messages (RFC 027).
- [ ] Implement POC of `GitHistoryResolver` to map Timestamp -> Commit SHA (RFC 027).
- [ ] Validate feasibility of integration with Writer agent Markdown.

## Dependencies

List dependencies on work from other personas:

- **Builder:** Support for Git Lookups cache schema in DuckDB.
- **Scribe:** Update documentation to include new historical link feature.

## Context

Explain the context and reasoning behind this plan:

After the approval of the Quick Win (RFC 027), the focus is to validate the core technology (Regex + Git CLI) before fully integrating it into the pipeline. We need to ensure detection is accurate and commit resolution is fast.

## Expected Deliverables

1. Python script `detect_refs.py` extracting references from a text file.
2. Python script `resolve_commit.py` accepting date/time and returning local repo SHA.
3. Performance report (time per lookup).

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Slow Git Lookup | High | Medium | Implement aggressive caching (DuckDB/Redis) |
| Path Ambiguity | Medium | Low | Link to tree root or show warning if file does not exist |

## Proposed Collaborations

- **With Builder:** Define `git_cache` table schema.
- **With Artisan:** Review resolver code for optimization.

## Additional Notes

Total focus on "Foundation" for the Context Layer.
