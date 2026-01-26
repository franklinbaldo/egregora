# Plan: Absolutist - Sprint 3

**Persona:** Absolutist 💯
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to simplify the codebase by removing legacy code and backward compatibility layers based on rigorous evidence.

- [ ] **Remove Legacy Media Behavior:** Based on Sprint 2 investigation, remove the `att_file` legacy logic and obsolete markers from `src/egregora/ops/media.py`.
- [ ] **Remove `prompts.py` Shim:** If confirmed safe in Sprint 2, execute the removal of the legacy prompt compatibility layer.
- [ ] **Audit Input Adapters:** As we polish the "Mobile" experience, I will ensure our input adapters don't contain any legacy hacks for older mobile export formats that we no longer support.

## Dependencies
- **Curator:** Coordinate on "Related Content" to ensure we don't need any legacy search shims (TF-IDF etc.).

## Context
Sprint 3 focuses on "Mobile Polish". Ensuring our backend media handling is clean and efficient is a key part of supporting a high-quality mobile experience. Legacy hacks often slow down processing or cause unpredictable behavior.

## Expected Deliverables
1.  Removal of `att_file` legacy logic in `media.py`.
2.  Removal of `prompts.py` (if approved).
3.  Clean bill of health for input adapters.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Breaking Old Exports | Medium | Medium | Test with a corpus of old exports if available, or make a clear decision to drop support. |
