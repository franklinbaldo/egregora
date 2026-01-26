# Plan: Visionary 🔭 - Sprint 2

**Persona:** Visionary 🔭
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives

Describe the main objectives for this sprint:

- [ ] **Prototype `CodeReferenceDetector`:** Develop regex/logic to detect file paths and Git SHAs in chat messages (RFC 027).
- [ ] **Implement `GitHistoryResolver` POC:** Create a script to map Timestamp -> Commit SHA for local repositories (RFC 027).
- [ ] **Research Cross-Site Resolution:** Investigate `feedparser` and `httpx` for fetching external Atom feeds to support "Smart Embeds" (RFC 029).
- [ ] **Validate Writer Integration:** Ensure the detector can inject context into the Writer agent's prompt without breaking the flow.

## Dependencies

List dependencies on work from other personas:

- **Builder:** Support for `git_cache` schema in DuckDB.
- **Scribe:** Updates to documentation to include the new "Historical Linking" feature.

## Context

Explain the context and reasoning behind this plan:

Following the approval of RFC 027 (Historical Code Linking), our focus is on validating the core technology (Regex + Git CLI) before full pipeline integration. We must ensure detection is accurate and commit resolution is fast. Additionally, we are starting early research on RFC 029 (Cross-Site Resolver) to prepare for the "Egregora Mesh" initiative.

## Expected Deliverables

1.  Python script `detect_refs.py` extracting references from text.
2.  Python script `resolve_commit.py` mapping Time -> SHA.
3.  Research notes on Atom Feed parsing for cross-site embedding.
4.  Performance report (time per Git lookup).

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Slow Git Lookups | High | Medium | Implement aggressive caching (DuckDB/Redis). |
| Path Ambiguity | Medium | Low | Link to tree root or warn if file doesn't exist. |
| External Feed Latency | High | Low | (RFC 29) Plan for build-time caching of external feeds. |

## Proposed Collaborations

- **With Builder:** Define `git_cache` table schema.
- **With Artisan:** Review resolver code for optimization.

## Additional Notes

Focus on "Foundation" for the Context Layer and early steps for the Mesh.
