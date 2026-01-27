# Plan: Visionary - Sprint 3

<<<<<<< HEAD
<<<<<<< HEAD
**Persona:** Visionary
**Sprint:** 3
**Created:** 2026-01-22
=======
**Persona:** Visionary 🔭
**Sprint:** 3
**Created:** 2026-01-28
>>>>>>> origin/pr/2895
**Priority:** High

## Objectives

<<<<<<< HEAD
Describe the main objectives for this sprint:

- [ ] Finalize integration of `CodeReferenceDetector` into the main pipeline (Enricher Agent) (RFC 027).
- [ ] Start API design for Universal Context Layer (RFC 026).
- [ ] Create "Hello World" VS Code Plugin that queries the local API.

## Dependencies

List dependencies from other personas:

- **Architect:** Review of Context Layer API design (REST vs MCP).
- **Sheriff:** Setup of integration tests for the VS Code plugin.

## Context

Explain the context and reasoning behind this plan:

With the historical database (RFC 027) working, we can start exposing this data to external tools (RFC 026). The VS Code plugin will serve as a proof of concept for the "Ubiquitous Memory" vision.

## Expected Deliverables

1. Feature RFC 027 complete and merged (Historical links on blog).
2. OpenAPI Spec for Context Layer API.
3. `egregora-vscode` repository with basic plugin.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| API Complexity | Medium | High | Adopt MCP (Model Context Protocol) standard to simplify |
| Plugin Overhead | Low | Low | Keep plugin "dumb", logic on Egregora server |

## Proposed Collaborations

- **With Architect:** Definition of API endpoints.
- **With Forge:** Help with TypeScript for the VS Code plugin.

## Additional Notes

Critical sprint for transition from "Generator" to "Platform".
=======
My mission is to integrate the "Context Layer" and "Autopoiesis" into the core product.

- [ ] **Integrate Reflective Optimization (RFC 029):** Hook the `CriticAgent` into the main pipeline (enabled via flag `--reflection`).
- [ ] **Design Autopoiesis Loop (RFC 028):** Create the architectural spec for how the Critic's output can mutate the configuration.
- [ ] **Universal Context Layer API (RFC 026):** Draft the OpenAPI spec for the external context service.

## Dependencies

- **Architect:** Review of the Context Layer API.
- **Shepherd:** Load testing the pipeline with the added `CriticAgent` step.

## Context

Sprint 3 is the "Symbiote Shift". We move from a static generator to a living system. The `CriticAgent` moves from prototype to production (RFC 029), and we design the "nervous system" (API) that connects Egregora to the outside world (RFC 026).

## Expected Deliverables

1.  **Integration of `CriticAgent`:** Merged into `main`.
2.  **`reflection.md` output:** The pipeline produces this artifact.
3.  **Context Layer OpenAPI Spec:** `docs/api/context-layer.yaml`.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Performance Hit | High | Medium | Ensure Reflection is async and optional (opt-in). |
| API Complexity | Medium | High | Start with a minimal "Read-Only" API for the Context Layer. |

## Collaborations

- **With Architect:** On API design.
- **With Shepherd:** On performance profiling of the Reflection step.
>>>>>>> origin/pr/2895
=======
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
>>>>>>> origin/pr/2876
