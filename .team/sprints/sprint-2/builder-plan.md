# Plan: Builder - Sprint 2

**Persona:** Builder 🏗️
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to support the "Structure" sprint by providing the necessary data schemas for the new Context Layer features while maintaining strict data integrity.

- [ ] **Implement `git_commits` Schema:** Create a new table to cache git commit history, supporting Visionary's `GitHistoryResolver`. This will allow fast "What was the SHA of this file at time T?" queries.
- [ ] **Enforce Schema Hygiene:** Remove unused legacy schema definitions (e.g., `MEDIA_SCHEMA`) to prevent confusion during the Refactor persona's work.
- [ ] **Verify Unified Constraints:** Continuously monitor the `documents` table usage to ensure the new conditional constraints are working as intended.

## Dependencies
- **Visionary:** My `git_commits` table is a direct dependency for their `GitHistoryResolver`.

## Context
Sprint 2 is about laying the foundation. The `git_commits` table is a key piece of infrastructure for the "Universal Context" vision. It effectively turns our database into a "Time Machine" for code references.

## Expected Deliverables
1.  **New Table:** `git_commits` in `src/egregora/database/schemas.py` and `init.py`.
2.  **Migration:** (Implicit) New databases will include this table.
3.  **Clean Code:** Removal of dead schema code.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Index overhead on `git_commits` | Low | Medium | I will ensure the index is optimized for the specific access pattern `(path, timestamp DESC)`. |

## Proposed Collaborations
- **With Visionary:** To confirm the exact columns needed for the Git History Resolver.
