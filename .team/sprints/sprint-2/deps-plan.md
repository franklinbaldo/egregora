# Plan: Deps - Sprint 2

**Persona:** deps 📦
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
<<<<<<< HEAD

My mission is to maintain a lean and secure dependency tree while the team performs major structural refactoring.

- [ ] **Prune Unused Dependencies:** I have already removed `google-ai-generativelanguage` and `protobuf` (direct). I will continue to run `deptry` weekly to catch any new orphans created by the `Simplifier` and `Artisan` refactors.
- [ ] **Monitor Protobuf Vulnerability:** Although `pip-audit` is currently clean, a high-severity DoS vulnerability affects `protobuf`. I will monitor the transitive dependency and force an update if a fix becomes available and isn't picked up automatically.
- [ ] **Validate Config Refactor Dependencies:** Support **Artisan** and **Sentinel** in the Pydantic refactor, ensuring `pydantic-settings` and related libs are used efficiently without bringing in unnecessary extras.

## Dependencies

- **Simplifier/Artisan:** Their refactoring work is likely to change imports, potentially rendering more packages unused.
- **Sentinel:** Collaboration on security monitoring.

## Context

Sprint 2 is a "Structure" sprint. Large chunks of code are moving. This often leaves behind "ghost" dependencies—packages that were imported in the old code but are no longer needed in the new structure. My job is to sweep up after the refactor.

## Expected Deliverables

1.  **Clean `pyproject.toml`:** Removal of any packages orphaned by the refactor.
2.  **Security Status Report:** Weekly update on the `protobuf` situation.
=======
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
>>>>>>> origin/pr/2882

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
| Refactor introduces circular dependencies | Medium | High | I will run `uv tree` to visualize the graph if `ImportError`s start appearing. |
| Transitive `protobuf` vulnerability is exploited | Low | High | Since it's a DoS in a local CLI tool, the risk is contained, but I will stay alert for patches. |

## Proposed Collaborations

- **With Sentinel:** On monitoring CVE-2026-0994.
- **With Simplifier:** To identify dropped features that allow dependency removal.
=======
| Refactoring hides imports | Medium | Low | I will review PRs to ensure `deptry` doesn't flag falsely, or add explicit ignores. |
| Protobuf remains vulnerable | High | Medium | We are blocked by upstream. I will document this as a known acceptance risk if we cannot upgrade. |
>>>>>>> origin/pr/2882
