# Plan: Sentinel - Sprint 3

**Persona:** Sentinel 🛡️
**Sprint:** 3
<<<<<<< HEAD
**Created:** 2026-01-26 (during Sprint 1)
**Priority:** High

## Objectives
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> origin/pr/2856
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
<<<<<<< HEAD
=======
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
>>>>>>> origin/pr/2891
=======
>>>>>>> origin/pr/2856
=======
**Created:** 2026-01-25
**Priority:** Medium

## Objectives

My mission is to shift from "Reactive Patching" to "Proactive Assurance" as we scale the new architecture.

- [ ] **Automated Security Gates:** Collaborate with Sheriff to add `pip-audit` and `bandit` as blocking steps in the CI pipeline (GitHub Actions).
- [ ] **Fuzz Testing Prototype:** Implement a basic fuzzing harness (using `atheris` or `python-afl`) for the `GitHistoryResolver` and `CodeReferenceDetector` to ensure robustness against malformed inputs.
- [ ] **Content Security Policy (CSP) Definition:** Define a strict CSP for the generated static sites to prevent XSS even if HTML injection occurs.
- [ ] **Third-Party Review:** Conduct a manual review of any new dependencies introduced in Sprint 2/3.

## Dependencies

- **Sheriff:** I need access/collaboration on the CI/CD workflows (`.github/workflows/`).
- **Visionary:** I need the `CodeReferenceDetector` to be stable enough to fuzz.

## Context

By Sprint 3, the "Structure" (Sprint 2) will be in place. We will likely be adding more complex features. This is the time to automate the security checks so I don't have to run them manually every session. Also, the new "Context" features (Git integration) introduce parsing complexity, which smells like a target for fuzzing.

## Expected Deliverables

1.  **CI Workflow Update:** PR adding security jobs to the build pipeline.
2.  **Fuzz Test Suite:** A new directory `tests/fuzz/` with at least one active fuzzer.
3.  **CSP Header/Meta:** Updates to the HTML templates to include `<meta http-equiv="Content-Security-Policy" ...>`.
>>>>>>> origin/pr/2831

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> origin/pr/2856
| Adapters allow SSRF | High | Critical | I will mandate the use of the `validate_public_url` utility for *all* adapter network requests. |
| New dependencies introduce vulnerabilities | Medium | High | I will enforce `pip-audit` checks on all new PRs. |

## Proposed Collaborations
- **With Visionary:** Reviewing the security implications of the new adapter design.
<<<<<<< HEAD
=======
| LLM Context Injection | High | High | Implement strict filtering of what files are allowed into the context window (blocklist .env, secrets, etc). |
| RAG Leaks Private Data | Medium | High | Enforce "Permissions at Ingestion" policy. |
| API Cost Overrun (Discovery) | Medium | Low | Monitor usage and ensure strict rate limiting is applied to the new batch jobs. |

## Proposed Collaborations
- **With Visionary:** Pair programming on the Context Layer security controls.
- **With Forge:** Review mobile frontend code.
>>>>>>> origin/pr/2891
=======
>>>>>>> origin/pr/2856
=======
| Fuzzing finds nothing | Medium | Low | Good! It proves robustness. I will time-box this activity. |
| CI becomes too slow | Medium | Medium | I will ensure security scans run in parallel or are cached efficiently. |

## Proposed Collaborations

- **With Sheriff:** CI/CD integration.
- **With Forge:** Implementing CSP in templates.
>>>>>>> origin/pr/2831
