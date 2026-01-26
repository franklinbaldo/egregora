# Plan: Visionary - Sprint 2

**Persona:** Visionary 🔭
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to prepare the architecture for "Autopoiesis" (RFC 028) by defining the data structures for self-reflection.

- [ ] **Define Reflection Schema:** Create the Pydantic models for the "System Feedback" section of the journal. This turns unstructured text into actionable data.
- [ ] **Design Prompt Optimizer CLI:** Create the design spec for `egregora optimize-prompts` (RFC 029), including the "Human-in-the-loop" PR workflow.
- [ ] **Security Collaboration:** Work with Sentinel to define the "Mutation Sandbox" to prevent prompt injection attacks via the journal.

## Dependencies
- **Simplifier:** I need `write.py` decomposed so I can hook into the journal generation process cleanly.
- **Sentinel:** I need the "SecretStr" implementation to ensure my optimizer doesn't leak secrets.

## Context
We are moving from a "Batch/Static" era to a "Living System" era. Sprint 2 is about creating the *language* of this evolution. If we can't structure the feedback, we can't act on it.

## Expected Deliverables
1.  **Schema Module:** `src/egregora/reflection/models.py` (Draft).
2.  **Design Doc:** `docs/design/reflective-optimizer.md`.
3.  **RFCs:** 028 and 029 finalized and merged.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Schema is too rigid | Medium | Medium | I will analyze past journals to ensure the schema covers existing feedback patterns. |
| Security concerns block Autopoiesis | Medium | High | I will co-design with Sentinel from Day 1 to ensure safety is built-in. |

## Proposed Collaborations
- **With Sentinel:** To design the "Mutation Sandbox".
- **With Simplifier:** To align on where the `Reflection` module sits in the new architecture.
