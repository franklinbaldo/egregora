# Plan: Visionary - Sprint 3

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
