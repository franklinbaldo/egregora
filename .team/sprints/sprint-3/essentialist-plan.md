# Plan: Essentialist 💎 - Sprint 3

**Persona:** Essentialist 💎
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** Medium

## Objectives
My mission is to attack the "Meta-config" smell.

- [ ] **Simplify `EgregoraConfig`:** The configuration surface area is too large. I will audit `src/egregora/config/settings.py` and hardcode values that do not need to be exposed to users (e.g., specific API batch sizes, implementation details).
- [ ] **Enforce "One Good Path":** Identify and remove "options" that are actually just "legacy compatibility modes".
- [ ] **Review New Features:** Monitor Sprint 3 feature work (Discovery/Mobile Polish) to ensure no new "Homemade infra" is introduced.

## Dependencies
- **Bolt:** I need to ensure that removing config knobs doesn't prevent performance tuning where it matters (I will consult Bolt).

## Context
"Meta-config" (Too many knobs, env vars) increases the cognitive load for both users and maintainers. By Sprint 3, the core architecture should be stable enough to decide what is "opinionated default" vs "configurable".

## Expected Deliverables
1.  Reduced line count in `src/egregora/config/settings.py`.
2.  Simplified `EgregoraConfig` model.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Removing a knob someone uses | Medium | Low | I will check the `defaults.py` and ensuring the hardcoded value is the one everyone uses. |
