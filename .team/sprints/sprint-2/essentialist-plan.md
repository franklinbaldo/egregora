# Plan: Essentialist 💎 - Sprint 2

**Persona:** Essentialist 💎
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
<<<<<<< HEAD
My mission is to enforce architectural simplicity and reduce "lifetime maintenance load". In this sprint, I act as a watchdog for the major refactors and optimize critical paths.

- [ ] **Simplicity Watchdog:** Audit the active refactors by Simplifier (`write.py`) and Artisan (`runner.py`) to ensure they reduce complexity rather than just redistributing it.
- [x] **Optimize `_window_by_count`:** Refactor the windowing logic in `src/egregora/transformations/windowing.py` to remove the N+1 query loop, aligning with "Data over Logic" and "Fetch-then-Compute".
- [x] **Janitorial Maintenance:** Fix corrupted or non-compliant plan files (Steward, Visionary) to maintain a clean project state.

## Dependencies
- **Simplifier & Artisan:** My audit work runs in parallel with their implementation.
- **Visionary:** I am providing feedback to steer them away from complex infrastructure (Redis).

## Context
The team is undertaking major structural changes. Without an Essentialist watchdog, these refactors risk introducing "Over-layering" or "Future-proofing tax". I will also directly tackle a known performance bottleneck (`_window_by_count`) to demonstrate that simplicity (fewer queries) equals performance.

## Expected Deliverables
1.  **Optimized `windowing.py`:** A `_window_by_count` function that runs in O(1) queries.
2.  **Clean Plan Files:** Restored `steward-plan.md` and English `visionary-plan.md`.
3.  **Feedback Report:** `essentialist-feedback.md` guiding the team.
=======
My mission is to support the structural refactoring ("Simplification") by removing dead code and enforcing heuristics.

- [x] **Remove Legacy Migrations:** Remove `migrate_media_table` from `src/egregora/database/migrations.py`. This is dead code from the V2->V3 transition.
- [ ] **Review Refactors:** Provide architectural review for **Simplifier**'s `write.py` decomposition and **Artisan**'s `runner.py` decomposition, ensuring they don't introduce "Indirection inflation" or "Over-layering".
- [ ] **Monitor Heuristics:** Scan new PRs for "Meta-config" and "Homemade infra" violations.

## Dependencies
- **Absolutist:** I am taking a piece of the "cleanup" work that aligns with radical simplicity.

## Context
Sprint 2 is a "Structure" sprint. While others build new structures, I must remove the old scaffolding to prevent "Ghost Code" (code that exists but is never called). `migrations.py` contains logic for a `media` table that no longer exists in the Pure architecture.

## Expected Deliverables
1.  Cleaned `src/egregora/database/migrations.py`.
2.  Feedback on PRs from Simplifier/Artisan.
>>>>>>> origin/pr/2862

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
| Refactor conflicts with Simplifier | Medium | Medium | I will focus on the *internal implementation* of specific functions (windowing) while they focus on structure. |
| Visionary ignores feedback | Low | High | I have explicitly flagged the Redis risk in the feedback file. |
=======
| Deleting code that is secretly used | Low | High | I will usage `grep` to verify zero usage before deletion. |
>>>>>>> origin/pr/2862
