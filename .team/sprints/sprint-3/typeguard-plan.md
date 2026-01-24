# Plan: Typeguard - Sprint 3

**Persona:** Typeguard 🔒
**Sprint:** 3
**Created:** 2026-01-24
**Priority:** Medium

## Objectives

My mission is to enforce strict type safety across the codebase. For Sprint 3, I will focus on expanding coverage to the entire `src/egregora` package.

- [ ] **Package-Wide Strictness:** Target `mypy --strict` compliance for the entire `src/egregora` directory (excluding legacy/test files if necessary).
- [ ] **Automated Coverage Reporting:** Implement a CI check that prevents type coverage regression (e.g., ensuring `disallow_untyped_defs` is on for all new files).
- [ ] **Protocol Definition:** Replace usage of `Any` or complex `Union`s with explicit `Protocol` definitions for clearer interfaces, especially in the `input_adapters` and `output_adapters`.

## Dependencies

- **All Personas:** Requires a relatively stable codebase to avoid chasing moving targets.

## Context

By Sprint 3, the "Structure" sprint (Sprint 2) should be complete. This is the time to lock in the gains and ensure that as we build new features, we don't slide back into loose typing.

## Expected Deliverables

1.  **Strict Compliance:** `mypy.ini` or `pyproject.toml` updated to enforce strictness on `src/egregora`.
2.  **Protocols:** A `src/egregora/protocols.py` or similar defining core interfaces.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| strictness fatigue | Medium | Low | Strict typing can be verbose. I will ensure that the benefits (caught bugs) are communicated and that I help write the verbose parts. |

## Proposed Collaborations

- **With Architect/Steward:** To define the `Protocols` that represent the core system interfaces.
