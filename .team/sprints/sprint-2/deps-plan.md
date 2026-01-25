# Plan: Deps - Sprint 2

**Persona:** Deps 📦
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to ensure the dependency tree remains healthy and secure while the team performs major structural refactoring.

- [x] **Fix Dependency Auditing:** Restore and configure `[tool.deptry]` in `pyproject.toml` to eliminate false positives and make audits useful again. (Completed in Sprint 1 transition).
- [x] **Security Updates:** Update `protobuf` to fix CVE-2026-0994. (Completed).
- [ ] **Monitor Refactoring Impacts:** Watch for new dependencies introduced by Simplifier (`write.py` refactor) and Artisan (`pydantic` models).
- [ ] **Support Social Cards:** Be ready to add `cairosvg` or other image processing libs for Forge.

## Dependencies
- **Forge:** Waiting on implementation of Social Cards to finalize dependencies.
- **Simplifier:** Refactoring `write.py` might change import structures affecting `deptry`.

## Context
Sprint 2 is heavy on refactoring. My role is "support and monitor". I have already cleaned up the `deptry` configuration and handled the critical `protobuf` update.

## Expected Deliverables
1.  **Clean `deptry` Report:** No false positives.
2.  **Secure `uv.lock`:** All critical patches applied.
3.  **Feedback:** Timely feedback on PRs adding new libraries.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| `mkdocs-material` blocks updates | High | Low | `pillow` 12.0 is blocked. I will monitor for upstream updates. |
