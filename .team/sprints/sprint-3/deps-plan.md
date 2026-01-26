# Plan: Deps 📦 - Sprint 3

**Persona:** Deps 📦
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to optimize the dependency tree for production readiness as we move towards release.

- [ ] **License Compliance Scan:** Audit all dependencies for non-permissive licenses (e.g., GPL) that might conflict with our project goals.
- [ ] **Heavyweight Analysis:** Investigate removal of `scikit-learn` or `pandas` if `ibis-framework` and `duckdb` can fully replace their functionality in the new "Real-Time" architecture.
- [ ] **Production vs Dev Split:** Strictly enforce separation of dependencies. Ensure no dev-tools leak into production builds.
- [ ] **Automated Dependency Updates:** Configure `renovate` or a similar tool for automated, safe dependency updates with CI checks.

## Dependencies
- **Simplifier:** Success of their refactor determines if we can drop `pandas`.
- **Sentinel:** License compliance policy definition.

## Context
As the "Egregora Mesh" and "Universal Context Layer" features land (RFC 028/026), the system complexity will grow. We must counter-balance this by aggressively pruning legacy data processing libraries if the new architecture renders them obsolete.

## Expected Deliverables
1.  **License Audit Report:** List of all licenses and any violations.
2.  **Slimmer Lockfile:** Target <250 resolved packages (currently ~280).
3.  **Renovate Config:** Optimized configuration for automated updates.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| `scikit-learn` is deeply embedded | High | Low | If removal is too hard, we keep it but ensure it's version-pinned. |
| License violation found late | Low | High | Run scan early in the sprint. |

## Proposed Collaborations
- **With Simplifier:** Discuss dropping `pandas`/`sklearn` in favor of pure DuckDB/Ibis.
- **With Sentinel:** Define the "Allowed License List".
