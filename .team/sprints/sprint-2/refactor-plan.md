# Plan: Refactor - Sprint 2

**Persona:** Refactor 🔧
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to systematically reduce technical debt and enforce code quality standards, focusing on areas not covered by Artisan's and Simplifier's structural refactors.

- [ ] **Eliminate Dead Code:** Run `vulture` and remove or explicitly whitelist unused code, variables, and functions. My previous journal noted this as a high-priority item.
- [ ] **Type Safety in Agents:** Target `src/egregora/agents/` to replace `Any` types with specific types or protocols and ensure 100% type coverage.
- [ ] **Test Suite Hygiene:** Refactor `tests/` to remove `# noqa` comments and fix linting warnings within the test code itself (e.g., `PT` rules).
- [ ] **Linting Polish for New Modules:** Review and apply strict linting/typing to the new modules created by Simplifier (`pipelines/etl/`) and Artisan (`config` models) as they are merged.

## Dependencies
- **Artisan:** I will wait for their `config` and `runner` refactors to stabilize before heavily modifying those files.
- **Simplifier:** I will wait for the `write.py` extraction before polishing the new ETL modules.

## Context
While Artisan and Simplifier are doing heavy structural lifting, I will ensure the codebase remains clean and compliant. The `agents` directory is complex and needs specific attention to typing to prevent runtime errors. Dead code removal is a low-risk, high-value activity that cleans up the noise.

## Expected Deliverables
1.  **Vulture Whitelist/Clean Code:** A cleaner codebase with verified unused code removed.
2.  **Typed Agents:** `src/egregora/agents/` passing strict `mypy` checks without `Any`.
3.  **Clean Tests:** Reduced linting warnings in the `tests/` directory.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Deleting "unused" code that is actually used dynamically | Medium | High | I will verify every deletion with `grep` and ensure tests cover the removed paths. If unsure, I will whitelist instead of delete. |
| Merge Conflicts | Low | Medium | I am targeting directories (`agents/`, `tests/`) that are less likely to be heavily modified by the other refactors in this sprint. |

## Proposed Collaborations
- **With Artisan:** Coordinate on Type Safety standards.
