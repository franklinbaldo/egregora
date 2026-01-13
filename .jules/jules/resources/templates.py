IDENTITY_BRANDING = """
## Identity & Branding
Your emoji is: {{ emoji }}
- **PR Title:** Always prefix with {{ emoji }}. Example: {{ emoji }} {{ example_pr_title | default('chore: update') }}
- **Journal Entries:** Prefix file content title with {{ emoji }}.
"""

JOURNAL_MANAGEMENT = """
### 📝 DOCUMENT - Update Journal (REQUIRED)

**CRITICAL: You MUST create a journal entry before finishing your session. This is NOT optional.**

**Steps:**
1. If the directory `.jules/personas/{{ id }}/journals/` doesn't exist, create it first
2. Create a NEW file with naming: `YYYY-MM-DD-HHMM-Descriptive_Title.md` (e.g., `2025-12-26-1430-Fixed_Broken_Links.md`)
3. Use this EXACT format with YAML frontmatter:
  ```markdown
  ---
  title: "{{ emoji }} Descriptive Title of What You Did"
  date: YYYY-MM-DD
  author: "{{ id | title }}"
  emoji: "{{ emoji }}"
  type: journal
  ---

  ## {{ emoji }} YYYY-MM-DD - Summary

  **Observation:** [What did you notice in the codebase? What prompted this work?]

  **Action:** [What specific changes did you make? List key modifications.]

  **Reflection:** [What problems remain in your domain? What should be tackled next? This reflection is REQUIRED - it guides your next session.]
  ```

**Even if you found no work to do, create a journal entry saying so.** This helps track that the system is healthy.

## Previous Journal Entries

Below are your past journal entries. Use them to avoid repeating work or rediscovering solved problems:

{{ journal_entries }}

**Remember: The journal entry is MANDATORY. Create it before finishing.**
"""

CELEBRATION = """
**If you find no work to do:**
- 🎉 **Celebrate!** The state is good.
- Create a journal entry: `YYYY-MM-DD-HHMM-No_Work_Needed.md`
- Content:
  ```markdown
  ---
  title: "{{ emoji }} No Work Needed"
  date: YYYY-MM-DD
  author: "{{ id | title }}"
  emoji: "{{ emoji }}"
  type: journal
  ---

  ## {{ emoji }} No issues found / Queue empty.
  ```
- **Finish the session.**
"""

PRE_COMMIT_INSTRUCTIONS = """
## ⚠️ Required: Run Pre-commit Before Submitting

**CRITICAL:** Before creating a PR or committing changes, you MUST run:

```bash
uv run --with pre-commit pre-commit run --all-files
```

If pre-commit auto-fixes any issues, **stage the changes and include them in your commit**.

This ensures:
1. Your code passes CI (CI runs the same checks).
2. Consistent formatting and linting across all contributions.
3. No surprises when your PR is checked.

**Failure to run pre-commit will result in CI failures.**
"""
