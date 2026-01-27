# Plan: Deps - Sprint 3

**Persona:** deps 📦
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
<<<<<<< HEAD

My mission is to operationalize dependency security and gatekeep new additions for the "Discovery" and "Mobile" features.

- [ ] **Automate Security Audits:** Collaborate with **Sentinel** to add `pip-audit` to the `pre-commit` or CI/CD pipeline, ensuring no vulnerable packages are merged.
- [ ] **Vet "Discovery" Dependencies:** Review any new packages proposed for the RAG/Content Discovery features (e.g., vector DB clients, NLP libs) to ensure they are well-maintained and minimal.
- [ ] **Audit Mobile Assets:** Ensure that "Mobile Polish" doesn't introduce heavy frontend assets or Python packages that bloat the install size.

## Dependencies

- **Sentinel:** We share the goal of automated security checks.
- **Visionary/Forge:** They will likely propose new dependencies for the Discovery features.

## Context

Sprint 3 introduces "Smart" features. In the Python ecosystem, "AI" and "Data" libraries are often heavy (numpy, pandas, torch). I must act as the gatekeeper to prevent Egregora from becoming bloated. We prefer "small and focused" over "monolithic and heavy".

## Expected Deliverables

1.  **CI/CD Security Check:** A GitHub Action or pre-commit hook running `pip-audit`.
2.  **Dependency Review Report:** A review of any new packages added in Sprint 3.
=======
Sprint 3 focuses on the "Symbiote Shift" and Context Layer. My role is to ensure this new layer doesn't bloat the project.

- [ ] **Audit Context Layer Deps:** Review dependencies introduced for Git history and code reference features.
- [ ] **Minimize "Sidecar" Weight:** Ensure the "Structured Sidecar" architecture doesn't duplicate dependencies or introduce heavy frameworks.
- [ ] **Routine Maintenance:** Regular updates (minor versions) and security scans.

## Dependencies
- **Visionary:** Will likely propose new tools for the Context Layer.
- **Bolt:** May introduce new performance-related libraries.

## Context
As we add new capabilities (Git understanding), the temptation to add libraries like `GitPython` or complex parsers will be high. I must advocate for "shelling out" to `git` or using simple internal parsers to keep the image size small.

## Expected Deliverables
1.  **Dependency Review Report:** A review of any new packages proposed for the Context Layer.
2.  **Updated Lockfile:** Routine maintenance updates.
>>>>>>> origin/pr/2882

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
<<<<<<< HEAD
| "Discovery" requires heavy ML libs | High | Medium | I will advocate for lightweight alternatives or API-based solutions (like the existing `google-genai`) to avoid local heavy lifting. |
| CI becomes too slow with audits | Low | Low | `pip-audit` is fast; we can cache the vulnerability DB. |

## Proposed Collaborations

- **With Sentinel:** Implementing the automated audit.
- **With Visionary:** Selecting lightweight libraries for RAG.
=======
| Feature bloat | Medium | Medium | I will strictly enforce the "stdlib first" philosophy. |
>>>>>>> origin/pr/2882
