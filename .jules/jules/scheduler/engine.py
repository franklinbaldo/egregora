"""Jules Scheduler V2 - Simplified API-driven sequential execution."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jinja2

# Initialize Jinja2 environment for prompt templates
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    undefined=jinja2.StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)

from jules.core.client import JulesClient
from jules.core.github import get_open_prs, get_repo_info
from jules.scheduler.legacy import JULES_BRANCH
from jules.scheduler.loader import PersonaLoader
from jules.scheduler.managers import (
    BranchManager,
    PRManager,
    SessionOrchestrator,
)
from jules.scheduler.models import SessionRequest


def get_sync_patch(persona_id: str) -> dict | None:
    """Find persona's open PR and generate sync patch URL.
    
    Jules cannot do git rebase, so we provide a GitHub URL where Jules can
    download a patch showing the difference between their PR and current jules.
    
    Args:
        persona_id: The persona identifier to find PR for
        
    Returns:
        Dict with patch_url and pr_number if persona has an open PR, None otherwise

    """
    import json
    import subprocess

    try:
        # 1. Find persona's open PR
        result = subprocess.run(
            ["gh", "pr", "list", "--author", "app/google-labs-jules",
             "--json", "number,headRefName,baseRefName,body"],
            capture_output=True, text=True, check=True
        )
        prs = json.loads(result.stdout)

        # Find PR for this persona (check head branch name or body)
        persona_pr = None
        for pr in prs:
            head = pr.get("headRefName", "").lower()
            body = pr.get("body", "").lower()
            if persona_id.lower() in head or persona_id.lower() in body:
                persona_pr = pr
                break

        if not persona_pr:
            return None  # No existing PR, no sync needed

        # 2. Get repo info for URL construction
        repo_result = subprocess.run(
            ["gh", "repo", "view", "--json", "owner,name"],
            capture_output=True, text=True, check=True
        )
        repo_info = json.loads(repo_result.stdout)
        owner = repo_info["owner"]["login"]
        repo = repo_info["name"]

        head_branch = persona_pr["headRefName"]
        pr_number = persona_pr["number"]

        # 3. Construct patch URL
        # This URL gives the diff of what's in jules but not in the PR branch
        patch_url = f"https://github.com/{owner}/{repo}/compare/{head_branch}...{JULES_BRANCH}.patch"

        return {
            "patch_url": patch_url,
            "pr_number": pr_number,
            "head_branch": head_branch,
        }

    except Exception:
        return None


def build_session_prompt(persona_prompt: str, sync_info: dict | None, persona_id: str) -> str:
    """Build prompt with optional sync patch URL prefix.
    
    Args:
        persona_prompt: The persona's original prompt content
        sync_info: Dict with patch_url and pr_number, or None
        persona_id: The persona identifier
        
    Returns:
        Complete prompt with sync instructions if needed

    """
    if not sync_info:
        return persona_prompt

    # Render sync instruction from template
    template = JINJA_ENV.get_template("prompts/sync_instruction.md.j2")
    sync_instruction = template.render(
        patch_url=sync_info["patch_url"],
        pr_number=sync_info["pr_number"],
        head_branch=sync_info["head_branch"],
    )
    return sync_instruction + persona_prompt

def execute_sequential_tick(dry_run: bool = False) -> None:
    """Execute next persona in sequential order based on API session history.
    
    This simplified scheduler:
    1. Loads personas alphabetically from .jules/personas/
    2. Queries the Jules API for recent sessions
    3. Determines the next persona based on round-robin from last completed
    4. Skips if there's an active session in progress
    """
    print("=" * 70)
    print("SEQUENTIAL MODE: API-driven persona execution")
    print("=" * 70)

    # === SETUP ===
    client = JulesClient()
    repo_info = get_repo_info()
    open_prs = get_open_prs(repo_info["owner"], repo_info["repo"])

    # 1. Load all personas (sorted alphabetically for deterministic order)
    base_context = {**repo_info, "open_prs": open_prs}
    loader = PersonaLoader(Path(".jules/personas"), base_context)
    personas = sorted(loader.load_personas([]), key=lambda p: p.id)

    if not personas:
        print("❌ No personas found in .jules/personas/")
        return

    persona_ids = [p.id for p in personas]
    print(f"📋 Loaded {len(personas)} personas: {', '.join(persona_ids)}")

    # 2. Get recent sessions from API
    try:
        sessions_response = client.list_sessions()
        sessions = sessions_response.get("sessions", [])
        print(f"📊 Found {len(sessions)} sessions in API")
    except Exception as e:
        print(f"⚠️ Failed to fetch sessions from API: {e}")
        sessions = []

    # 3. Check for active sessions (don't start new one if busy)
    active_states = ["IN_PROGRESS", "PENDING", "AWAITING_PLAN_APPROVAL", "AWAITING_USER_FEEDBACK"]
    active_sessions = [s for s in sessions if s.get("state") in active_states]

    if active_sessions:
        latest = active_sessions[0]
        session_id = latest.get("name", "").split("/")[-1]
        state = latest.get("state", "UNKNOWN")
        print(f"⏳ Active session exists: {session_id} ({state}). Waiting.")
        return

    # 4. Find last completed session's persona
    completed_sessions = [s for s in sessions if s.get("state") == "COMPLETED"]
    last_persona_id = None

    if completed_sessions:
        # Sort by createTime descending (most recent first)
        completed_sessions.sort(key=lambda s: s.get("createTime", ""), reverse=True)

        # Extract persona ID from session title (format: "emoji persona_id: task")
        last_title = completed_sessions[0].get("title", "")
        for pid in persona_ids:
            if pid.lower() in last_title.lower():
                last_persona_id = pid
                break

        if last_persona_id:
            print(f"📍 Last completed persona: {last_persona_id}")
        else:
            print(f"📍 Could not determine last persona from title: {last_title}")

    # 5. Determine next persona (round-robin)
    if last_persona_id and last_persona_id in persona_ids:
        current_idx = persona_ids.index(last_persona_id)
        next_idx = (current_idx + 1) % len(personas)
    else:
        next_idx = 0
        print("📍 Starting from first persona")

    next_persona = personas[next_idx]
    print(f"\n🚀 Next persona: {next_persona.emoji} {next_persona.id}")

    if dry_run:
        print("[DRY RUN] Would create session for above persona")
        return

    # 6. Create session for next persona
    branch_mgr = BranchManager(JULES_BRANCH)
    branch_mgr.ensure_jules_branch_exists()

    session_branch = branch_mgr.create_session_branch(
        base_branch=JULES_BRANCH,
        persona_id=next_persona.id
    )

    # Check for sync patch if persona has existing PR
    sync_info = get_sync_patch(next_persona.id)
    if sync_info:
        print(f"🔄 Found existing PR #{sync_info['pr_number']} - will include sync instructions")

    session_prompt = build_session_prompt(next_persona.prompt_body, sync_info, next_persona.id)

    request = SessionRequest(
        persona_id=next_persona.id,
        title=f"{next_persona.emoji} {next_persona.id}: sequential task",
        prompt=session_prompt,
        branch=session_branch,
        owner=repo_info["owner"],
        repo=repo_info["repo"],
        automation_mode="AUTO_CREATE_PR",
        require_plan_approval=False,
    )

    orchestrator = SessionOrchestrator(client, dry_run)
    session_id = orchestrator.create_session(request)
    print(f"✅ Created session: {session_id}")
    print("=" * 70)


def execute_parallel_cycle_tick(dry_run: bool = False) -> None:
    """Legacy wrapper - redirects to sequential tick."""
    execute_sequential_tick(dry_run)


def execute_cycle_tick(dry_run: bool = False) -> None:
    """Wrapper to maintain backward compatibility for CLI."""
    execute_parallel_cycle_tick(dry_run)


def execute_scheduled_tick(
    run_all: bool = False, prompt_id: str | None = None, dry_run: bool = False
) -> None:
    """Execute a specific persona by ID (legacy support for --prompt-id).

    Args:
        run_all: Deprecated, ignored
        prompt_id: If provided, runs only the specified persona
        dry_run: If True, prints actions without executing them

    """
    if not prompt_id:
        print("⚠️ execute_scheduled_tick requires --prompt-id. Use execute_sequential_tick instead.")
        return

    print("=" * 70)
    print(f"SINGLE PERSONA MODE: {prompt_id}")
    print("=" * 70)

    # === SETUP ===
    client = JulesClient()
    repo_info = get_repo_info()
    open_prs = get_open_prs(repo_info["owner"], repo_info["repo"])

    # Load all personas
    base_context = {**repo_info, "open_prs": open_prs}
    loader = PersonaLoader(Path(".jules/personas"), base_context)
    personas = loader.load_personas([])

    # Find target persona
    target = None
    for persona in personas:
        if persona.id == prompt_id or persona.path == str(prompt_id):
            target = persona
            break

    if not target:
        print(f"❌ Persona not found: {prompt_id}")
        return

    print(f"▶️ Running: {target.emoji} {target.id}")

    if dry_run:
        print("[DRY RUN] Would create session")
        return

    branch_mgr = BranchManager(JULES_BRANCH)
    branch_mgr.ensure_jules_branch_exists()

    session_branch = branch_mgr.create_session_branch(
        base_branch=JULES_BRANCH,
        persona_id=target.id,
    )

    # Check for sync patch if persona has existing PR
    sync_info = get_sync_patch(target.id)
    if sync_info:
        print(f"🔄 Found existing PR #{sync_info['pr_number']} - will include sync instructions")

    session_prompt = build_session_prompt(target.prompt_body, sync_info, target.id)

    request = SessionRequest(
        persona_id=target.id,
        title=f"{target.emoji} {target.id}: manual task",
        prompt=session_prompt,
        branch=session_branch,
        owner=repo_info["owner"],
        repo=repo_info["repo"],
        automation_mode="AUTO_CREATE_PR",
        require_plan_approval=False,
    )

    orchestrator = SessionOrchestrator(client, dry_run)
    session_id = orchestrator.create_session(request)
    print(f"✅ Created session: {session_id}")
    print("=" * 70)


def run_scheduler(
    command: str, run_all: bool = False, dry_run: bool = False, prompt_id: str | None = None
) -> None:
    """Main scheduler entry point.
    
    Simplified to always use sequential API-driven execution.
    """
    client = JulesClient()
    repo_info = get_repo_info()
    pr_mgr = PRManager(JULES_BRANCH)

    # Always use sequential mode now
    if prompt_id:
        # Run specific persona (legacy support)
        execute_scheduled_tick(run_all=False, prompt_id=prompt_id, dry_run=dry_run)
    else:
        # Default: sequential execution
        execute_sequential_tick(dry_run)

    # === GLOBAL RECONCILIATION ===
    # Automate the lifecycle for ALL Jules PRs
    pr_mgr.reconcile_all_jules_prs(client, repo_info, dry_run)

    # === EMAIL POLLING ===
    from jules.features.polling import EmailPoller
    poller = EmailPoller(client)
    poller.poll_and_deliver()

    # === WEAVER INTEGRATION ===
    # Weaver is currently disabled
    # from jules.scheduler.managers import WEAVER_ENABLED
    # if WEAVER_ENABLED and conflict_prs:
    #     run_weaver_for_conflicts(client, repo_info, conflict_prs, dry_run)



def run_weaver_for_conflicts(
    client: JulesClient, repo_info: dict[str, Any], conflict_prs: list[dict], dry_run: bool = False
) -> None:
    """Trigger Weaver to resolve merge conflicts.
    
    Called by Overseer when PRs fail to auto-merge.
    
    Args:
        client: Jules API client
        repo_info: Repository information
        conflict_prs: List of PRs that failed to merge
        dry_run: If True, only log actions

    """
    from jules.scheduler.managers import WEAVER_SESSION_TIMEOUT_MINUTES

    print(f"\n🕸️ Weaver: Resolving {len(conflict_prs)} conflict PR(s)...")

    # Check for existing Weaver session
    try:
        sessions = client.list_sessions().get("sessions", [])
        weaver_sessions = [s for s in sessions if "weaver" in s.get("title", "").lower()]

        if weaver_sessions:
            latest = sorted(weaver_sessions, key=lambda x: x.get("createTime", ""))[-1]
            state = latest.get("state", "UNKNOWN")
            session_id = latest.get("name", "").split("/")[-1]

            if state == "IN_PROGRESS":
                print(f"   ⏳ Weaver session {session_id} is already running. Waiting...")
                return

            if state == "COMPLETED":
                from datetime import timedelta
                create_time = latest.get("createTime", "")
                if create_time:
                    try:
                        created = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
                        if datetime.now(UTC) - created < timedelta(minutes=WEAVER_SESSION_TIMEOUT_MINUTES):
                            print("   ⏳ Weaver recently completed. Waiting...")
                            return
                    except Exception:
                        pass
    except Exception as e:
        print(f"   ⚠️ Failed to check Weaver sessions: {e}")

    if dry_run:
        print("   [DRY RUN] Would create Weaver conflict resolution session")
        return

    try:
        base_context = {**repo_info, "jules_branch": JULES_BRANCH}
        loader = PersonaLoader(Path(".jules/personas"), base_context)

        weaver_prompt = Path(".jules/personas/weaver/prompt.md.j2")
        if not weaver_prompt.exists():
            weaver_prompt = Path(".jules/personas/weaver/prompt.md")
        if not weaver_prompt.exists():
            print("   ⚠️ Weaver persona not found!")
            return

        weaver = loader.load_persona(weaver_prompt)
        orchestrator = SessionOrchestrator(client, dry_run=False)
        branch_mgr = BranchManager(JULES_BRANCH)

        session_branch = branch_mgr.create_session_branch(
            base_branch=JULES_BRANCH,
            persona_id="weaver"
        )

        # Build conflict resolution prompt from template
        template = JINJA_ENV.get_template("prompts/conflict_resolution.md.j2")
        pr_numbers_str = ", ".join([f"#{pr['number']}" for pr in conflict_prs])

        conflict_section = template.render(
            conflict_prs=conflict_prs,
            owner=repo_info["owner"],
            repo=repo_info["repo"],
            pr_numbers_str=pr_numbers_str,
        )

        prompt = f"{weaver.prompt_body}\n\n{conflict_section}"

        request = SessionRequest(
            persona_id="weaver",
            title="🕸️ weaver: conflict resolution",
            prompt=prompt,
            branch=session_branch,
            owner=repo_info["owner"],
            repo=repo_info["repo"],
            automation_mode="AUTO_CREATE_PR",
            require_plan_approval=False,
        )

        session_id = orchestrator.create_session(request)
        print(f"   ✅ Created Weaver session: {session_id}")

    except Exception as e:
        print(f"   ⚠️ Failed to create Weaver session: {e}")
