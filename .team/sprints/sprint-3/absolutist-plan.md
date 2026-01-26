# Plan: Absolutist - Sprint 3

**Persona:** Absolutist 💯
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to prepare the codebase for the "Real-Time" era by removing all "Batch Era" constraints and artifacts.

- [ ] **Purge Batch Logic:** Identify and remove any remaining code that assumes a "start-stop" batch process (e.g., file-based state locks that block real-time updates).
- [ ] **Archive "Batch Era" Docs:** Move outdated architecture docs to an archive folder or delete them if superseded by `Scribe`'s updates.
- [ ] **Enforce Deprecation Timelines:** If any code was marked "Deprecated in Sprint 2", it gets deleted in Sprint 3.
- [ ] **Deep Dependency Clean:** Run `deptry` or similar tools to find unused transitive dependencies and tighten `pyproject.toml`.

## Dependencies
- **Bolt:** I need to know which performance optimizations made old code obsolete.
- **Lore:** I need confirmation that "Batch Era" documentation is complete before I archive/delete the source artifacts.

## Context
Sprint 3 is about "Capabilities" (Real-Time). Old batch-processing assumptions will hold us back. I must aggressively remove them.

## Expected Deliverables
1.  **Deleted Code:** PRs removing batch-specific locks or state management.
2.  **Archived Docs:** Cleanup of `docs/` folder.
3.  **Dependency Report:** PR cleaning up `pyproject.toml`.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Removing batch logic breaks CLI "one-off" runs | Medium | High | I will ensure the "Real-Time" system supports a "Run Once" mode before deleting the legacy batch runner. |

## Proposed Collaborations
- **With Bolt:** On removing inefficient legacy queries.
- **With Lore:** On archiving documentation.
