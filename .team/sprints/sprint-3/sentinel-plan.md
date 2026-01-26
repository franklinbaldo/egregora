# Plan: Sentinel - Sprint 3
**Persona:** Sentinel 🛡️
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to safeguard the new "Symbiote Shift" (Context Layer) and ensure the "Structured Sidecar" architecture doesn't introduce data leakage or injection vulnerabilities.

- [ ] **Audit Context Layer (Symbiote):** Review the `GitHistoryResolver` and any other context-fetching mechanisms to ensure they respect file permissions and do not leak content from `.env` or other sensitive files into the LLM context window.
- [ ] **Secure "Structured Sidecar":** Verify that the metadata sidecar (JSON/YAML) generation process properly sanitizes inputs to prevent injection attacks when these files are consumed by downstream agents.
- [ ] **Mobile UI Security Audit:** Verify that the "Mobile Polish" updates (Discovery UI) do not introduce DOM-based XSS vulnerabilities, especially in touch event handlers or dynamic content rendering.
- [ ] **RAG Data Privacy:** Ensure that the "Related Content" embedding pipeline filters out private/draft content *before* embedding, not just at retrieval time.

## Dependencies
- **Visionary:** I need access to the Symbiote/Context Layer implementation.
- **Simplifier:** I need to review the Structured Sidecar implementation.
- **Forge:** I need to see the mobile UI changes.

## Context
Sprint 3 moves from structure to "Intelligence" and "Context". The system will be reading more of its own code and history. This "introspection" capability is a major security risk if it can be tricked into reading secrets or executing malicious commit history.

## Expected Deliverables
1.  **Context Layer Security Review:** A report on the safety of the `GitHistoryResolver` and file reading logic.
2.  **Sidecar Sanitization Tests:** Tests proving that malicious content in source files doesn't corrupt the sidecar metadata.
3.  **RAG Privacy Verification:** Tests confirming private docs are not embeddable.
4.  **XSS Regression Tests:** Specific checks for mobile UI components.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| LLM Context Injection | High | High | Implement strict filtering of what files are allowed into the context window (blocklist .env, secrets, etc). |
| RAG Leaks Private Data | Medium | High | Enforce "Permissions at Ingestion" policy. |
| API Cost Overrun (Discovery) | Medium | Low | Monitor usage and ensure strict rate limiting is applied to the new batch jobs. |

## Proposed Collaborations
- **With Visionary:** Pair programming on the Context Layer security controls.
- **With Forge:** Review mobile frontend code.
