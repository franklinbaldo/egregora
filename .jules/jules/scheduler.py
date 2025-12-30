"""Jules Scheduler."""

import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import frontmatter
import jinja2

# Import from new package relative to execution or absolute
from jules.client import JulesClient
from jules.github import get_open_prs, get_repo_info

# --- Standard Text Blocks ---

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


def load_schedule_registry(registry_path: Path) -> dict:
    if not registry_path.exists():
        return {}
    with open(registry_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("schedules", {})


def ensure_journals_directory(persona_dir: Path) -> None:
    """Ensure the journals directory exists for a persona."""
    journals_dir = persona_dir / "journals"
    journals_dir.mkdir(parents=True, exist_ok=True)


def collect_journals(persona_dir: Path) -> str:
    """Collects all journal entries from the journals/ subdirectory."""
    journals_dir = persona_dir / "journals"
    if not journals_dir.exists():
        return ""

    # Collect all .md files, sorted by name
    journal_files = sorted(journals_dir.glob("*.md"))
    # Limit to the last 10 entries
    if len(journal_files) > 10:
        journal_files = journal_files[-10:]

    entries = []

    for jf in journal_files:
        try:
            content = jf.read_text().strip()
            # If frontmatter exists, strip it
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()

            if content:
                entries.append(f"\n--- Journal Entry: {jf.name} ---\n{content}\n")
        except Exception:
            pass

    return "\n".join(entries)


def parse_prompt_file(filepath: Path, context: dict) -> dict:
    post = frontmatter.load(filepath)
    config = post.metadata
    body_template = post.content

    full_context = {**context, **config}
    env = jinja2.Environment()

    full_context["identity_branding"] = env.from_string(IDENTITY_BRANDING).render(**full_context)
    full_context["journal_management"] = env.from_string(JOURNAL_MANAGEMENT).render(**full_context)
    full_context["empty_queue_celebration"] = env.from_string(CELEBRATION).render(**full_context)
    full_context["pre_commit_instructions"] = env.from_string(PRE_COMMIT_INSTRUCTIONS).render(**full_context)

    rendered_body = env.from_string(body_template).render(**full_context)

    title = config.get("title", "Jules Task")
    if "{{" in title:
        title = env.from_string(title).render(**full_context)
        config["title"] = title

    return {"config": config, "prompt": rendered_body.strip()}


def check_schedule(schedule_str: str) -> bool:
    if not schedule_str:
        return False

    parts = schedule_str.split()
    if len(parts) != 5:
        return False

    _min_s, hour_s, _dom_s, _month_s, dow_s = parts
    now = datetime.now(timezone.utc)

    # Check Hour
    if hour_s != "*" and int(hour_s) != now.hour:
        return False

    # Check Day of Week
    if dow_s != "*":
        py_dow = now.weekday()  # 0=Mon
        cron_dow = (py_dow + 1) % 7
        if int(dow_s) != cron_dow:
            return False

    return True


def run_scheduler(
    command: str, run_all: bool = False, dry_run: bool = False, prompt_id: str | None = None
) -> None:
    client = JulesClient()
    repo_info = get_repo_info()
    prompts_dir = Path(".jules/personas")
    registry_path = Path(".jules/schedules.toml")

    if not prompts_dir.exists():
        sys.exit(1)

    open_prs = get_open_prs(repo_info["owner"], repo_info["repo"])
    base_context = {**repo_info, "open_prs": open_prs}
    if open_prs:
        pass

    prompt_files = list(prompts_dir.glob("*/prompt.md"))
    registry = load_schedule_registry(registry_path)

    for p_file in prompt_files:
        try:
            persona_dir = p_file.parent
            # Ensure journals directory exists before collecting
            ensure_journals_directory(persona_dir)
            journal_entries = collect_journals(persona_dir)

            raw_post = frontmatter.load(p_file)
            emoji = raw_post.metadata.get("emoji", "")

            context = {
                **base_context,
                "journal_entries": journal_entries,
                "emoji": emoji,
                "id": raw_post.metadata.get("id", ""),
            }

            parsed = parse_prompt_file(p_file, context)
            config = parsed["config"]
            prompt_body = parsed["prompt"]

            pid = config.get("id")
            if not pid:
                continue

            if prompt_id and prompt_id != pid:
                continue

            if not config.get("enabled", True):
                if prompt_id == pid:
                    pass
                else:
                    continue

            should_run = False
            schedule_str = registry.get(pid)

            if not schedule_str and config.get("schedule"):
                schedule_str = config.get("schedule")

            if run_all or (prompt_id == pid):
                should_run = True
            elif command == "tick":
                if schedule_str and check_schedule(schedule_str):
                    should_run = True
                elif not schedule_str:
                    pass

            if should_run:
                if not dry_run:
                    client.create_session(
                        prompt=prompt_body,
                        owner=repo_info["owner"],
                        repo=repo_info["repo"],
                        branch=config.get("branch", "main"),
                        title=config.get("title", f"Task: {pid}"),
                        automation_mode=config.get("automation_mode", "AUTO_CREATE_PR"),
                        require_plan_approval=config.get("require_plan_approval", False),
                    )
                else:
                    pass

        except Exception as e:
            # Print error to logs so we can debug failed prompts
            print(f"Error processing prompt {p_file.name}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
