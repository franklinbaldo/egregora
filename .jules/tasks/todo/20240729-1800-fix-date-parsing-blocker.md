---
id: 20240729-1800-fix-date-parsing-blocker
title: "🎭 CRITICAL: Fix Demo Generation Blocker - Invalid Date Parsing"
tags:
  - bug
  - critical
  - blocker
  - backend
persona: forge
status: todo
---

## 1. Why is this important?

**This is a critical, session-blocking bug.** The `uv run egregora demo` command is failing with a `RuntimeError`. This prevents the entire Curation Cycle, as I cannot generate a demo site to evaluate. No UX work can proceed until this is fixed.

The error is: `RuntimeError: Failed to persist post document: Failed to parse date string for frontmatter: '2025-10-28 14:10 to 14:15'.`

## 2. What needs to be done?

The Writer agent is generating a `date` field in post frontmatter that contains a date range (e.g., `'2025-10-28 14:10 to 14:15'`). The `python-frontmatter` library cannot parse this string, causing the application to crash.

The fix likely involves ensuring that the date provided to the frontmatter is a single, valid ISO 8601 timestamp. The most logical choice is to use the **start time** of the conversation window as the canonical `date` for the generated post.

### Implementation Steps:

1.  **Locate the logic:** The error originates from the LLM's output but is triggered during file persistence. Investigate `src/egregora/agents/tools/writer_tools.py` where the document is created and passed to the output format.
2.  **Sanitize the date:** Before writing the frontmatter, ensure the `date` value is a valid datetime object or a correctly formatted string. If the LLM provides a range, parse it and use the start date.
3.  **Ensure Robustness:** The fix should be robust enough to handle various date/time formats the LLM might output, always falling back to a parsable format.

## 3. How do I verify it's done?

1.  **The command MUST succeed:** Run `uv run egregora demo` multiple times. It must complete successfully without any `RuntimeError` related to date parsing.
2.  **Inspect the output:** Check the frontmatter of the generated markdown files in `demo/docs/posts/`. The `date` field should contain a single, valid timestamp (e.g., `date: 2025-10-28 14:10:00`).
