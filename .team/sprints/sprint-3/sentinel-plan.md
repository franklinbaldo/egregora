# Plan: Sentinel - Sprint 3

**Persona:** Sentinel 🛡️
**Sprint:** 3
**Created:** 2026-01-26 (during Sprint 1)
**Priority:** High

## Objectives
My mission is to prepare the security defenses for the incoming "Symbiote" architecture and Real-Time Adapters.

- [ ] **Threat Model "Real-Time Adapters":** Analyze the RFC from Sprint 2 and produce a Threat Model document identifying risks (SSRF, DoS, Data Exfiltration).
- [ ] **Implement Adapter Sandboxing:** Design and implement the security controls for the new adapter framework (e.g., restricted network access, resource quotas).
- [ ] **Automated Security Gates:** Integrate `pip-audit` and `bandit` explicitly into the new `taskmaster` or CI pipelines.
- [ ] **Secret Rotation Policy:** Establish a documented policy and potential tooling for rotating the API keys used by the new architecture.

## Dependencies
- **Visionary:** I need the "Real-Time Adapter Framework" RFC to be finalized.
- **Simplifier:** I need the new pipeline structure to be stable to integrate automated security gates.

## Context
Sprint 3 is where the "Egregora Symbiote" starts to become real. Moving from a batch-processed static site generator to a real-time, data-ingesting agent significantly increases the risk profile. My focus shifts from "Code Hygiene" to "Architecture Security."

## Expected Deliverables
1.  **Threat Model Document:** `.team/security/threat-models/real-time-adapters.md`.
2.  **Sandboxing Utilities:** Python decorators or context managers for restricted execution in `src/egregora/security/sandbox.py`.
3.  **Security CI Job:** Updated workflow or task definition including security scanners.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Adapters allow SSRF | High | Critical | I will mandate the use of the `validate_public_url` utility for *all* adapter network requests. |
| New dependencies introduce vulnerabilities | Medium | High | I will enforce `pip-audit` checks on all new PRs. |

## Proposed Collaborations
- **With Visionary:** Reviewing the security implications of the new adapter design.
