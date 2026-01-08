"""Jules Scheduler."""

import sys
import tomllib
import subprocess
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter
import jinja2

# Import from new package relative to execution or absolute
from jules.client import JulesClient
from jules.github import (
    get_open_prs,
    get_repo_info,
    _extract_session_id,
    get_pr_details_via_gh,
    get_pr_by_session_id_any_state,
)
from jules.exceptions import JulesError, SchedulerError, BranchError, MergeError, GitHubError

# --- Sprint Manager ---

class SprintManager:
    """Manages sprint lifecycle and provides context to personas."""
    
    SPRINTS_DIR = Path(".jules/sprints")
    CURRENT_FILE = SPRINTS_DIR / "current.txt"
    
    def __init__(self, repo_path: Path = Path(".")):
        self.repo_path = repo_path
        self.sprints_dir = self.repo_path / self.SPRINTS_DIR
        self.current_file = self.repo_path / self.CURRENT_FILE
        self._ensure_structure()
    
    def _ensure_structure(self) -> None:
        """Ensure sprint directory structure exists."""
        if not self.sprints_dir.exists():
            self.sprints_dir.mkdir(parents=True)
        
        if not self.current_file.exists():
            self.current_file.write_text("1\n")
            # Create initial sprint directories
            for i in range(1, 4):
                sprint_dir = self.sprints_dir / f"sprint-{i}"
                sprint_dir.mkdir(exist_ok=True)
    
    def get_current_sprint(self) -> int:
        """Get the current sprint number."""
        try:
            return int(self.current_file.read_text().strip())
        except (ValueError, FileNotFoundError):
            return 1
    
    def increment_sprint(self) -> int:
        """Increment to the next sprint and create necessary directories."""
        current = self.get_current_sprint()
        next_sprint = current + 1
        
        # Update current.txt
        self.current_file.write_text(f"{next_sprint}\n")
        
        # Create directories for next sprints if they don't exist
        for offset in [0, 1, 2]:
            sprint_num = next_sprint + offset
            sprint_dir = self.sprints_dir / f"sprint-{sprint_num}"
            sprint_dir.mkdir(exist_ok=True)
            
            # Create README if it doesn't exist
            readme = sprint_dir / "README.md"
            if not readme.exists():
                readme.write_text(f"# Sprint {sprint_num}\n\n**Status:** Planned\n")
        
        print(f"Sprint incremented: {current} → {next_sprint}")
        return next_sprint

    def get_sprint_context(self, persona: str) -> str:
        """Generate prompt context for a persona about sprints."""
        current = self.get_current_sprint()
        next_sprint = current + 1
        plus_2 = current + 2
        
        # List existing plans
        next_dir = self.sprints_dir / f"sprint-{next_sprint}"
        plus_2_dir = self.sprints_dir / f"sprint-{plus_2}"
        
        next_plans = [p.name for p in next_dir.glob("*-plan.md")] if next_dir.exists() else []
        plus_2_plans = [p.name for p in plus_2_dir.glob("*-plan.md")] if plus_2_dir.exists() else []
        
        prompt = f"""
## 🏃 Sprint Planning Context

**Current Sprint:** {current}

You are working in Sprint {current}. As part of your work, you should:

### 1. Complete Your Regular Tasks
Execute your normal persona responsibilities as defined in your prompt.

### 2. Read Other Personas' Plans

**For Sprint {next_sprint}:**
"""
        if next_plans:
            prompt += "\n".join([f"- `.jules/sprints/sprint-{next_sprint}/{plan}`" for plan in next_plans])
        else:
            prompt += f"(No plans created yet for sprint-{next_sprint})"
        
        prompt += f"""

**For Sprint {plus_2}:**
"""
        if plus_2_plans:
            prompt += "\n".join([f"- `.jules/sprints/sprint-{plus_2}/{plan}`" for plan in plus_2_plans])
        else:
            prompt += f"(No plans created yet for sprint-{plus_2})"
        
        prompt += f"""

### 3. Provide Feedback

After reading other personas' plans for sprint-{next_sprint}, create:
- `.jules/sprints/sprint-{next_sprint}/{persona}-feedback.md`

### 4. Create Your Plans

Create or update your plans for future sprints:
- `.jules/sprints/sprint-{next_sprint}/{persona}-plan.md`
- `.jules/sprints/sprint-{plus_2}/{persona}-plan.md`

Use the templates in `.jules/sprints/TEMPLATE-*.md` as guides.
"""
        return prompt

# Global instance
sprint_manager = SprintManager()

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


def load_prompt_entries(prompts_dir: Path, cycle_list: list[str]) -> list[dict[str, Any]]:
    """Load prompt metadata for scheduler execution."""
    entries: list[dict[str, Any]] = []
    if cycle_list:
        base_dir = prompts_dir.parent
        for rel_path in cycle_list:
            p_file = (base_dir / rel_path).resolve()
            if not p_file.exists():
                print(f"Cycle prompt not found: {rel_path}", file=sys.stderr)
                continue
            try:
                post = frontmatter.load(p_file)
                pid = post.metadata.get("id")
                emoji = post.metadata.get("emoji", "")
                title = post.metadata.get("title", "")
                if not pid:
                    print(f"Cycle prompt missing id: {rel_path}", file=sys.stderr)
                    continue
                entries.append(
                    {"id": pid, "path": p_file, "rel_path": rel_path, "emoji": emoji, "title": title}
                )
            except Exception as exc:
                print(f"Failed to load cycle prompt {rel_path}: {exc}", file=sys.stderr)
        return entries

    base_dir = prompts_dir.parent
    for p_file in prompts_dir.glob("*/prompt.md"):
        try:
            post = frontmatter.load(p_file)
            pid = post.metadata.get("id")
            emoji = post.metadata.get("emoji", "")
            title = post.metadata.get("title", "")
            if pid:
                rel_path = str(p_file.relative_to(base_dir))
                entries.append(
                    {"id": pid, "path": p_file, "rel_path": rel_path, "emoji": emoji, "title": title}
                )
        except Exception:
            pass

    return entries


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

    # Add sprint context to the body
    sprint_context = sprint_manager.get_sprint_context(config.get("id", "unknown"))
    body_template += sprint_context

    rendered_body = env.from_string(body_template).render(**full_context)

    title = config.get("title", "Jules Task")
    if "{{" in title:
        title = env.from_string(title).render(**full_context)
        config["title"] = title

    return {"config": config, "prompt": rendered_body.strip()}


def check_schedule(schedule_str: str) -> bool:
    """Check if schedule matches current time."""
    if not schedule_str:
        return False

    parts = schedule_str.split()
    if len(parts) != 5:
        return False

    _min_s, hour_s, _dom_s, _month_s, dow_s = parts
    now = datetime.now(timezone.utc)

    # Check Hour
    if hour_s != "*":
        if hour_s.startswith("*/"):
            try:
                step = int(hour_s[2:])
                if now.hour % step != 0:
                    return False
            except ValueError:
                return False
        else:
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

def get_pr_by_session_id(open_prs: list[dict[str, Any]], session_id: str) -> dict[str, Any] | None:
    """Find a PR that matches the given session ID."""
    for pr in open_prs:
        head_ref = pr.get("headRefName", "")
        body = pr.get("body", "") or ""
        extracted_id = _extract_session_id(head_ref, body)
        if extracted_id == session_id:
            return pr
    return None

def _match_persona_from_title(title: str, cycle_entries: list[dict[str, Any]]) -> str | None:
    title_lower = title.lower()
    for entry in cycle_entries:
        pid = entry.get("id", "")
        emoji = entry.get("emoji", "")
        if pid and pid.lower() in title_lower:
            return pid
        if emoji and emoji in title:
            return pid
    return None


def get_last_cycle_session(
    client: JulesClient,
    cycle_entries: list[dict[str, Any]],
    repo_info: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Find the most recent session that matches one of the cycle personas."""
    response = client.list_sessions()
    sessions = response.get("sessions", [])
    repo_name = repo_info.get("repo", "")

    candidates: list[tuple[str, dict[str, Any], str]] = []
    for session in sessions:
        title = session.get("title") or ""
        if repo_name and repo_name not in title:
            continue
        persona_id = _match_persona_from_title(title, cycle_entries)
        if persona_id:
            candidates.append((session.get("createTime", ""), session, persona_id))

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: item[0], reverse=True)
    latest = candidates[0][1]
    latest_persona = candidates[0][2]
    session_name = latest.get("name", "")
    session_id = session_name.split("/")[-1] if session_name else None
    return session_id, latest_persona

JULES_BRANCH = "jules"

def prepare_session_base_branch(
    base_branch: str,
    base_pr_number: str = "",
    last_session_id: str | None = None,
) -> str:
    """Create a short, stable base branch before starting a Jules session."""
    if base_pr_number and last_session_id:
        base_ref = f"jules-pr{base_pr_number}-{last_session_id}"
    elif base_pr_number:
        base_ref = f"jules-pr{base_pr_number}"
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        base_ref = f"jules-main-{stamp}"

    try:
        subprocess.run(["git", "fetch", "origin", base_branch], check=True, capture_output=True)
        result = subprocess.run(
            ["git", "rev-parse", f"origin/{base_branch}"],
            capture_output=True, text=True, check=True
        )
        base_sha = result.stdout.strip()
        print(f"Base branch '{base_branch}' is at SHA: {base_sha[:12]}")

        subprocess.run(
            ["git", "push", "origin", f"{base_sha}:refs/heads/{base_ref}"],
            check=True, capture_output=True
        )
        print(f"Prepared base branch '{base_ref}' from {base_branch}")
        return base_ref
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        print(f"Failed to prepare base branch: {stderr}", file=sys.stderr)
        print(f"Falling back to base branch: {base_branch}")
        return base_branch

def is_jules_drifted() -> bool:
    """Check if the 'jules' branch is drifted (unmergeable) with 'main'."""
    try:
        result = subprocess.run(
            ["git", "merge-tree", "--write-tree", "origin/" + JULES_BRANCH, "origin/main"],
            capture_output=True, text=True
        )
        if result.returncode == 1:
            print(f"Drift detected: Conflicting changes between 'origin/{JULES_BRANCH}' and 'origin/main'.")
            return True
        if result.returncode > 1:
            stderr = result.stderr.strip()
            print(f"Warning: git merge-tree failed with code {result.returncode}: {stderr}. Assuming NO drift to avoid accidental rotation.")
            return False
        return False
    except Exception as e:
        print(f"Warning: Error checking drift: {e}. Assuming NO drift.")
        return False

def rotate_drifted_jules_branch() -> None:
    """Rename drifted jules branch with sprint number."""
    current_sprint = sprint_manager.get_current_sprint()
    drift_branch = f"{JULES_BRANCH}-sprint-{current_sprint}"
    
    print(f"Drift detected in '{JULES_BRANCH}'. Rotating to '{drift_branch}'...")
    
    try:
        subprocess.run(
            ["git", "push", "origin", f"origin/{JULES_BRANCH}:refs/heads/{drift_branch}"],
            check=True, capture_output=True
        )
        
        pr_title = f"Sprint {current_sprint} - Drifted work from {JULES_BRANCH}"
        pr_body = (
            f"This PR contains work from Sprint {current_sprint}.\n\n"
            f"**Sprint:** {current_sprint}\n"
            f"**Branch:** {drift_branch}\n\n"
            "The `jules` branch became unmergeable with `main`. "
            "Please review and merge manually if needed."
        )
        
        try:
            subprocess.run(
                ["gh", "pr", "create", "--head", drift_branch, "--base", "main",
                 "--title", pr_title, "--body", pr_body],
                check=True, capture_output=True
            )
            print(f"Created PR for sprint {current_sprint}: {drift_branch}")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            print(f"Warning: Failed to create PR for drift branch: {stderr}", file=sys.stderr)
            
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        print(f"Warning: Failed to rotate jules branch fully: {stderr}", file=sys.stderr)

def update_jules_from_main() -> bool:
    """Updates the jules branch with changes from main."""
    try:
        subprocess.run(["git", "config", "user.name", "Jules Bot"], check=False)
        subprocess.run(["git", "config", "user.email", "jules-bot@google.com"], check=False)
        subprocess.run(["git", "checkout", "-B", JULES_BRANCH, f"origin/{JULES_BRANCH}"], check=True, capture_output=True)
        print(f"Merging origin/main into '{JULES_BRANCH}'...")
        subprocess.run(["git", "merge", "origin/main", "--no-edit"], check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", JULES_BRANCH], check=True, capture_output=True)
        print(f"Successfully updated '{JULES_BRANCH}' from main.")
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        print(f"Failed to update jules from main: {stderr}. Treating as drift...")
        rotate_drifted_jules_branch()
        return False

def ensure_jules_branch_exists() -> None:
    """Ensure the 'jules' branch exists and is not drifted."""
    try:
        subprocess.run(["git", "fetch", "origin"], check=True, capture_output=True)
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", JULES_BRANCH],
            capture_output=True, text=True, check=True
        )
        
        if result.stdout.strip():
            if is_jules_drifted():
                rotate_drifted_jules_branch()
            else:
                print(f"Branch '{JULES_BRANCH}' exists and is healthy. Updating from main...")
                if update_jules_from_main():
                    return
        
        print(f"Branch '{JULES_BRANCH}' needs recreation. Creating from main...")
        result = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            capture_output=True, text=True, check=True
        )
        main_sha = result.stdout.strip()
        subprocess.run(
            ["git", "push", "--force", "origin", f"{main_sha}:refs/heads/{JULES_BRANCH}"],
            check=True, capture_output=True
        )
        print(f"Created fresh '{JULES_BRANCH}' branch from main at {main_sha[:12]}")
        
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        raise BranchError(f"Failed to ensure jules branch exists: {stderr}") from e

def merge_pr_into_jules(pr_number: int) -> None:
    """Merge a PR into the jules branch using gh CLI."""
    try:
        subprocess.run(
            ["gh", "pr", "merge", str(pr_number), "--merge", "--delete-branch"],
            check=True, capture_output=True
        )
        print(f"Successfully merged PR #{pr_number} into '{JULES_BRANCH}'.")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        raise MergeError(f"Failed to merge PR #{pr_number}: {stderr}") from e

def is_pr_green(pr_details: dict) -> bool:
    """Check if all CI checks on a PR are successful."""
    status_check_rollup = pr_details.get("statusCheckRollup", [])
    if not status_check_rollup:
        return True
    for check in status_check_rollup:
        status = (check.get("conclusion") or check.get("status") or "").upper()
        if status in ["SUCCESS", "NEUTRAL", "SKIPPED", "COMPLETED"]:
            continue
        return False
    return True

def run_cycle_step(
    client: JulesClient,
    repo_info: dict,
    cycle_entries: list[dict[str, Any]],
    open_prs: list[dict[str, Any]],
    dry_run: bool,
    base_context: dict
) -> None:
    """Run a single step of the cycle scheduler."""
    cycle_ids = [entry["id"] for entry in cycle_entries]
    print(f"Running in CYCLE mode with order: {cycle_ids}")
    ensure_jules_branch_exists()
    last_session_id, last_pid = get_last_cycle_session(client, cycle_entries, repo_info)
    next_entry = cycle_entries[0]
    base_pr_number = ""

    if last_session_id and last_pid:
        print(f"Last recorded session: {last_session_id} ({last_pid})")
        pr = get_pr_by_session_id(open_prs, last_session_id)

        if pr:
            pr_number = pr["number"]
            base_pr_number = str(pr_number)
            print(f"Found PR for last session: #{pr_number} - {pr['title']}")
            pr_details = get_pr_details_via_gh(pr_number)
            if not is_pr_green(pr_details):
                print(f"PR #{pr_number} is not green. Waiting.")
                return
            print(f"PR #{pr_number} is green! Merging into '{JULES_BRANCH}'...")
            if not dry_run:
                merge_pr_into_jules(pr_number)
            
            if last_pid in cycle_ids:
                idx = cycle_ids.index(last_pid)
                next_idx = (idx + 1) % len(cycle_entries)
                next_entry = cycle_entries[next_idx]
                
                # If we completed a full cycle, increment sprint
                if next_idx == 0:
                    old_sprint = sprint_manager.get_current_sprint()
                    new_sprint = sprint_manager.increment_sprint()
                    print(f"Cycle completed! Sprint incremented: {old_sprint} → {new_sprint}")
            
            print(f"Next persona: {next_entry['id']}. Starting from '{JULES_BRANCH}'.")
        else:
            merged_pr = get_pr_by_session_id_any_state(repo_info["owner"], repo_info["repo"], last_session_id)
            if merged_pr and merged_pr.get("mergedAt"):
                base_pr_number = str(merged_pr.get("number", ""))
                print(f"PR for session {last_session_id} already merged. Continuing.")
                if last_pid in cycle_ids:
                    idx = cycle_ids.index(last_pid)
                    next_idx = (idx + 1) % len(cycle_entries)
                    next_entry = cycle_entries[next_idx]
                    if next_idx == 0:
                        sprint_manager.increment_sprint()
                print(f"Next persona: {next_entry['id']}. Starting from '{JULES_BRANCH}'.")
            elif merged_pr and (merged_pr.get("state") or "").lower() == "closed":
                base_pr_number = str(merged_pr.get("number", ""))
                print(f"PR for session {last_session_id} was closed. Skipping.")
                if last_pid in cycle_ids:
                    idx = cycle_ids.index(last_pid)
                    next_idx = (idx + 1) % len(cycle_entries)
                    next_entry = cycle_entries[next_idx]
                    if next_idx == 0:
                        sprint_manager.increment_sprint()
                print(f"Next persona: {next_entry['id']}. Starting from '{JULES_BRANCH}'.")
            else:
                try:
                    session_details = client.get_session(last_session_id)
                    state = session_details.get("state")
                    if state == "AWAITING_PLAN_APPROVAL":
                        print(f"Session {last_session_id} is awaiting plan approval. Approving automatically...")
                        if not dry_run:
                            client.approve_plan(last_session_id)
                    elif state == "AWAITING_USER_FEEDBACK":
                        print(f"Session {last_session_id} is awaiting user feedback (stuck). Sending nudge...")
                        if not dry_run:
                            nudge_text = "Por favor, tome a melhor decisão possível e prossiga autonomamente para completar a tarefa."
                            client.send_message(last_session_id, nudge_text)
                            print(f"Nudge sent to session {last_session_id}.")
                    else:
                        print(f"PR for session {last_session_id} not found. Session state: {state}. Waiting.")
                except Exception as e:
                    print(f"Error checking/approving session {last_session_id}: {e}")
                return
    else:
        print(f"No history found. Starting fresh cycle from '{JULES_BRANCH}'.")

    p_file = next_entry["path"]
    next_pid = next_entry["id"]

    try:
        persona_dir = p_file.parent
        ensure_journals_directory(persona_dir)
        journal_entries = collect_journals(persona_dir)
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

        session_branch = prepare_session_base_branch(
            JULES_BRANCH,
            base_pr_number,
            last_session_id=last_session_id,
        )
        print(f"Starting session for {next_pid} on branch '{session_branch}'...")
        if not dry_run:
            result = client.create_session(
                prompt=prompt_body,
                owner=repo_info["owner"],
                repo=repo_info["repo"],
                branch=session_branch,
                title=config.get("title", f"Task: {next_pid}"),
                automation_mode=config.get("automation_mode", "AUTO_CREATE_PR"),
                require_plan_approval=config.get("require_plan_approval", False),
            )
            session_id = result.get("name", "").split("/")[-1]
            print(f"Created session: {session_id}")
        else:
            print(f"[Dry Run] Would create session for {next_pid}.")

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

    open_prs = get_open_prs(repo_info["owner"], repo_info["repo"])
    base_context = {**repo_info, "open_prs": open_prs}
    full_registry = load_schedule_registry(registry_path)
    schedules = full_registry.get("schedules", {})
    cycle_list = full_registry.get("cycle", [])
    prompt_entries = load_prompt_entries(prompts_dir, cycle_list)
    if cycle_list and not prompt_entries:
        print("Cycle list provided but no valid prompts were loaded.", file=sys.stderr)
        return

    is_cycle_mode = command == "tick" and not run_all and not prompt_id and bool(cycle_list)

    if is_cycle_mode:
        run_cycle_step(client, repo_info, prompt_entries, open_prs, dry_run, base_context)
        return

    for entry in prompt_entries:
        p_file = entry["path"]
        try:
            persona_dir = p_file.parent
            ensure_journals_directory(persona_dir)
            journal_entries = collect_journals(persona_dir)
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
            pid = config.get("id")
            if not pid or (prompt_id and prompt_id not in {pid, entry.get("rel_path")}):
                continue

            should_run = False
            schedule_str = schedules.get(pid) or config.get("schedule")
            if run_all or (prompt_id == pid):
                should_run = True
            elif command == "tick" and schedule_str and check_schedule(schedule_str):
                should_run = True

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
                    print(f"Created session for {pid}: {session_id}")
                else:
                    print(f"[Dry Run] Would create session for {pid}")
        except Exception as e:
            print(f"Error processing prompt {p_file.name}: {e}", file=sys.stderr)
