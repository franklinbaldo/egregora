# Plan: Sentinel - Sprint 2
**Persona:** Sentinel 🛡️
**Sprint:** 2
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to ensure security is "built-in" to the new structural changes (ADRs, Config Refactor) and to maintain a clean vulnerability slate.

- [ ] **Secure Configuration Refactor:** Collaborate with Artisan to ensure the new Pydantic configuration uses `pydantic.SecretStr` for sensitive data and validates input strictly.
- [ ] **Security in ADRs:** Work with Steward to embed a mandatory "Security Implications" section into the new ADR template and review initial ADRs.
- [ ] **Patch Vulnerabilities (Protobuf):** Investigate CVE-2026-0994 in `protobuf`. Attempt to upgrade to a fixed version (e.g., 6.33.5+ or 5.29.6+) if compatible with `google-genai`. If unpatchable due to dependency pinning, document the risk and potential mitigation.
- [ ] **Audit Runner Refactor:** Review Artisan's decomposition of `runner.py` to ensure security contexts (e.g., rate limits, blocklists) are preserved.
- [ ] **Exception Handling Audit:** Work with Sapper to ensure the new exception hierarchy (especially in `enricher.py` and `runner.py`) does not swallow security-critical errors (SSRF, Auth failures).
- [ ] **OWASP Test Suite Expansion:** Add tests for A05 (Security Misconfiguration) specifically targeting the new configuration loading logic.

## Dependencies
- **Artisan:** My work on configuration security is directly tied to their Pydantic refactor.
- **Steward:** I need the ADR template to be available to provide feedback.
- **Sapper:** Collaboration on Exception classes.

## Context
Sprint 2 is a "Structure" sprint. The team is hardening the foundation. This is the perfect time to embed security into the DNA of the project (via Config and ADRs) before we start building complex new features in Sprint 3.

## Expected Deliverables
1.  **Secured Pydantic Models:** `SecretStr` usage in `src/egregora/config/`.
2.  **Updated ADR Template:** Template with security section.
3.  **Vulnerability Status:** `protobuf` patched or documented exception.
4.  **Security Regression Tests:** New tests in `tests/security/` covering configuration and runner logic.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Config Refactor Exposes Secrets | Medium | High | I will pair with Artisan and write tests that attempt to print/log the config object to ensure secrets are masked. |
| ADRs Ignore Security | Low | Medium | I will proactively review the template and the first few ADRs. |
| Protobuf Patch Conflict | High | Low | If `google-genai` pins the version, I cannot force it without breaking the app. I will document this as an accepted risk (DoS vector) until upstream releases a fix. |

## Proposed Collaborations
- **With Artisan:** Close collaboration on `config.py`.
- **With Steward:** Review of `.team/adr/TEMPLATE.md`.
- **With Sapper:** Review of `src/egregora/orchestration/exceptions.py`.
