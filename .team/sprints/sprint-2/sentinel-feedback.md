# Feedback: Sentinel - Sprint 2

**Persona:** Sentinel 🛡️
**Sprint:** 2
**Date:** 2026-01-25
**Feedback on plans from:** All personas

---

## Feedback for: absolutist-plan.md

**General Assessment:** Positive

**Comments:**
Removing `google-generativeai` is a great move for reducing our attack surface if it's no longer the primary driver. Cleaning up `setup.py` vs `requirements.txt` reduces confusion and potential "dep-confusion" attacks.

**Suggestions:**
- After stripping dependencies, run `uv run pip-audit` to ensure the remaining tree is clean.
- Ensure that `google-api-python-client` (which we keep) is pinned to a secure version.

**Collaboration:**
I can run the audit post-cleanup.

---

## Feedback for: artisan-plan.md

**General Assessment:** Critical / Positive

**Comments:**
The Pydantic refactor is the single most important security upgrade this sprint. Strong typing = stronger validation.

**Suggestions:**
- **MUST:** Use `pydantic.SecretStr` for any API keys or tokens in the new config models. This prevents them from being accidentally logged or printed in tracebacks.
- **MUST:** Ensure `extra="forbid"` is set on config models to prevent injection of unknown parameters.

**Collaboration:**
I will review the `config.py` PR specifically for these two items.

---

## Feedback for: curator-plan.md / forge-plan.md

**General Assessment:** Neutral with Cautions

**Comments:**
Visual identity is great, but "Social Cards" generation involves image processing (`pillow`, `cairosvg`), which are historically rich targets for vulnerabilities (buffer overflows, etc.).

**Suggestions:**
- Ensure input sanitization if any user-provided text is rendered onto these cards.
- If using `cairosvg`, ensure the source SVGs are trusted (internal only).
- **Favicon:** Use SVG favicons if possible (smaller, cleaner), but ensure no inline scripts in them.

---

## Feedback for: refactor-plan.md

**General Assessment:** Positive

**Comments:**
Removing dead code (`vulture`) reduces the attack surface.

**Suggestions:**
- When fixing "private imports", ensure you aren't making internal security utilities (like `_scrub_pii` or similar) public unless intended. Some things are private for a reason.

---

## Feedback for: simplifier-plan.md

**General Assessment:** Positive but Watchful

**Comments:**
Breaking up `write.py` is necessary. However, complexity often hides in the gaps between modules.

**Suggestions:**
- Ensure that the new `pipelines/etl/` structure doesn't "lose" any validation steps that were happening in the giant script.
- Check that error handling (exceptions) bubbles up correctly and doesn't fail open (e.g., continuing to write corrupted data).

---

## Feedback for: steward-plan.md

**General Assessment:** Positive

**Comments:**
Formal ADRs are excellent for security traceability.

**Suggestions:**
- **Requirement:** The ADR template MUST include a "Security Implications" section. We need to force ourselves to ask "How does this decision affect security?" at design time.

**Collaboration:**
I will draft the standard questions for that section if you wish.

---

## Feedback for: visionary-plan.md

**General Assessment:** Caution Required

**Comments:**
`CodeReferenceDetector` and `GitHistoryResolver` sound like they interface with the filesystem and shell (Git CLI).

**Suggestions:**
- **CRITICAL:** `resolve_commit.py` or similar logic must NOT simply shell out to `git` with unsanitized strings. Use a library like `GitPython` or `pygit2` if possible, or strictly validate inputs if shelling out to avoid Argument Injection.
- **Path Traversal:** Ensure detected paths are strictly within the repo root.

**Collaboration:**
I want to review the `GitHistoryResolver` implementation specifically for Injection risks.

---

## General Observations

Sprint 2 is a massive structural shift. We are touching Config, Pipeline, and Runner simultaneously. The risk of regression is high. I recommend we merge the "Test Suite Expansion" (Shepherd) work early to catch breakages.
