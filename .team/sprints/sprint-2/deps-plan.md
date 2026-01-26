# Plan: Deps - Sprint 2

**Persona:** deps 📦
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to maintain a healthy dependency tree while supporting the team's structural refactoring efforts.

- [ ] **Support Refactoring:** Monitor `deptry` and `vulture` results as `refactor` and `simplifier` modify the codebase, adjusting ignores or removing dependencies as needed.
- [ ] **Monitor Protobuf:** Track the status of `protobuf` vs `google-api-core` and attempt to upgrade to a non-vulnerable version as soon as upstream allows.
- [ ] **Enforce Minimalism:** Review any new dependency requests (e.g., from `visionary` or `bolt`) and suggest stdlib alternatives where possible.
- [ ] **Automated Audits:** Ensure CI checks for dependencies (audit, deptry) remain green.

## Dependencies
- **Refactor:** Their work on dead code removal may allow me to remove unused packages.
- **Sentinel:** We share the goal of patching `protobuf`.

## Context
Sprint 2 is heavy on refactoring. This is a high-risk time for "dependency drift" where imports get moved and static analysis tools get confused. I need to be vigilant.

## Expected Deliverables
1.  **Clean Dependency Tree:** No unused packages (`deptry` clean).
2.  **No Vulnerabilities:** `pip-audit` clean (with known `protobuf` exception if needed).
3.  **Updated Config:** Adjustments to `pyproject.toml` to reflect code structure changes.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Refactoring hides imports | Medium | Low | I will review PRs to ensure `deptry` doesn't flag falsely, or add explicit ignores. |
| Protobuf remains vulnerable | High | Medium | We are blocked by upstream. I will document this as a known acceptance risk if we cannot upgrade. |
