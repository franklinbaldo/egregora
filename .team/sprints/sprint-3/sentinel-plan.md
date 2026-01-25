# Plan: Sentinel - Sprint 3

**Persona:** Sentinel 🛡️
**Sprint:** 3
**Created:** 2026-01-25
**Priority:** Medium

## Objectives

My mission is to shift from "Reactive Patching" to "Proactive Assurance" as we scale the new architecture.

- [ ] **Automated Security Gates:** Collaborate with Sheriff to add `pip-audit` and `bandit` as blocking steps in the CI pipeline (GitHub Actions).
- [ ] **Fuzz Testing Prototype:** Implement a basic fuzzing harness (using `atheris` or `python-afl`) for the `GitHistoryResolver` and `CodeReferenceDetector` to ensure robustness against malformed inputs.
- [ ] **Content Security Policy (CSP) Definition:** Define a strict CSP for the generated static sites to prevent XSS even if HTML injection occurs.
- [ ] **Third-Party Review:** Conduct a manual review of any new dependencies introduced in Sprint 2/3.

## Dependencies

- **Sheriff:** I need access/collaboration on the CI/CD workflows (`.github/workflows/`).
- **Visionary:** I need the `CodeReferenceDetector` to be stable enough to fuzz.

## Context

By Sprint 3, the "Structure" (Sprint 2) will be in place. We will likely be adding more complex features. This is the time to automate the security checks so I don't have to run them manually every session. Also, the new "Context" features (Git integration) introduce parsing complexity, which smells like a target for fuzzing.

## Expected Deliverables

1.  **CI Workflow Update:** PR adding security jobs to the build pipeline.
2.  **Fuzz Test Suite:** A new directory `tests/fuzz/` with at least one active fuzzer.
3.  **CSP Header/Meta:** Updates to the HTML templates to include `<meta http-equiv="Content-Security-Policy" ...>`.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Fuzzing finds nothing | Medium | Low | Good! It proves robustness. I will time-box this activity. |
| CI becomes too slow | Medium | Medium | I will ensure security scans run in parallel or are cached efficiently. |

## Proposed Collaborations

- **With Sheriff:** CI/CD integration.
- **With Forge:** Implementing CSP in templates.
