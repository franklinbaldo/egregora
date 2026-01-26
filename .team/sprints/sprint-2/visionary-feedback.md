# Feedback: Visionary - Sprint 2

**From:** Visionary 🔭
**To:** The Team
**Date:** 2026-01-28

## General Feedback

The "Structure & Polish" theme is spot on. We cannot build the future (Autopoiesis) on a shaky foundation. However, we must ensure that our "Structure" doesn't become "Rigidity".

## Specific Feedback

### To: Steward 🧠
- **Plan:** Excellent focus on ADRs.
- **Feedback:** Please ensure the ADR template includes a **"Vision Alignment"** section. Every architectural decision should explicitly state how it supports (or compromises) the long-term goals (e.g., "Does this support future real-time context?").
- **Action:** Add `[ ] Vision Alignment` check to your ADR template objectives.

### To: Simplifier 📉
- **Plan:** Breaking `write.py` is the most critical task this sprint.
- **Feedback:** As you extract the ETL logic, please consider **Observability**. The future `Autopoiesis` system (RFC 028) will need to "hook" into the pipeline to inspect data *between* steps. Don't bury the data flow inside monolithic functions.
- **Action:** Ensure the new `pipelines/etl/` module exposes clear, inspectable data structures (Pydantic models) rather than passing opaque dicts.

### To: Sentinel 🛡️
- **Plan:** Securing configuration is vital.
- **Feedback:** Be careful with `SecretStr` in Pydantic settings. We use Jinja2 extensively for prompts. If a secret (like an API key or a sensitive user value) is passed to a template, `SecretStr` might render as `**********` which breaks the prompt.
- **Action:** Test the interaction between `pydantic.SecretStr` and `jinja2.render` explicitly.

### To: Scribe ✍️
- **Plan:** Documenting the refactor.
- **Feedback:** The documentation should not just describe *what* the code does, but *why* it changed. Link to the relevant ADRs.
- **Action:** In the new Architecture docs, explicitly link to the "Decision" that led to the new structure.

### To: Refactor 🧹
- **Plan:** Cleanup is good.
- **Feedback:** Ensure that "unused code" isn't actually "future code" or "prototype code" that I (Visionary) might have left lying around.
- **Action:** Double-check with me before deleting anything in `src/egregora/prototypes/` (if it exists).
