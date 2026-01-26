# Plan: Deps - Sprint 2

**Persona:** Deps 📦
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to declutter the dependency tree and ensure the "Structure" sprint builds on a clean foundation.

- [ ] **Remove Unused Dependencies:** Remove `protobuf` and `google-ai-generativelanguage` from `pyproject.toml` as flagged by `deptry`.
- [ ] **Support Security Patches:** Allow `protobuf` to float as a transitive dependency to facilitate automatic security updates (addressing Sentinel's CVE concern).
- [ ] **Automated Audits:** continue running manual audits and investigate formalizing them into CI (as requested by Sentinel).

## Dependencies
- **Sentinel:** Coordination on `protobuf` security verification.

## Context
We have some "zombie" dependencies that were likely needed for legacy code but are no longer imported. Removing them reduces the attack surface and simplifies the lockfile.

## Expected Deliverables
1.  **Cleaner `pyproject.toml`:** Removal of at least 2 unused packages.
2.  **Updated `uv.lock`:** Reflecting the removals.
3.  **Audit Report:** Confirmation that the new dependency tree is secure.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Implicit/Legacy usage breaks | Low | High | Run full test suite (`uv run pytest`) immediately after removal. `google-api-core` is kept for exceptions. |
| Protobuf version mismatch | Medium | Medium | Rely on `uv`'s resolution. If `google-genai` forces an insecure version, I will explicitly override it in `pyproject.toml`. |
