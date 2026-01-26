# Plan: Builder - Sprint 2

**Persona:** Builder 🏗️
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to harden the V3 "Pure" architecture and support the team's caching and refactoring needs with robust schemas.

- [ ] **Design `git_lookup_cache` Schema:** Create a schema to support Visionary's `GitHistoryResolver`, optimizing for (path, timestamp) lookups.
- [ ] **Design `asset_cache` Schema:** Create a schema to support Bolt's social card caching strategy (if DB persistence is chosen).
- [ ] **Audit & Optimize Indexes:** Review the indexes created in `init.py` (especially for `messages`) to ensure they cover the new query patterns from the refactored pipelines.
- [ ] **Migration Hardening:** Add "idempotency verification" tests to ensure migrations can run repeatedly without side effects.
- [ ] **Schema Documentation Update:** Update `docs/schema-evolution-plan.md` to reflect the completed V3 consolidation and new Sprint 2 schemas.

## Dependencies
- **Visionary:** Need confirmation on query patterns for Git history.
- **Bolt:** Need decision on DB vs. Filesystem for asset cache.

## Context
Sprint 2 is about structure. While others refactor code (Simplifier, Artisan), I must ensure the data structure remains rigid where it matters (constraints) and flexible where needed (new cache tables). The "Batch Era" is ending; these schemas will support the transition to more dynamic lookups.

## Expected Deliverables
1.  **Schema Update:** `git_lookup_cache` added to `schemas.py` and `init.py`.
2.  **Schema Update:** `asset_cache` added (if verified).
3.  **Migration Script:** New migration for cache tables.
4.  **Documentation:** Updated `docs/schema-evolution-plan.md`.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Cache tables grow indefinitely | Medium | Medium | Implement TTL or "Cap" logic in the schema or application (or rely on periodic cleanup). |
| Migration conflicts with Refactors | Low | High | Coordinate with Simplifier/Artisan to ensure `init.py` changes are compatible with new runner logic. |

## Proposed Collaborations
- **With Visionary:** Pair on the Git Cache implementation.
- **With Bolt:** Pair on Index tuning.
