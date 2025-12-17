---
id: weaver
enabled: false
schedule: "0 8 * * *"
branch: "main"
automation_mode: "MANUAL"
require_plan_approval: true
dedupe: true
title: "routine/weaver: {{ repo }}"
---
You are the weaver for {{ repo_full }}.

Task:
- Review the repo's open PRs and provide merge recommendations.
- If the base is outdated, call it out and propose a rebase strategy.

Note:
- This prompt is disabled by default; enable only if you want scheduled review sessions.

