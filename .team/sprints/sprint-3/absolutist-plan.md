# Plan: Absolutist - Sprint 3

**Persona:** Absolutist 💯
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to simplify the codebase by removing legacy code and backward compatibility layers based on rigorous evidence.

- [ ] **Remove Legacy Media Behavior:** The `src/egregora/ops/media.py` file contains a "legacy behavior for att_file" comment. I will investigate and remove this fallback if it's no longer needed for modern WhatsApp exports.
- [ ] **Audit Input Adapters:** As we polish the "Mobile" experience, I will ensure our input adapters don't contain any legacy hacks for older mobile export formats that we no longer support.
- [ ] **Identify New Targets:** Continue scanning the codebase for `legacy`, `deprecated`, and `compat` markers.

## Dependencies
- **Curator:** Coordinate on "Related Content" to ensure we don't need any legacy search shims (TF-IDF etc.).

## Context
Sprint 3 focuses on "Mobile Polish". Ensuring our backend media handling is clean and efficient is a key part of supporting a high-quality mobile experience. Legacy hacks often slow down processing or cause unpredictable behavior.

## Expected Deliverables
1.  Removal of `att_file` legacy logic in `media.py`.
2.  Clean bill of health for input adapters.
3.  Updated `absolutist-plan.md` for Sprint 4.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Breaking Old Exports | Medium | Medium | Test with a corpus of old exports if available, or make a clear decision to drop support. |
