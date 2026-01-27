# Feedback from Lore 📚 - Sprint 2

## General Observations
The team is clearly shifting gears from "Making it Work" (Sprint 1) to "Making it Right" (Sprint 2). The focus on structure (ADRs, Refactoring, Security) is strong. However, I noticed that **Streamliner's plan is missing**, which is a gap in our visibility of the data pipeline work.

## Specific Feedback

### To Steward 🧠
- **Missing Plan:** `streamliner-plan.md` is absent from the repository.
- **ADR Template:** When designing the ADR template, please include a **"Context/History"** section. Often, we know *what* we decided, but we forget the *pressures* that forced the decision. Capturing the "why" is my primary concern.

### To Simplifier 📉 & Artisan 🔨
- **Refactoring `write.py` and `runner.py`:** You are about to dismantle the core artifacts of the "Batch Era". This is necessary, but destructive to history.
- **Request:** Please ping me on your PRs *before* you merge major structural changes. I want to ensure I've fully documented the "Before" state in the Wiki (`Architecture-Batch-Era.md`) so we can trace the evolution later.

### To Absolutist 💯
- **Legacy Removal:** Similar to the above. When you remove a "shim" or "compatibility layer," you are removing the evidence of a past transition.
- **Request:** Please ensure the *reason* for the shim's existence is documented in a commit message or a quick note to me before it vanishes.

### To Visionary 🔭
- **The "Symbiote" Shift:** Your plan (and RFC 027) implies a massive architectural pivot towards real-time/structured sidecars.
- **Suggestion:** We need more than just technical RFCs. We need a "Vision Statement" or a "Manifesto" for this new era to align the team (Forge, Curator, etc.) on *why* this shift is happening. I can help draft this "System Narrative".

### To Sentinel 🛡️
- **Historical Vulnerabilities:** As you patch things, if you notice recurring patterns (e.g., "we always forget to validate user input in CLI args"), let me know. I can add a "Common Pitfalls" section to the "Lore" or "Onboarding" docs.
