# Plan: Absolutist - Sprint 3

**Persona:** Absolutist 💯
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
<<<<<<< HEAD
<<<<<<< HEAD
Continue the purification of the codebase.

<<<<<<< HEAD
- [ ] **Address CLI Compatibility Layers:** Investigate `src/egregora/cli/main.py` comments regarding "DuckDBStorageManager directly to ensure Ibis compatibility". If the underlying issue is resolved, remove the workaround.
- [ ] **Deep Clean of `input_adapters`:** Check `src/egregora/input_adapters/base.py` for "Note: This is the only adapter interface. The legacy InputSource has been removed." and ensure no artifacts remain.
- [ ] **Review `output_sinks` conventions:** Check for any remaining version tracking or migration compatibility code.
=======
- [ ] **Remove Legacy Media Behavior:** Based on Sprint 2 investigation, remove the `att_file` legacy logic and obsolete markers from `src/egregora/ops/media.py`.
- [ ] **Remove `prompts.py` Shim:** If confirmed safe in Sprint 2, execute the removal of the legacy prompt compatibility layer.
- [ ] **Audit Input Adapters:** As we polish the "Mobile" experience, I will ensure our input adapters don't contain any legacy hacks for older mobile export formats that we no longer support.
>>>>>>> origin/pr/2890
=======
Continuing the mission of simplification, Sprint 3 will focus on deeper structural cleanups and auditing peripheral adapters.

- [ ] **Audit `input_adapters` for Legacy Artifacts:** Ensure that the transition from `InputSource` to the current adapter interface is complete and no "ghost" classes remain.
- [ ] **Review `output_sinks` Compatibility:** Investigate `src/egregora/output_sinks/conventions.py` and other output adapters for migration layers that have served their purpose.
- [ ] **Dead Code Analysis:** Conduct a sweep for unreachable code or unused imports that linters might have missed (or that were ignored).
>>>>>>> origin/pr/2837

## Dependencies
- **Refactor:** Coordination on any large-scale structural changes.

## Context
By Sprint 3, the core configuration and pipeline runner should be stabilized (thanks to Sprint 2 work). This opens the door for cleaning up the "edges" of the system—the input and output adapters—where compatibility shims often hide.

## Expected Deliverables
<<<<<<< HEAD
<<<<<<< HEAD
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
=======
1.  Removal of `att_file` legacy logic in `media.py`.
2.  Removal of `prompts.py` (if approved).
3.  Clean bill of health for input adapters.
>>>>>>> origin/pr/2890
=======
1.  Report on `input_adapters` cleanliness.
2.  Removal of any identified legacy code in `output_sinks`.
3.  Deletion of verified dead code blocks.
>>>>>>> origin/pr/2837

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
<<<<<<< HEAD
| CLI Stability | Medium | High | Manual verification of CLI commands (`egregora write`, `egregora demo`). |
=======
| Removing batch logic breaks CLI "one-off" runs | Medium | High | I will ensure the "Real-Time" system supports a "Run Once" mode before deleting the legacy batch runner. |

## Proposed Collaborations
- **With Bolt:** On removing inefficient legacy queries.
- **With Lore:** On archiving documentation.
>>>>>>> origin/pr/2897
=======
| Removing rarely used but valid adapters | Low | High | Verify usage against production logs or test coverage before removal. |

## Proposed Collaborations
- **With Shepherd:** Ensure that removing "unused" code doesn't reduce test coverage of edge cases that are actually important.
>>>>>>> origin/pr/2837
