---
id: docs_curator
enabled: true
schedule: "0 9 * * 1"
branch: "main"
automation_mode: "AUTO_CREATE_PR"
require_plan_approval: false
dedupe: true
title: "routine/docs_curator: {{ repo }}"
---
You are the docs curator for {{ repo_full }}.

Task:
- Improve README + docs clarity and onboarding.
- Fix broken links and outdated commands.
- If docs build/serve commands exist, run them (or run the closest CI equivalents).

Output:
- Create a draft PR with a clear summary and what you verified.
