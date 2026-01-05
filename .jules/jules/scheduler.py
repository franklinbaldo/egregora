"""Jules Scheduler."""

import csv
import sys
import tomllib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter
import jinja2

# Import from new package relative to execution or absolute
from jules.client import JulesClient
from jules.github import get_open_prs, get_repo_info, _extract_session_id, get_pr_details_via_gh
from jules.exceptions import JulesError, SchedulerError, BranchError, MergeError, GitHubError

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
    """Check if schedule matches current time.

    Supports cron expressions:
    - Exact value: "12" (match hour 12)
    - Wildcard: "*" (match any)
    - Step values: "*/2" (every 2 hours), "*/3" (every 3 hours), etc.

    """
    if not schedule_str:
        return False

    parts = schedule_str.split()
    if len(parts) != 5:
        return False

    _min_s, hour_s, _dom_s, _month_s, dow_s = parts
    now = datetime.now(timezone.utc)

    # Check Hour
    if hour_s != "*":
        # Handle step values like "*/2" (every 2 hours)
        if hour_s.startswith("*/"):
            try:
                step = int(hour_s[2:])
                if now.hour % step != 0:
                    return False
            except ValueError:
                return False
        else:
            # Exact hour match
            try:
                if int(hour_s) != now.hour:
                    return False
            except ValueError:
                return False

    # Check Day of Week
    if dow_s != "*":
        py_dow = now.weekday()  # 0=Mon
        cron_dow = (py_dow + 1) % 7
        try:
            if int(dow_s) != cron_dow:
                return False
        except ValueError:
            return False

    return True

# --- History Manager ---

class HistoryManager:
    def __init__(self, filepath: Path = Path(".jules/history.csv")):
        self.filepath = filepath
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.filepath.exists():
            with open(self.filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "session_id", "persona", "base_branch", "base_pr_number"])

    def get_last_entry(self) -> dict[str, str] | None:
        entries = []
        try:
            with open(self.filepath, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entries.append(row)
        except Exception:
            return None

        if not entries:
            return None
        return entries[-1]

    def append_entry(self, session_id: str, persona: str, base_branch: str, base_pr_number: str = "") -> None:
        with open(self.filepath, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now(timezone.utc).isoformat(),
                session_id,
                persona,
                base_branch,
                base_pr_number
            ])

    def commit_history(self) -> None:
        """Commits and pushes the history file."""
        try:
            # Check if there are changes
            status = subprocess.run(["git", "status", "--porcelain", str(self.filepath)], capture_output=True, text=True)
            if not status.stdout.strip():
                return

            # Configure git if needed (CI environment)
            subprocess.run(["git", "config", "user.name", "Jules Bot"], check=False)
            subprocess.run(["git", "config", "user.email", "jules-bot@google.com"], check=False)

            subprocess.run(["git", "add", str(self.filepath)], check=True)
            subprocess.run(["git", "commit", "-m", "chore: update jules session history"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("Successfully pushed session history.")
        except Exception as e:
            print(f"Failed to push session history: {e}", file=sys.stderr)


def get_pr_by_session_id(open_prs: list[dict[str, Any]], session_id: str) -> dict[str, Any] | None:
    """Find a PR that matches the given session ID."""
    for pr in open_prs:
        # Check title or branch for session ID
        # We can reuse _extract_session_id but need to be careful with branch format
        head_ref = pr.get("headRefName", "")
        body = pr.get("body", "") or "" # body might be None

        extracted_id = _extract_session_id(head_ref, body)
        if extracted_id == session_id:
            return pr

    return None

JULES_BRANCH = "jules"


def ensure_jules_branch_exists() -> None:
    """Ensure the 'jules' branch exists, creating it from main if needed.
    
    Raises:
        BranchError: If any branch operation fails.
    """
    try:
        # Fetch latest
        subprocess.run(["git", "fetch", "origin"], check=True, capture_output=True)
        
        # Check if jules branch exists on remote
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", JULES_BRANCH],
            capture_output=True, text=True, check=True
        )
        
        if result.stdout.strip():
            print(f"Branch '{JULES_BRANCH}' exists on remote.")
            return
        
        # Jules branch doesn't exist - create it from main
        print(f"Branch '{JULES_BRANCH}' doesn't exist. Creating from main...")
        
        # Get main SHA
        result = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            capture_output=True, text=True, check=True
        )
        main_sha = result.stdout.strip()
        
        # Create jules branch pointing to main
        subprocess.run(
            ["git", "push", "origin", f"{main_sha}:refs/heads/{JULES_BRANCH}"],
            check=True, capture_output=True
        )
        print(f"Created '{JULES_BRANCH}' branch from main at {main_sha[:12]}")
        
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        raise BranchError(f"Failed to ensure jules branch exists: {stderr}") from e


def merge_pr_into_jules(pr_number: int) -> None:
    """Merge a PR into the jules branch using gh CLI.
    
    Args:
        pr_number: The PR number to merge.
        
    Raises:
        MergeError: If the merge operation fails.
    """
    try:
        print(f"Merging PR #{pr_number} into '{JULES_BRANCH}'...")
        
        # Ensure PR is ready for review (not a draft)
        subprocess.run(
            ["gh", "pr", "ready", str(pr_number)],
            capture_output=True, text=True, check=False # Ignore errors if already ready
        )

        # Use gh pr merge with --merge as squash is disabled in this repo
        subprocess.run(
            ["gh", "pr", "merge", str(pr_number), "--merge", "--delete-branch"],
            capture_output=True, text=True, check=True
        )
        print(f"Successfully merged PR #{pr_number} into '{JULES_BRANCH}'")
        
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        raise MergeError(f"Failed to merge PR #{pr_number}: {stderr}") from e


def is_pr_green(pr_details: dict[str, Any]) -> bool:
    """Check if all PR status checks are passing."""
    status_check_rollup = pr_details.get("statusCheckRollup", [])
    if not status_check_rollup:
        # If no checks, we assume it's safe to proceed (or repo doesn't have CI)
        # But usually we expect checks. Let's assume True if empty,
        # unless there's a reason to believe checks are required but missing.
        return True

    for check in status_check_rollup:
        # Normalized status fields
        status = check.get("conclusion") or check.get("status") or check.get("state")

        # Consider these statuses as "not finished/passed"
        # SUCCESS, NEUTRAL, SKIPPED are OK.
        # FAILURE, TIMED_OUT, CANCELLED, ACTION_REQUIRED are FAIL.
        # PENDING, IN_PROGRESS, QUEUED are WAIT.

        if status in ["SUCCESS", "success", "NEUTRAL", "neutral", "SKIPPED", "skipped", "COMPLETED", "completed"]:
            continue

        # If any check is not in the safe list, return False
        return False

    return True

def run_cycle_step(
    client: JulesClient,
    repo_info: dict,
    cycle_list: list[str],
    personas: dict[str, Any],
    open_prs: list[dict[str, Any]],
    dry_run: bool,
    base_context: dict
) -> None:
    """Run a single step of the cycle scheduler.
    
    This uses a persistent 'jules' branch that accumulates all work:
    1. Ensure 'jules' branch exists (create from main if not)
    2. If there's a pending PR from the last session, check if it's green
    3. If green, merge it into 'jules' branch
    4. Start the next session from 'jules' branch
    """
    print(f"Running in CYCLE mode with order: {cycle_list}")

    # Ensure jules branch exists
    ensure_jules_branch_exists()

    history_mgr = HistoryManager()
    last_entry = history_mgr.get_last_entry()

    next_pid = cycle_list[0]

    if last_entry:
        last_sid = last_entry["session_id"]
        last_pid = last_entry["persona"]
        print(f"Last recorded session: {last_sid} ({last_pid})")

        # Find the PR for this session
        pr = get_pr_by_session_id(open_prs, last_sid)

        if pr:
            pr_number = pr["number"]
            print(f"Found PR for last session: #{pr_number} - {pr['title']}")

            # Check if PR is Green
            pr_details = get_pr_details_via_gh(pr_number)
            
            if not is_pr_green(pr_details):
                print(f"PR #{pr_number} is not green (CI pending or failed). Waiting for CI/Autofix.")
                return

            # PR is green! Merge it into jules branch
            print(f"PR #{pr_number} is green! Merging into '{JULES_BRANCH}'...")
            if not dry_run:
                merge_pr_into_jules(pr_number)
            else:
                print(f"[Dry Run] Would merge PR #{pr_number} into '{JULES_BRANCH}'")

            # Determine next persona
            if last_pid in cycle_list:
                idx = cycle_list.index(last_pid)
                next_idx = (idx + 1) % len(cycle_list)
                next_pid = cycle_list[next_idx]
            else:
                # If last persona not in current cycle, start from beginning
                print(f"Last persona {last_pid} not in cycle list. Restarting cycle.")

            print(f"Next persona: {next_pid}. Starting from '{JULES_BRANCH}'.")
        else:
            print(f"PR for session {last_sid} not found in OPEN PRs. Waiting for it to appear or manual intervention.")
            return

    else:
        print(f"No history found. Starting fresh cycle from '{JULES_BRANCH}'.")

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
             return

        print(f"Starting session for {next_pid} on branch '{JULES_BRANCH}'...")

        session_id = "dry-run-session-id"
        if not dry_run:
            result = client.create_session(
                prompt=prompt_body,
                owner=repo_info["owner"],
                repo=repo_info["repo"],
                branch=JULES_BRANCH,
                title=config.get("title", f"Task: {next_pid}"),
                automation_mode=config.get("automation_mode", "AUTO_CREATE_PR"),
                require_plan_approval=config.get("require_plan_approval", False),
            )
            # result['name'] is like "sessions/uuid"
            session_id = result.get("name", "").split("/")[-1]
            session_url = f"https://jules.google.com/sessions/{session_id}"
            print(f"Created session: {session_id}")
            print(f"🔗 Jules Session URL: {session_url}")

            # Update History
            history_mgr.append_entry(session_id, next_pid, JULES_BRANCH, "")
            history_mgr.commit_history()

        else:
            print(f"[Dry Run] Would create session for {next_pid} and update history.")

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
                    result = client.create_session(
                        prompt=prompt_body,
                        owner=repo_info["owner"],
                        repo=repo_info["repo"],
                        branch=config.get("branch", "main"),
                        title=config.get("title", f"Task: {pid}"),
                        automation_mode=config.get("automation_mode", "AUTO_CREATE_PR"),
                        require_plan_approval=config.get("require_plan_approval", False),
                    )
                    session_id = result.get("name", "").split("/")[-1]
                    session_url = f"https://jules.google.com/sessions/{session_id}"
                    print(f"Created session for {pid}: {session_id}")
                    print(f"🔗 Jules Session URL: {session_url}")
                else:
                    print(f"[Dry Run] Would create session for {pid}")

        except Exception as e:
            # Propagate critical errors, log others
            if isinstance(e, (SchedulerError, JulesError)):
                raise
            
            print(f"Error processing prompt {p_file.name}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            # If we're in a critical cycle, we might want to raise, 
            # but for regular tick we just continue
