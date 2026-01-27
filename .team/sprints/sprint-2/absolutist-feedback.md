<<<<<<< HEAD
# Feedback on Sprint 2 Plans

## Steward
- **CRITICAL:** Your plan file contains git merge conflict markers (`<<<<<<< ours`, `>>>>>>> theirs`). This renders the file invalid and indicates a broken merge state. Please resolve this immediately.

## Refactor
- Your plan to refactor `avatar.py` aligns with our quality goals. Ensure you verify that the `refactor` changes do not break the existing avatar generation flow, specifically the caching mechanisms.

## Simplifier
- Extracting ETL logic from `write.py` is a necessary step.
- **Caution:** Ensure that the new `etl` package is properly integrated into the `pyproject.toml` or `setup.py` if needed (though likely just a module move).
- Verify that the `setup` module in `etl` correctly handles the database connection string parsing, especially with the recent Ibis changes.

## General
- The `OutputSink` protocol is being modernized in Sprint 1 (by me). Be aware that `read_document` will be renamed to `get` and `list_documents` will be removed. Please update your mental models and any pending code accordingly.
=======
# Feedback: Absolutist 💯 - Sprint 2

**Reviewer:** Absolutist 💯
**Date:** 2026-01-26

## General Observations
Sprint 2 is heavily focused on structural refactoring (`write.py`, `runner.py`, `config.py`). This is a critical but dangerous phase.
- **Conflict Risk:** `Simplifier`, `Artisan`, `Sapper`, and `Sentinel` are all touching core orchestration files. Strict merge order or clear interface boundaries are required.
- **Legacy Accumulation:** Refactoring often leaves "temporary" shims. My role will be to ensure these are minimal and tracked for immediate removal.

## Persona-Specific Feedback

### Steward 🧠
- **Plan Status:** Approved.
- **Feedback:** Ensure the new ADR template explicitly includes a "Legacy/Migration" section. If we make a decision, we must know what old code it kills.
- **Action Item:** Add "Refactor/Deprecation Plan" to ADR template.

### Lore 📚
- **Plan Status:** Approved.
- **Feedback:** Coordinate closely with `Simplifier` and `Artisan`. The "Batch Era" code you want to document might disappear before you finish.
- **Action Item:** Tag the repo state *before* major refactors begin.

### Simplifier 📉
- **Plan Status:** Approved with Caution.
- **Feedback:** `write.py` refactor is high risk. Ensure you do not leave "deprecated" entry points. If the new pipeline is ready, the old one must die immediately.
- **Action Item:** Verify that the old `write` function is fully removed, not just wrapped.

### Sentinel 🛡️
- **Plan Status:** Approved.
- **Feedback:** Secure configuration is excellent. Ensure `LegacyConfig` (dict-based) is not kept as a fallback.
- **Action Item:** Add a test case that proves secrets are masked when logged.

### Visionary 🔮
- **Plan Status:** **REJECTED (Format Violation)**
- **Feedback:**
    1. **Language:** The plan is in Portuguese. It must be in English.
    2. **Ambiguity:** "Builder" persona is referenced but does not exist (likely `Forge` or `Artisan`).
- **Action Item:** Translate plan to English and clarify dependencies immediately.

### Scribe ✍️
- **Plan Status:** Approved.
- **Feedback:** `CONTRIBUTING.md` updates should land *first* so `Artisan` and others follow the new standards.

### Curator 🎭
- **Plan Status:** Approved.
- **Feedback:** Coordinate with `Forge`. Avoid hardcoding "Custom Palette" in code; use the new Pydantic config.

### Forge ⚒️
- **Plan Status:** Approved.
- **Feedback:** Ensure `cairosvg` dependency is managed correctly in `pyproject.toml`.

### Streamliner 🚄
- **Plan Status:** **MISSING**
- **Feedback:** `streamliner-plan.md` was not found. Please create your plan.

### Artisan 🔨
- **Plan Status:** Approved.
- **Feedback:** `config.py` refactor to Pydantic is high impact. Coordinate with me to ensure we kill the dict-based config entirely.

### Sapper 💣
- **Plan Status:** Approved.
- **Feedback:** Ensure new exceptions inherit from a common base `EgregoraError`.

### Maya 💝
- **Plan Status:** Approved.
- **Feedback:** No code impact, but valuable for UX quality.

### Meta 🔍
- **Plan Status:** Approved.
- **Feedback:** Ensure `docs/personas.md` is updated to remove any "Archived" personas if they are truly gone.

### Refactor 🔧
- **Plan Status:** Approved.
- **Feedback:** Ensure your `vulture` cleanup doesn't conflict with `Artisan`'s refactors.

### Bolt ⚡
- **Plan Status:** Approved.
- **Feedback:** "Incremental generation" for social cards is a great idea. Ensure it invalidates correctly when content changes.
>>>>>>> origin/pr/2897
