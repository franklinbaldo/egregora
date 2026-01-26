# Plan: Deps - Sprint 3

**Persona:** Deps 📦
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to support the new "Discovery" features by ensuring RAG-related dependencies are secure and efficient.

- [ ] **Audit RAG Dependencies:** Review the dependency tree for `lancedb`, `google-genai`, and any new vector search libraries introduced for "Discovery".
- [ ] **Minimize Bloat:** Ensure we don't pull in heavy ML libraries (like full `torch` or `transformers`) unless absolutely necessary.
- [ ] **Rate Limiting:** Verify that `ratelimit` or similar packages are correctly configured/updated to support the "Discovery" batch jobs.

## Dependencies
- **Visionary/Simplifier:** I need to know which new libraries are being added for the "Related Content" feature.

## Context
Sprint 3 introduces "Smart" features. AI libraries are notoriously heavy and prone to vulnerabilities. I need to be the gatekeeper to keep the image size and startup time reasonable.

## Expected Deliverables
1.  **RAG Dependency Audit:** A report on the weight and security of the new AI stack.
2.  **Optimization Recommendations:** Suggestions to replace heavy deps with lighter alternatives if found.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| AI Deps explode image size | High | Medium | Monitor `uv tree` and `uv pip list` sizes. Advocate for "slim" versions of packages. |
| Rate Limit issues | Medium | Low | Ensure `tenacity` or `ratelimit` are up to date and used correctly. |
