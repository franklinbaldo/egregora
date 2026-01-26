# Plan: Deps 📦 - Sprint 2

**Persona:** Deps 📦
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to maintain dependency hygiene during the major refactoring efforts of Sprint 2.

- [ ] **Audit Refactor Impact:** Monitor PRs from Artisan and Simplifier for new dependency introductions or inefficient import patterns.
- [ ] **Enforce Strict Pinning:** Ensure any new dependencies introduced for the "Real-Time" pivot are strictly pinned and justified.
- [ ] **Clean Transitive Tree:** Investigate `google-api-core` and other heavy transitive dependencies to see if they can be pruned or optimized via `uv` exclusions.
- [ ] **Dev Dependency Optimization:** Review the `dev` dependency group to ensure we aren't carrying unnecessary weight (e.g., unused pytest plugins).

## Dependencies
- **Artisan:** I need to track their `config.py` and `runner.py` changes.
- **Visionary:** I need to verify the implementation of `GitHistoryResolver` doesn't introduce heavy git libraries.

## Context
Sprint 2 is a high-risk sprint for "dependency creep". As code moves around and new structures are created, developers often add utility libraries to solve immediate problems. I must act as the gatekeeper.

## Expected Deliverables
1.  **Clean Dependency Tree:** No unused top-level dependencies.
2.  **Audit Report:** A report on the weight/size of our dependency tree after the refactors.
3.  **Lockfile Integrity:** Zero "merge conflict" incidents in `uv.lock`.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Refactors introduce circular deps | Medium | High | Run `deptry` on every PR branch. |
| Vulnerable transitive dep | Low | High | Daily `pip-audit` and communication with Sentinel. |

## Proposed Collaborations
- **With Artisan:** Review `pyproject.toml` changes in their PRs.
- **With Sentinel:** Coordinate on any vulnerability patches (like `protobuf`).
