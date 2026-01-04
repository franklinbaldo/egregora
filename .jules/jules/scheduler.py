"""Jules Scheduler."""

import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    return data


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


def get_latest_jules_pr(open_prs: list[dict[str, Any]], personas: dict[str, Any]) -> dict[str, Any] | None:
    """Find the latest PR created by a Jules persona."""
    # Filter for Jules PRs (assuming author or title patterns)
    # Since 'author' from get_open_prs might be just login string or dict
    jules_prs = []

    # Create a mapping of emoji to persona ID for easier lookup
    emoji_to_id = {meta["emoji"]: pid for pid, meta in personas.items() if meta.get("emoji")}

    for pr in open_prs:
        # Check author (if available) - usually "app/google-labs-jules" or similar
        author = pr.get("author", {})
        login = author.get("login") if isinstance(author, dict) else str(author)

        # Also check title for persona emojis
        title = pr.get("title", "")

        is_jules = "jules" in login.lower()
        if not is_jules:
            # Fallback: check if title starts with a known persona emoji
            for emoji in emoji_to_id:
                if title.strip().startswith(emoji):
                    is_jules = True
                    break

        if is_jules:
            jules_prs.append(pr)

    if not jules_prs:
        return None

    # Sort by number descending (proxy for time) or creation date if available
    # get_open_prs returns simplified list, usually sorted by number desc by default from GH CLI
    # but let's sort by number just in case
    jules_prs.sort(key=lambda x: x.get("number", 0), reverse=True)
    return jules_prs[0]


def identify_persona_from_pr(pr: dict[str, Any], personas: dict[str, Any]) -> str | None:
    """Identify which persona created the PR based on title emoji or other markers."""
    title = pr.get("title", "").strip()

    # Check emojis
    for pid, meta in personas.items():
        emoji = meta.get("emoji")
        if emoji and title.startswith(emoji):
            return pid

    return None


def run_cycle_step(
    client: JulesClient,
    repo_info: dict,
    cycle_list: list[str],
    personas: dict[str, Any],
    open_prs: list[dict[str, Any]],
    dry_run: bool,
    base_context: dict
) -> None:
    """Run a single step of the cycle scheduler."""
    print(f"Running in CYCLE mode with order: {cycle_list}")

    latest_pr = get_latest_jules_pr(open_prs, personas)

    next_pid = cycle_list[0]
    base_branch = "main"

    if latest_pr:
        print(f"Found latest Jules PR: #{latest_pr['number']} - {latest_pr['title']}")
        last_pid = identify_persona_from_pr(latest_pr, personas)

        if last_pid and last_pid in cycle_list:
            # Find next in cycle
            idx = cycle_list.index(last_pid)
            next_idx = (idx + 1) % len(cycle_list)
            next_pid = cycle_list[next_idx]
            print(f"Last persona was {last_pid}. Next is {next_pid}.")
        else:
            print(f"Could not identify persona from PR or persona not in cycle. defaulting to start: {next_pid}")

        # Use the PR's branch as base
        base_branch = latest_pr.get("headRefName", "main")
        print(f"Chaining from branch: {base_branch}")

    else:
        print("No open Jules PRs found. Starting fresh cycle from main.")

    # Execute the next persona
    if next_pid not in personas:
        print(f"Error: Persona {next_pid} not found in configuration.", file=sys.stderr)
        return

    p_data = personas[next_pid]
    p_file = p_data["path"]

    try:
        persona_dir = p_file.parent
        ensure_journals_directory(persona_dir)
        journal_entries = collect_journals(persona_dir)

        # Load raw again to ensure clean state
        raw_post = frontmatter.load(p_file)

        context = {
            **base_context,
            "journal_entries": journal_entries,
            "emoji": raw_post.metadata.get("emoji", ""),
            "id": raw_post.metadata.get("id", ""),
        }

        parsed = parse_prompt_file(p_file, context)
        config = parsed["config"]
        prompt_body = parsed["prompt"]

        if not config.get("enabled", True):
             print(f"Skipping {next_pid} (disabled).")
             # In a real cycle we might want to skip to the NEXT one recursively,
             # but for now let's just abort this tick to avoid infinite loops if all disabled.
             return

        print(f"Starting session for {next_pid} on branch {base_branch}...")

        if not dry_run:
            client.create_session(
                prompt=prompt_body,
                owner=repo_info["owner"],
                repo=repo_info["repo"],
                branch=base_branch,
                title=config.get("title", f"Task: {next_pid}"),
                automation_mode=config.get("automation_mode", "AUTO_CREATE_PR"),
                require_plan_approval=config.get("require_plan_approval", False),
            )
        else:
            print(f"[Dry Run] Would create session for {next_pid}")

    except Exception as e:
        print(f"Error processing prompt {p_file.name}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()


def run_scheduler(
    command: str, run_all: bool = False, dry_run: bool = False, prompt_id: str | None = None
) -> None:
    client = JulesClient()
    repo_info = get_repo_info()
    prompts_dir = Path(".jules/personas")
    registry_path = Path(".jules/schedules.toml")

    if not prompts_dir.exists():
        sys.exit(1)

    # Load ALL personas first to have a lookup map
    prompt_files = list(prompts_dir.glob("*/prompt.md"))
    personas = {}
    for p_file in prompt_files:
        try:
            post = frontmatter.load(p_file)
            pid = post.metadata.get("id")
            if pid:
                personas[pid] = {
                    "path": p_file,
                    **post.metadata
                }
        except Exception:
            pass

    open_prs = get_open_prs(repo_info["owner"], repo_info["repo"])
    base_context = {**repo_info, "open_prs": open_prs}

    full_registry = load_schedule_registry(registry_path)
    schedules = full_registry.get("schedules", {})
    cycle_list = full_registry.get("cycle", [])

    # Check for Cycle Mode
    # If a prompt_id is provided, or run_all is set, we bypass cycle mode logic and run specific/all.
    # Cycle mode runs only on standard 'tick' without overrides, IF cycle list is present.
    is_cycle_mode = command == "tick" and not run_all and not prompt_id and bool(cycle_list)

    if is_cycle_mode:
        run_cycle_step(client, repo_info, cycle_list, personas, open_prs, dry_run, base_context)
        return

    # --- Standard Schedule / Manual Mode ---

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
            schedule_str = schedules.get(pid)

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
                    print(f"[Dry Run] Would create session for {pid}")

        except Exception as e:
            # Print error to logs so we can debug failed prompts
            print(f"Error processing prompt {p_file.name}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
