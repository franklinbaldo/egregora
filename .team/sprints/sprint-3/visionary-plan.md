# Plan: Visionary 🔭 - Sprint 3

**Persona:** Visionary 🔭
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives

Describe the main objectives for this sprint:

- [ ] **Design "Egregora Mesh" Architecture:** Define the JSON/AtomPub protocol for federated discovery and query (RFC 028).
- [ ] **Integrate Universal Context Layer:** Move `CodeReferenceDetector` from prototype to production integration in the `WriterAgent` pipeline (RFC 026).
- [ ] **Implement `ReferenceResolver` MVP:** Build the first version of the cross-site embedding system (RFC 029) using the research from Sprint 2.
- [ ] **Security Audit for Federation:** Work with Sentinel to define the trust model for inter-node communication.

## Dependencies

List dependencies on work from other personas:

- **Sentinel:** Security review of the proposed federation protocol.
- **Builder:** Implementation of the `ContentLibrary` facade (needed for clean cross-site fetching).
- **Forge:** Design of the "Reference Card" UI component.

## Context

Explain the context and reasoning behind this plan:

Sprint 3 is about "Connecting the Dots". We move from local context (Code Linking) to global context (Mesh). RFC 026 (Context Layer) moves to production, while RFC 028 (Mesh) enters the detailed design phase. RFC 029 (Resolver) serves as the bridge between the two.

## Expected Deliverables

1.  `mesh_protocol_spec.md`: Detailed specification of the federation protocol.
2.  `ReferenceResolver` class integrated into the rendering pipeline.
3.  Production-ready `CodeReferenceDetector` in `src/egregora/agents/`.

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Federation Protocol Complexity | High | High | Start with "Read-Only" public feeds before tackling auth/private sharing. |
| Build Time Explosion | Medium | Medium | Strict timeouts and caching for all external fetches. |

## Proposed Collaborations

- **With Sentinel:** Threat modeling for the Mesh.
- **With Forge:** UI design for external content cards.

## Additional Notes

The goal is to prove "Egregora is not an Island".
