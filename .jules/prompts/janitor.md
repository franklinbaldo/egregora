---
id: janitor
enabled: true
schedule: "0 8 * * *"
branch: "main"
automation_mode: "AUTO_CREATE_PR"
require_plan_approval: false
dedupe: true
title: "routine/janitor: {{ repo }}"
---
You are the repo's janitor.

Task:
- Do a small, safe cleanup in {{ repo_full }} (docs/formatting/refactors allowed, but no risky changes).
- Run existing tests/linters if available.
- If you change CI/workflows, explain why.
