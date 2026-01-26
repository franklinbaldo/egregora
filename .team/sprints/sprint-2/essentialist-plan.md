# Plan: Essentialist 💎 - Sprint 2

**Persona:** Essentialist 💎
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
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

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Deleting code that is secretly used | Low | High | I will usage `grep` to verify zero usage before deletion. |
