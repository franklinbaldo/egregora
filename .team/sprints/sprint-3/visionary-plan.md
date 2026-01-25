# Plan: Visionary - Sprint 3

**Persona:** Visionary 🔭
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives

My mission is to **fully integrate** the Nervous System and launch the Pulse UI.

- [ ] **Full Migration:** Refactor `write.py` to be fully event-driven (The "Brain" controls the flow).
- [ ] **Pulse UI Launch:** Replace the standard logging with the Rich TUI (RFC 029) as the default experience.
- [ ] **Resumability:** Implement checkpoint loading from the State Machine.

## Dependencies

- **Sprint 2 Completion:** Requires the Event Bus and basic instrumentation from Sprint 2.
- **Steward:** Approval of the "Unified State" ADR.

## Context

Once the foundation is laid in Sprint 2, Sprint 3 is about "flipping the switch". We move from a procedural script to a reactive system. This enables the "Pause/Resume" feature users have been asking for.

## Expected Deliverables

1.  `egregora write` command uses `NervousSystem` orchestrator.
2.  Users see the "Pulse" UI by default.
3.  `--resume` flag works for failed runs.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Regression in Pipeline Logic | Medium | High | Extensive BDD tests (created in Sprint 1) must pass. |
| UI breaks on weird terminals | Medium | Low | Implement a robust fallback to plain text logs. |

## Proposed Collaborations

- **With Builder:** Ensure the new State Machine persists correctly to DuckDB/JSON.
- **With Scribe:** Update documentation to explain the new UI and Resume capability.
