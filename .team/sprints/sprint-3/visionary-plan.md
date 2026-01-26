# Plan: Visionary 🔭 - Sprint 3

**Persona:** Visionary 🔭
**Sprint:** 3
**Created:** 2026-01-22
**Priority:** High

## Objectives

Describe the main objectives for this sprint:

- [ ] Finalize integration of `CodeReferenceDetector` into the main pipeline (Enricher Agent) (RFC 027).
- [ ] Start API design for the Universal Context Layer (RFC 026).
- [ ] Create "Hello World" VS Code Plugin that queries the local API.

## Dependencies

List work dependencies from other personas:

- **Architect:** Review of the Context Layer API design (REST vs MCP).
- **Sheriff:** Setup of integration tests for the VS Code plugin.

## Context

Explain the context and reasoning behind this plan:

With the historical database (RFC 027) functioning, we can start exposing this data to external tools (RFC 026). The VS Code plugin will serve as a proof of concept for the "Ubiquitous Memory" vision.

## Expected Deliverables

1. RFC 027 feature complete and merged (Historical links in the blog).
2. OpenAPI Spec for Context Layer API.
3. `egregora-vscode` repository with basic plugin.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| API Complexity | Medium | High | Adopt MCP (Model Context Protocol) standard to simplify |
| Plugin Overhead | Low | Low | Keep plugin "dumb", logic on the Egregora server |

## Proposed Collaborations

- **With Architect:** Definition of API endpoints.
- **With Forge:** Help with TypeScript for the VS Code plugin.

## Additional Notes

Critical sprint for transition from "Generator" to "Platform".
