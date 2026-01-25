# Plan: Visionary - Sprint 2

**Persona:** Visionary 🔭
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives

My mission is to lay the groundwork for the **Egregora Nervous System** (RFC 028).

- [ ] **Event Schema Definition:** Define the core `Event` dataclasses and the `Bus` interface.
- [ ] **Instrumentation (Alpha):** Add event emission points to `write.py` (e.g., `PhaseChanged`, `WindowProcessed`) without breaking existing logic.
- [ ] **Prototype Pulse UI:** Build a standalone `rich` prototype that consumes mock events to demonstrate the UX (RFC 029).

## Dependencies

- **Refactor:** I need `write.py` to be stable enough to instrument, or ideally partially modularized.
- **Builder:** Need to ensure the new Event classes don't conflict with existing Pydantic models.

## Context

The "Historical Code Linking" (RFC 027) was a good idea, but the **Architecture Analysis** revealed a deeper systemic risk: the opacity and fragility of the core pipeline. We must fix the "Nervous System" before we add more complex organs.

## Expected Deliverables

1.  `src/egregora/orchestration/events.py`: Core event definitions.
2.  `src/egregora/orchestration/bus.py`: Simple synchronous event bus.
3.  `examples/pulse_demo.py`: A script demonstrating the proposed CLI UI.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Disruption to `write.py` | Medium | High | Use a "Sidecar" approach: emit events but don't change control flow yet. |
| Performance Overhead | Low | Low | Keep the Event Bus synchronous and lightweight for now. |

## Proposed Collaborations

- **With Refactor:** Coordinate on where to slice `write.py` so I can insert probes.
- **With Maya:** Design the "textual aesthetics" of the Pulse UI.
