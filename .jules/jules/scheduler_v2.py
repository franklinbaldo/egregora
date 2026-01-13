"""Jules Scheduler V2 - Refactored with clean architecture."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jules.client import JulesClient
from jules.github import get_open_prs, get_repo_info
from jules.scheduler import (
    JULES_BRANCH,
    check_schedule,
    load_schedule_registry,
    sprint_manager,
)
from jules.scheduler_loader import PersonaLoader
from jules.scheduler_managers import (
    BranchManager,
    CycleStateManager,
    PRManager,
    SessionOrchestrator,
)
from jules.scheduler_models import SessionRequest
from jules.scheduler_state import PersistentCycleState, commit_cycle_state

CYCLE_STATE_PATH = Path(".jules/cycle_state.json")


def get_sync_patch(persona_id: str) -> dict | None:
    """Find persona's open PR and generate sync patch URL.
    
    Jules cannot do git rebase, so we provide a GitHub URL where Jules can
    download a patch showing the difference between their PR and current jules.
    
    Args:
        persona_id: The persona identifier to find PR for
        
    Returns:
        Dict with patch_url and pr_number if persona has an open PR, None otherwise
    """
    import subprocess
    import json
    
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
    
    patch_url = sync_info["patch_url"]
    pr_number = sync_info["pr_number"]
    head_branch = sync_info["head_branch"]
    
    sync_instruction = f"""
## 🔄 SYNC REQUIRED - FIRST ACTION

Before starting your main task, you MUST sync with the latest `jules` branch changes.

**Your existing PR:** #{pr_number} (branch: `{head_branch}`)

**Why?** The `jules` branch has been updated since your last session. To avoid conflicts:

1. Download the sync patch:
   ```bash
   curl -L "{patch_url}" -o sync.patch
   ```

2. Apply the patch:
   ```bash
   git apply sync.patch
   ```
   
3. If apply fails with conflicts, try:
   ```bash
   git apply --3way sync.patch
   ```

4. Then proceed with your normal task.

**Important:** If the patch cannot be applied cleanly, document the conflicts and proceed with your task anyway. The Weaver will help resolve conflicts later.

---

"""
    return sync_instruction + persona_prompt

def execute_parallel_cycle_tick(dry_run: bool = False) -> None:
    """Execute concurrent persona tracks (Parallel Scheduler)."""
    print("=" * 70)
    print("PARALLEL CYCLE MODE")
    print("=" * 70)

    # === SETUP ===
    client = JulesClient()
    repo_info = get_repo_info()
    open_prs = get_open_prs(repo_info["owner"], repo_info["repo"])

    # Load configuration
    registry = load_schedule_registry(Path(".jules/schedules.toml"))

    # 1. Determine Tracks
    tracks = registry.get("tracks", {})
    cycle_list = registry.get("cycle", [])

    # Backward compatibility: If no tracks, treat "cycle" as a "default" track
    if not tracks and cycle_list:
        tracks = {"default": cycle_list}
    elif not tracks:
        print("No tracks or cycle defined in schedules.toml", file=sys.stderr)
        return

    # Load all personas once
    base_context = {**repo_info, "open_prs": open_prs}
    loader = PersonaLoader(Path(".jules/personas"), base_context)

    # Flatten all personas needed across all tracks
    all_persona_ids = set()
    for p_list in tracks.values():
        all_persona_ids.update(p_list)

    # Load all unique personas found in tracks
    # This prevents loading unnecessary files if directory has many drafts
    all_personas_map = {p.id: p for p in loader.load_personas(list(all_persona_ids))}

    # Initialize Managers
    branch_mgr = BranchManager(JULES_BRANCH)
    # pr_mgr = PRManager(JULES_BRANCH) # Used in reconciliation, not heavily in direct cycle
    orchestrator = SessionOrchestrator(client, dry_run)

    # Ensure base branch health
    branch_mgr.ensure_jules_branch_exists()

    # Load Persistent State
    persistent_state = PersistentCycleState.load(CYCLE_STATE_PATH)
    state_changed = False

    # === PROCESS EACH TRACK ===
    for track_name, track_personas in tracks.items():
        print(f"\n🛤️  Track: {track_name.upper()}")

        # Filter personas for this track
        track_persona_objs = []
        for pid in track_personas:
            # Handle path-based IDs in config (e.g. "personas/curator/prompt.md")
            clean_id = pid.split("/")[-2] if "/" in pid else pid
            if clean_id in all_personas_map:
                track_persona_objs.append(all_personas_map[clean_id])
            else:
                print(f"   ⚠️ Persona not found: {pid}")

        if not track_persona_objs:
            print("   (No valid personas in track)")
            continue

        cycle_mgr = CycleStateManager(track_persona_objs)
        track_state = persistent_state.get_track(track_name)

        # Determine Next Persona
        last_id = track_state.last_persona_id
        if last_id and last_id in cycle_mgr.cycle_ids:
            next_idx, should_increment = cycle_mgr.advance_cycle(last_id)
            print(f"   📍 Last: {last_id}")
        else:
            next_idx = 0
            should_increment = False
            print("   📍 Starting fresh")

        # Check Previous Session Status
        last_session_id = track_state.last_session_id
        ready_to_advance = True
        
        if last_session_id:
            try:
                session = client.get_session(last_session_id)
                status = session.get("state")

                if status == "COMPLETED":
                    print(f"   ✅ Previous session {last_session_id} COMPLETED.")
                    if should_increment:
                        # Only increment sprint if the primary/default track finishes?
                        # Or maybe we don't tie sprints to cycles anymore in parallel mode.
                        # For now, let's log it.
                        print(f"   🔄 Track {track_name} cycle complete.")
                elif status in ["IN_PROGRESS", "PENDING", "AWAITING_PLAN_APPROVAL", "AWAITING_USER_FEEDBACK"]:
                     # Check stuck
                    if orchestrator.handle_stuck_session(last_session_id, track_state.updated_at):
                         print(f"   ⚠️ Session {last_session_id} timed out/stuck. Skipping.")
                    else:
                        print(f"   ⏳ Previous session {last_session_id} is {status}. Waiting.")
                        ready_to_advance = False
                else:
                    print(f"   ⚠️ Session {last_session_id} in state {status}. Advancing.")

            except Exception as e:
                print(f"   ⚠️ Error checking session {last_session_id}: {e}")
                # Fail open to avoid deadlock

        if not ready_to_advance:
            continue
            
        # Start Next Session
        next_p = track_persona_objs[next_idx]
        print(f"   🚀 Starting: {next_p.emoji} {next_p.id}")

        # Direct Branching (Always direct per user request)
        session_branch = branch_mgr.create_session_branch(
            base_branch=JULES_BRANCH,
            persona_id=next_p.id
        )

        # Calculate sync patch if persona has existing PR
        sync_info = get_sync_patch(next_p.id)
        if sync_info:
            print(f"   🔄 Found existing PR #{sync_info['pr_number']} - will include sync instructions")
        
        # Build prompt with sync instructions if needed
        session_prompt = build_session_prompt(next_p.prompt_body, sync_info, next_p.id)

        request = SessionRequest(
            persona_id=next_p.id,
            title=f"{next_p.emoji} {next_p.id}: {track_name} task",
            prompt=session_prompt,
            branch=session_branch,
            owner=repo_info["owner"],
            repo=repo_info["repo"],
            automation_mode="AUTO_CREATE_PR",
            require_plan_approval=False,
        )

        session_id = orchestrator.create_session(request)
        print(f"   ✅ Created session: {session_id}")

        if not dry_run and session_id != "[DRY RUN]":
            persistent_state.record_session(
                persona_id=next_p.id,
                persona_index=next_idx,
                session_id=session_id,
                track_name=track_name
            )
            state_changed = True

    if state_changed and not dry_run:
        persistent_state.save(CYCLE_STATE_PATH)
        commit_cycle_state(CYCLE_STATE_PATH, "chore(jules): update parallel cycle state")


def execute_cycle_tick(dry_run: bool = False) -> None:
    """Wrapper to maintain backward compatibility for CLI."""
    execute_parallel_cycle_tick(dry_run)


def execute_scheduled_tick(
    run_all: bool = False, prompt_id: str | None = None, dry_run: bool = False
) -> None:
    """Execute scheduled personas based on cron schedules.

    Args:
        run_all: If True, ignores schedules and runs all personas
        prompt_id: If provided, only runs the specified persona
        dry_run: If True, prints actions without executing them
    """
    print("=" * 70)
    print("SCHEDULED MODE: Cron-based persona execution")
    print("=" * 70)

    # === SETUP ===
    client = JulesClient()
    repo_info = get_repo_info()
    open_prs = get_open_prs(repo_info["owner"], repo_info["repo"])

    # Load all personas
    base_context = {**repo_info, "open_prs": open_prs}
    loader = PersonaLoader(Path(".jules/personas"), base_context)
    personas = loader.load_personas([])

    # Load schedules
    registry = load_schedule_registry(Path(".jules/schedules.toml"))
    schedules = registry.get("schedules", {})

    orchestrator = SessionOrchestrator(client, dry_run)
    branch_mgr = BranchManager(JULES_BRANCH)

    print(f"Loaded {len(personas)} personas")
    print(f"Current time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print()

    # === FILTER AND RUN PERSONAS ===
    sessions_created = 0

    for persona in personas:
        should_run = False
        reason = ""

        if prompt_id:
            if persona.id == prompt_id or persona.path == str(prompt_id):
                should_run = True
                reason = f"--prompt-id={prompt_id}"
        elif run_all:
            should_run = True
            reason = "--all flag"
        else:
            schedule_str = schedules.get(persona.id, "")
            if schedule_str and check_schedule(schedule_str):
                should_run = True
                reason = f"schedule: {schedule_str}"

        if not should_run:
            continue

        print(f"▶️  {persona.emoji} {persona.id} ({reason})")

        # Scheduled mode uses direct branching now per user request
        session_branch = branch_mgr.create_session_branch(
            base_branch=JULES_BRANCH,
            persona_id=persona.id,
        )

        # Calculate sync patch if persona has existing PR
        sync_info = get_sync_patch(persona.id)
        if sync_info:
            print(f"   🔄 Found existing PR #{sync_info['pr_number']} - will include sync instructions")
        
        # Build prompt with sync instructions if needed
        session_prompt = build_session_prompt(persona.prompt_body, sync_info, persona.id)

        request = SessionRequest(
            persona_id=persona.id,
            title=f"{persona.emoji} {persona.id}: scheduled task",
            prompt=session_prompt,
            branch=session_branch,
            owner=repo_info["owner"],
            repo=repo_info["repo"],
            automation_mode="AUTO_CREATE_PR",
            require_plan_approval=False,
        )

        session_id = orchestrator.create_session(request)
        print(f"   ✅ Session: {session_id}")
        sessions_created += 1

    print(f"✅ Created {sessions_created} session(s)")
    print("=" * 70)


def run_scheduler(
    command: str, run_all: bool = False, dry_run: bool = False, prompt_id: str | None = None
) -> None:
    """Main scheduler entry point."""
    registry = load_schedule_registry(Path(".jules/schedules.toml"))

    # Check if we should run in cycle mode
    # Run cycle if "tick" command, no specific prompt/run_all flags, and either cycle or tracks exist
    has_cycle_config = bool(registry.get("cycle") or registry.get("tracks"))
    is_cycle_mode = command == "tick" and not run_all and not prompt_id and has_cycle_config

    client = JulesClient()
    repo_info = get_repo_info()
    pr_mgr = PRManager(JULES_BRANCH)

    if is_cycle_mode:
        execute_parallel_cycle_tick(dry_run)
        print("\nChecking for additional scheduled tasks...")
        execute_scheduled_tick(run_all=False, prompt_id=None, dry_run=dry_run)
    else:
        if prompt_id or run_all:
            execute_scheduled_tick(run_all, prompt_id, dry_run)
        else:
            execute_parallel_cycle_tick(dry_run)

    # === GLOBAL RECONCILIATION ===
    # Automate the lifecycle for ALL Jules PRs (parallel and cycle)
    pr_mgr.reconcile_all_jules_prs(client, repo_info, dry_run)

    # === WEAVER INTEGRATION ===
    # When enabled, trigger Weaver persona to handle merging
    from jules.scheduler_managers import WEAVER_ENABLED
    if WEAVER_ENABLED:
        run_weaver_integration(client, repo_info, dry_run)


def run_weaver_integration(
    client: JulesClient, repo_info: dict[str, Any], dry_run: bool = False
) -> None:
    """Trigger Weaver persona to integrate pending PRs.
    
    The Weaver will:
    1. Fetch all green PRs awaiting integration
    2. Attempt local merge and test
    3. Create wrapper PR or communicate via jules-mail if conflicts
    
    Args:
        client: Jules API client
        repo_info: Repository information
        dry_run: If True, only log actions
    """
    from jules.scheduler_managers import WEAVER_SESSION_TIMEOUT_MINUTES
    import json
    import subprocess
    
    print("\n🕸️ Weaver: Checking for integration work...")
    
    # 1. Check for green PRs targeting jules branch
    try:
        result = subprocess.run(
            ["gh", "pr", "list", "--json", "number,title,headRefName,baseRefName,mergeable,mergeStateStatus,isDraft"],
            capture_output=True, text=True, check=True
        )
        prs = json.loads(result.stdout)
        
        # Filter for green PRs targeting jules
        ready_prs = [
            pr for pr in prs
            if pr.get("baseRefName") == JULES_BRANCH
            and pr.get("mergeable") == "MERGEABLE"
            and pr.get("mergeStateStatus") in ["CLEAN", "BEHIND"]
            and not pr.get("isDraft", True)
        ]
        
        if not ready_prs:
            print("   No PRs ready for Weaver integration.")
            return
        
        print(f"   Found {len(ready_prs)} PR(s) ready for integration.")
        
    except Exception as e:
        print(f"   ⚠️ Failed to list PRs: {e}")
        return
    
    # 2. Check for existing Weaver session
    try:
        sessions = client.list_sessions().get("sessions", [])
        weaver_sessions = [
            s for s in sessions
            if "weaver" in s.get("title", "").lower()
        ]
        
        if weaver_sessions:
            # Sort by creation time, get most recent
            latest = sorted(weaver_sessions, key=lambda x: x.get("createTime", ""))[-1]
            state = latest.get("state", "UNKNOWN")
            session_id = latest.get("name", "").split("/")[-1]
            
            if state == "IN_PROGRESS":
                print(f"   ⏳ Weaver session {session_id} is already running. Waiting...")
                return
            
            if state == "COMPLETED":
                # Check if recently completed (avoid spam)
                from datetime import datetime, timedelta
                create_time = latest.get("createTime", "")
                if create_time:
                    try:
                        created = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
                        if datetime.now(timezone.utc) - created < timedelta(minutes=WEAVER_SESSION_TIMEOUT_MINUTES):
                            print(f"   ⏳ Weaver session recently completed. Waiting for next cycle...")
                            return
                    except Exception:
                        pass
        
    except Exception as e:
        print(f"   ⚠️ Failed to check Weaver sessions: {e}")
    
    # 3. Create new Weaver session
    if dry_run:
        print("   [DRY RUN] Would create Weaver integration session")
        return
    
    try:
        # Load Weaver persona
        base_context = {**repo_info, "jules_branch": JULES_BRANCH}
        loader = PersonaLoader(Path(".jules/personas"), base_context)
        
        # Find the weaver prompt file
        weaver_prompt = Path(".jules/personas/weaver/prompt.md.j2")
        if not weaver_prompt.exists():
            weaver_prompt = Path(".jules/personas/weaver/prompt.md")
        
        if not weaver_prompt.exists():
            print("   ⚠️ Weaver persona not found!")
            return
            
        weaver = loader.load_persona(weaver_prompt)
        
        # Create session request
        orchestrator = SessionOrchestrator(client, dry_run=False)
        branch_mgr = BranchManager(JULES_BRANCH)
        
        session_branch = branch_mgr.create_session_branch(
            base_branch=JULES_BRANCH,
            persona_id="weaver"
        )
        
        # Build patch URLs list for Weaver
        owner = repo_info["owner"]
        repo = repo_info["repo"]
        
        patch_instructions = []
        for pr in ready_prs:
            pr_num = pr['number']
            pr_title = pr['title']
            patch_url = f"https://github.com/{owner}/{repo}/pull/{pr_num}.patch"
            patch_instructions.append(f"""
### PR #{pr_num}: {pr_title}
```bash
curl -L "{patch_url}" -o pr_{pr_num}.patch
git apply pr_{pr_num}.patch || git apply --3way pr_{pr_num}.patch
```""")
        
        patches_section = "\n".join(patch_instructions)
        
        # Build commit message PR list
        pr_numbers_str = ", ".join([f"#{pr['number']}" for pr in ready_prs])
        
        weaver_prompt_with_patches = f"""{weaver.prompt_body}

---

## 🎯 YOUR TASK: Apply These Patches

The following PRs are ready for integration into `jules`. Download and apply each patch in order:

{patches_section}

After applying all patches successfully, commit with:
```bash
git add -A
git commit -m "🕸️ Weaver: Integrate PRs {pr_numbers_str}"
```
"""
        
        request = SessionRequest(
            persona_id="weaver",
            title="🕸️ weaver: integration session",
            prompt=weaver_prompt_with_patches,
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
