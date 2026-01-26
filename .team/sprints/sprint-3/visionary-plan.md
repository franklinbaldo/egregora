# Plan: Visionary - Sprint 3

**Persona:** Visionary 🔭
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to implement the "Reflective Prompt Optimization" loop (RFC 029), turning the design from Sprint 2 into working code.

- [ ] **Implement `ReflectivePromptOptimizer`:** Build the logic to parse journals and generate updated Pydantic settings / Jinja templates.
- [ ] **Build `egregora optimize-prompts`:** Implement the CLI command.
- [ ] **End-to-End Test:** specific test case where a "mock journal" triggers a real configuration update PR.
- [ ] **Draft RFC 030 (Topology Mutation):** Explore how the system could spawn *new* agents, not just tune existing ones.

## Dependencies
- **Visionary (Sprint 2):** The Schema and Design must be complete.
- **Simplifier (Sprint 2):** The `write.py` refactor must be stable.

## Context
Sprint 3 is the "Symbiote Shift". We are enabling the system to act on its own insights. This is the first time Egregora will modify itself.

## Expected Deliverables
1.  **Code:** `src/egregora/reflection/optimizer.py`.
2.  **CLI:** `egregora optimize-prompts` command.
3.  **RFC 030:** "Topology Mutation" (Draft).

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| LLM Hallucinations in Config | High | High | The CLI will *always* require human confirmation (or a PR review) before applying changes. |
| "Feedback Loop" instability | Low | Medium | We will implement versioning for prompts so we can rollback easily. |

## Proposed Collaborations
- **With Forge:** To visualize the "Optimization Diff" in the CLI or a web UI.
- **With Sapper:** To ensure invalid mutations are caught gracefully.
