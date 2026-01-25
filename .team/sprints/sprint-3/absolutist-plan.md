# Plan: Absolutist - Sprint 3

**Persona:** Absolutist 💯
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
Continuing the mission of simplification, Sprint 3 will focus on deeper structural cleanups and auditing peripheral adapters.

- [ ] **Audit `input_adapters` for Legacy Artifacts:** Ensure that the transition from `InputSource` to the current adapter interface is complete and no "ghost" classes remain.
- [ ] **Review `output_adapters` Compatibility:** Investigate `src/egregora/output_adapters/conventions.py` and other output adapters for migration layers that have served their purpose.
- [ ] **Dead Code Analysis:** Conduct a sweep for unreachable code or unused imports that linters might have missed (or that were ignored).

## Dependencies
- **Refactor:** Coordination on any large-scale structural changes.

## Context
By Sprint 3, the core configuration and pipeline runner should be stabilized (thanks to Sprint 2 work). This opens the door for cleaning up the "edges" of the system—the input and output adapters—where compatibility shims often hide.

## Expected Deliverables
1.  Report on `input_adapters` cleanliness.
2.  Removal of any identified legacy code in `output_adapters`.
3.  Deletion of verified dead code blocks.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Removing rarely used but valid adapters | Low | High | Verify usage against production logs or test coverage before removal. |

## Proposed Collaborations
- **With Shepherd:** Ensure that removing "unused" code doesn't reduce test coverage of edge cases that are actually important.
