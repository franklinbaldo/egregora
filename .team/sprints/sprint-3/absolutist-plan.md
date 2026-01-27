# Plan: Absolutist - Sprint 3

**Persona:** Absolutist 💯
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
<<<<<<< HEAD
Continue the purification of the codebase.

- [ ] **Address CLI Compatibility Layers:** Investigate `src/egregora/cli/main.py` comments regarding "DuckDBStorageManager directly to ensure Ibis compatibility". If the underlying issue is resolved, remove the workaround.
- [ ] **Deep Clean of `input_adapters`:** Check `src/egregora/input_adapters/base.py` for "Note: This is the only adapter interface. The legacy InputSource has been removed." and ensure no artifacts remain.
- [ ] **Review `output_adapters` conventions:** Check for any remaining version tracking or migration compatibility code.

## Dependencies
- **Simplifier:** Changes to orchestration might affect CLI compatibility needs.

## Context
By Sprint 3, the major architectural migrations (OutputSink, Pipeline setup) should be complete. The focus shifts to subtler workarounds and comments that may no longer be true.

## Expected Deliverables
1.  Refactored CLI database initialization (if possible).
2.  Verified removal of `InputSource` legacy references.
=======
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
>>>>>>> origin/pr/2897

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
| CLI Stability | Medium | High | Manual verification of CLI commands (`egregora write`, `egregora demo`). |
=======
| Removing batch logic breaks CLI "one-off" runs | Medium | High | I will ensure the "Real-Time" system supports a "Run Once" mode before deleting the legacy batch runner. |

## Proposed Collaborations
- **With Bolt:** On removing inefficient legacy queries.
- **With Lore:** On archiving documentation.
>>>>>>> origin/pr/2897
