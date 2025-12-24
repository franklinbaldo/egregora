"""Jules Scheduler."""

import os
import sys
import argparse
import glob
import subprocess
import json
from datetime import datetime
from pathlib import Path
import tomllib

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
### 📝 DOCUMENT - Update Journal
- Create a NEW file in `.jules/personas/{{ id }}/journals/`
- Naming convention: `YYYY-MM-DD-HHMM-Any_Title_You_Want.md`
- **CRITICAL:** Start with YAML Frontmatter:
  ```markdown
  ---
  title: "{{ emoji }} Any Title You Want"
  date: YYYY-MM-DD
  author: "{{ id | title }}"
  emoji: "{{ emoji }}"
  type: journal
  ---

  ## {{ emoji }} YYYY-MM-DD - Topic
  **Observation:** [What did you notice?]
  **Action:** [What did you do?]
  ```

## Previous Journal Entries

Below are the aggregated entries from previous sessions. Use them to avoid repeating mistakes or rediscovering solved problems.

{{ journal_entries }}
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

def load_schedule_registry(registry_path: Path) -> dict:
    if not registry_path.exists():
        return {}
    with open(registry_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("schedules", {})

def collect_journals(persona_dir: Path) -> str:
    """Collects all journal entries from the journals/ subdirectory."""
    journals_dir = persona_dir / "journals"
    if not journals_dir.exists():
        return ""

    # Collect all .md files, sorted by name
    journal_files = sorted(list(journals_dir.glob("*.md")))
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

    rendered_body = env.from_string(body_template).render(**full_context)

    title = config.get("title", "Jules Task")
    if "{{" in title:
         title = env.from_string(title).render(**full_context)
         config["title"] = title

    return {
        "config": config,
        "prompt": rendered_body.strip()
    }

def check_schedule(schedule_str: str) -> bool:
    if not schedule_str:
        return False

    parts = schedule_str.split()
    if len(parts) != 5:
        return False

    min_s, hour_s, dom_s, month_s, dow_s = parts
    now = datetime.utcnow()

    # Check Hour
    if hour_s != "*" and int(hour_s) != now.hour:
        return False

    # Check Day of Week
    if dow_s != "*":
        py_dow = now.weekday() # 0=Mon
        cron_dow = (py_dow + 1) % 7
        if int(dow_s) != cron_dow:
            return False

    return True

def run_scheduler(
    command: str, 
    run_all: bool = False, 
    dry_run: bool = False, 
    prompt_id: str | None = None
) -> None:
    client = JulesClient()
    repo_info = get_repo_info()
    prompts_dir = Path(".jules/personas")
    registry_path = Path(".jules/schedules.toml")

    if not prompts_dir.exists():
        print(f"Prompts directory {prompts_dir} not found")
        sys.exit(1)

    print(f"Repo context: {repo_info}")

    open_prs = get_open_prs(repo_info["owner"], repo_info["repo"])
    base_context = {**repo_info, "open_prs": open_prs}
    if open_prs:
        print(f"Fetched {len(open_prs)} open PRs for context.")

    prompt_files = list(prompts_dir.glob("*/prompt.md"))
    registry = load_schedule_registry(registry_path)
    print(f"Loaded {len(registry)} schedules from registry.")
    print(f"Found {len(prompt_files)} persona definitions.")

    for p_file in prompt_files:
        try:
            persona_dir = p_file.parent
            journal_entries = collect_journals(persona_dir)
            
            raw_post = frontmatter.load(p_file)
            emoji = raw_post.metadata.get("emoji", "")

            context = {
                **base_context,
                "journal_entries": journal_entries,
                "emoji": emoji,
                "id": raw_post.metadata.get("id", "")
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
                    print(f"Warning: Prompt {pid} is disabled but explicitly requested.")
                else:
                    continue

            should_run = False
            schedule_str = registry.get(pid)

            if not schedule_str and config.get("schedule"):
                schedule_str = config.get("schedule")
                print(f"Warning: Using deprecated frontmatter schedule for {pid}: {schedule_str}")

            if run_all or (prompt_id == pid):
                should_run = True
            elif command == "tick":
                if schedule_str and check_schedule(schedule_str):
                    should_run = True
                elif not schedule_str:
                     pass

            if should_run:
                print(f"Running prompt: {pid}")
                if not dry_run:
                    resp = client.create_session(
                        prompt=prompt_body,
                        owner=repo_info["owner"],
                        repo=repo_info["repo"],
                        branch=config.get("branch", "main"),
                        title=config.get("title", f"Task: {pid}"),
                        automation_mode=config.get("automation_mode", "AUTO_CREATE_PR"),
                        require_plan_approval=config.get("require_plan_approval", False)
                    )
                    print(f"Session created: {resp.get('name')}")
                else:
                    print(f"[Dry Run] Would create session for {pid}")

        except ValueError:
            pass
        except Exception as e:
            print(f"Error processing {p_file}: {e}")
