# Plan: Visionary - Sprint 2

**Persona:** Visionary 🔭
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives

My mission for this sprint is to deliver the "Dry Run Mode" (Quick Win) to enable cost control and pave the way for autonomous agents.

- [ ] **Core Logic Implementation:** Implement the `dry_run` flag in `write.py` and the `TokenEstimator` service (RFC 029).
- [ ] **Reporting UI:** Create the `DryRunReporter` to visualize estimated costs and window breakdowns using `rich`.
- [ ] **CLI Integration:** Expose `--dry-run` in the `egregora write` command.
- [ ] **Verification:** Ensure dry run performance is under 5 seconds for standard inputs.

## Dependencies

- **Bolt:** I need to ensure that my token estimation logic doesn't introduce performance regressions (e.g., re-reading files unnecessarily).
- **Scribe:** Documentation needs to be updated to explain the new flag and how to interpret the cost estimates.

## Context

We identified that running the pipeline is opaque and costly. Before we can build "The Active Maintainer" (Moonshot), we need a simulation layer. This sprint delivers that layer immediately as a user-facing feature (`--dry-run`).

## Expected Deliverables

1.  `--dry-run` flag working in `egregora write`.
2.  `TokenEstimator` service with unit tests.
3.  Cost estimation logic for Gemini models.
4.  Updated CLI help text.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Inaccurate Estimates | Medium | Low | Clearly label output as "Estimated" and add a disclaimer. |
| Code Complexity | Medium | Medium | Use the "Facade Pattern" to abstract the LLM calls so `write.py` doesn't become a mess of `if dry_run:` checks. |

## Proposed Collaborations

- **With Bolt:** Review the `TokenEstimator` for efficiency.
- **With Scribe:** Co-author the "Cost Management" section in the docs.
