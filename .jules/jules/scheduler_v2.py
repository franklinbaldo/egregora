"""Jules Scheduler V2 - Refactored with clean architecture.

This is the main entry point for the Jules scheduler, providing two modes:
1. Cycle Mode: Sequential persona execution with PR merging
2. Scheduled Mode: Cron-based persona execution

The scheduler coordinates persona loading, branch management, PR tracking,
and Jules session creation through clean, testable interfaces.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jules.client import JulesClient
from jules.github import get_open_prs, get_pr_details_via_gh, get_repo_info
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
    ReconciliationManager,
    SessionOrchestrator,
)
from jules.scheduler_models import SessionRequest
from jules.scheduler_state import PersistentCycleState, commit_cycle_state

CYCLE_STATE_PATH = Path(".jules/cycle_state.json")


def handle_drift_reconciliation(
    drift_info: tuple[int, int],
    client: JulesClient,
    repo_info: dict[str, Any],
    branch_mgr: BranchManager,
    pr_mgr: PRManager,
    dry_run: bool = False,
) -> None:
    """Handle drift reconciliation using Jules.

    Creates a reconciliation session, waits for its PR to be created
    and become green, then merges it.

    Args:
        drift_info: Tuple of (pr_number, sprint_number) for drift PR
        client: Jules API client
        repo_info: Repository information
        branch_mgr: Branch manager instance
        pr_mgr: PR manager instance
        dry_run: If True, don't actually execute
    """
    pr_number, sprint_number = drift_info
    print(f"\n⚠️  Drift detected! Created backup PR #{pr_number} (sprint-{sprint_number})")
    print("🔄 Starting reconciliation workflow...")

    # Create reconciliation manager
    recon_mgr = ReconciliationManager(client, repo_info, JULES_BRANCH, dry_run)

    # Create reconciliation session
    recon_session_id = recon_mgr.reconcile_drift(pr_number, sprint_number)
    if not recon_session_id or recon_session_id == "[DRY RUN]":
        print("⚠️  Reconciliation session not created. Manual intervention may be needed.")
        print(f"   See PR #{pr_number} for drifted changes.")
        return

    print(f"⏳ Waiting for reconciliation session {recon_session_id} to complete...")
    print("   (This is a blocking operation - scheduler will wait for PR merge)")
    print()

    # Note: In a real implementation, we'd poll the session and PR status here
    # For now, we just inform the user that manual action is needed on next tick
    print("📋 Reconciliation session created. On the next scheduler tick:")
    print("   1. Reconciliation PR will be checked")
    print("   2. If green, it will be merged")
    print("   3. Cycle will continue to next persona")
    print()
    print(f"💡 Tip: The reconciliation session will handle merging the drift from PR #{pr_number}")


def execute_cycle_tick(dry_run: bool = False) -> None:
    """Execute the sequential persona cycle.

    In cycle mode, the scheduler:
    1. Checks status of the last persona's session or PR.
    2. Advances the cycle if work is integrated.
    3. Starts the next persona.

    Args:
        dry_run: If True, prints actions without executing them
    """
    print("=" * 70)
    print("CYCLE MODE: Sequential persona execution")
    print("=" * 70)

    # === SETUP ===
    client = JulesClient()
    repo_info = get_repo_info()
    open_prs = get_open_prs(repo_info["owner"], repo_info["repo"])

    # Load personas in cycle order
    registry = load_schedule_registry(Path(".jules/schedules.toml"))
    cycle_list = registry.get("cycle", [])
    if not cycle_list:
        print("No cycle defined in schedules.toml", file=sys.stderr)
        return

    base_context = {**repo_info, "open_prs": open_prs}
    loader = PersonaLoader(Path(".jules/personas"), base_context)
    personas = loader.load_personas(cycle_list)

    print(f"Loaded {len(personas)} personas: {[p.id for p in personas]}")

    # Initialize managers
    branch_mgr = BranchManager(JULES_BRANCH)
    pr_mgr = PRManager(JULES_BRANCH)
    cycle_mgr = CycleStateManager(personas)
    orchestrator = SessionOrchestrator(client, dry_run)

    # === ENSURE JULES BRANCH ===
    branch_mgr.ensure_jules_branch_exists()

    # === LOAD PERSISTENT STATE ===
    persistent_state = PersistentCycleState.load(CYCLE_STATE_PATH)

    # Determine next persona from persistent state
    if persistent_state.last_persona_id and persistent_state.last_persona_id in cycle_mgr.cycle_ids:
        next_idx, should_increment = cycle_mgr.advance_cycle(persistent_state.last_persona_id)
        next_persona_id = cycle_mgr.cycle_ids[next_idx]
        print(f"\n📍 Last cycle: {persistent_state.last_persona_id} (from state)")
    else:
        # Fallback to API if persistent state is missing or inconsistent
        state = client.get_cycle_state(repo_info["owner"], repo_info["repo"])
        if state and state.last_persona_id in cycle_mgr.cycle_ids:
            next_idx, should_increment = cycle_mgr.advance_cycle(state.last_persona_id)
            next_persona_id = cycle_mgr.cycle_ids[next_idx]
            print(f"\n📍 Last cycle: {state.last_persona_id} (from API)")
        else:
            next_idx = 0
            should_increment = False
            next_persona_id = cycle_mgr.cycle_ids[0]
            print("\n📍 No previous cycle found. Starting fresh.")

    print(f"➡️  Next persona: {next_persona_id}")
    print()

    # === HANDLE PREVIOUS SESSION ===
    last_session_id = persistent_state.last_session_id
    persona_pr = None
    is_direct = False

    if last_session_id:
        # Per user request, we minimize intermediary branches. Cycle sessions are now direct.
        is_direct = True
        
        # Check if an open PR exists (might be legacy or the integration PR itself)
        persona_pr = pr_mgr.find_by_session_id(open_prs, last_session_id)
        if persona_pr:
            is_direct = False # Found a branch PR, treat as legacy/explicit branch session

    if persona_pr:
        # HANDLING BRANCH-BASED SESSION (Legacy or Explicit)
        pr_number = persona_pr["number"]
        print(f"Found PR #{pr_number}: {persona_pr['title']}")

        # Ensure state is synced
        if persistent_state.last_pr_number != pr_number:
            persistent_state.last_pr_number = pr_number

        pr_details = get_pr_details_via_gh(pr_number)

        # 1. Automate Draft -> Ready
        if pr_mgr.is_draft(pr_details):
            print(f"📝 PR #{pr_number} is a draft. Checking session status...")
            try:
                session = client.get_session(last_session_id)
                session_state = session.get("state")
                if session_state == "COMPLETED":
                    print(f"✅ Session completed! Auto-marking PR as ready...")
                    if not dry_run:
                        pr_mgr.mark_ready(pr_number)
                        pr_details = get_pr_details_via_gh(pr_number)
                    if pr_mgr.is_draft(pr_details):
                        return # Waiting for API reflect
                elif session_state in ["IN_PROGRESS", "PENDING", "AWAITING_PLAN_APPROVAL", "AWAITING_USER_FEEDBACK"]:
                    # Try to unstick if needed
                    created_at = None
                    if persistent_state.history and persistent_state.history[0].get("session_id") == last_session_id:
                        created_at = persistent_state.history[0].get("created_at")
                    if orchestrator.handle_stuck_session(last_session_id, created_at):
                        # Skip if timed out
                        if should_increment: sprint_manager.increment_sprint()
                    else:
                        return
                else:
                    print(f"⏳ Session state: {session_state}. Waiting...")
                    return
            except Exception as e:
                print(f"⚠️ Error checking session: {e}")
                return

        # 2. Check if green and merge
        if not pr_mgr.is_green(pr_details):
            print(f"❌ PR #{pr_number} is not green. Waiting for CI.")
            return

        print(f"✅ PR #{pr_number} is green! Merging into '{JULES_BRANCH}'...")
        if not dry_run:
            pr_mgr.merge_into_jules(pr_number)
            branch_mgr.sync_with_main()
            pr_mgr.ensure_integration_pr_exists(repo_info)

        if should_increment:
            sprint_manager.increment_sprint()
        print(f"✨ Ready to start next persona: {next_persona_id}")

    elif last_session_id:
        # HANDLING DIRECT-PUSH SESSION (New Standard)
        print(f"🔍 Checking direct session {last_session_id[:12]}...")
        try:
            session = client.get_session(last_session_id)
            session_state = session.get("state")
            
            if session_state == "COMPLETED":
                print(f"✅ Direct session completed. Advancing cycle...")
                if should_increment:
                    sprint_manager.increment_sprint()
                # Continue below to next persona
            elif session_state in ["IN_PROGRESS", "PENDING", "AWAITING_PLAN_APPROVAL", "AWAITING_USER_FEEDBACK"]:
                print(f"⏳ Session is {session_state}. Waiting...")
                # Try to unstick if needed
                created_at = None
                if persistent_state.history and persistent_state.history[0].get("session_id") == last_session_id:
                    created_at = persistent_state.history[0].get("created_at")
                if orchestrator.handle_stuck_session(last_session_id, created_at):
                    if should_increment: sprint_manager.increment_sprint()
                else:
                    return
            else:
                print(f"⚠️ Session state '{session_state}'. Advancing to avoid deadlock.")
                if should_increment: sprint_manager.increment_sprint()
        except Exception as e:
            print(f"⚠️ Error checking session: {e}")
            return

    # === START NEXT SESSION ===
    next_persona = personas[next_idx]
    print(f"🚀 Starting session for {next_persona.emoji} {next_persona.id}")

    # DIRECT INTEGRATION: Work directly on jules branch
    session_branch = branch_mgr.create_session_branch(
        base_branch=JULES_BRANCH,
        persona_id=next_persona.id,
    )

    request = SessionRequest(
        persona_id=next_persona.id,
        title=f"{next_persona.emoji} {next_persona.id}: cycle task",
        prompt=next_persona.prompt_body,
        branch=session_branch,
        owner=repo_info["owner"],
        repo=repo_info["repo"],
        automation_mode="AUTO_CREATE_PR", 
        require_plan_approval=False,
    )

    session_id = orchestrator.create_session(request)
    print(f"✅ Created session: {session_id}")

    # === SAVE STATE ===
    if not dry_run and session_id != "[DRY RUN]":
        persistent_state.record_session(
            persona_id=next_persona.id,
            persona_index=next_idx,
            session_id=session_id,
        )
        persistent_state.save(CYCLE_STATE_PATH)
        commit_cycle_state(CYCLE_STATE_PATH, f"chore(jules): cycle state -> {next_persona.id}")

    print("=" * 70)


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

        # Scheduled mode uses direct branching now
        session_branch = branch_mgr.create_session_branch(
            base_branch=JULES_BRANCH,
            persona_id=persona.id,
        )

        request = SessionRequest(
            persona_id=persona.id,
            title=f"{persona.emoji} {persona.id}: scheduled task",
            prompt=persona.prompt_body,
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
    cycle_list = registry.get("cycle", [])
    is_cycle_mode = command == "tick" and not run_all and not prompt_id and bool(cycle_list)

    client = JulesClient()
    repo_info = get_repo_info()
    pr_mgr = PRManager(JULES_BRANCH)

    if is_cycle_mode:
        execute_cycle_tick(dry_run)
        print("\nChecking for additional scheduled tasks...")
        execute_scheduled_tick(run_all=False, prompt_id=None, dry_run=dry_run)
    else:
        if prompt_id or run_all:
            execute_scheduled_tick(run_all, prompt_id, dry_run)
        else:
            execute_cycle_tick(dry_run)

    # === GLOBAL RECONCILIATION ===
    # Automate the lifecycle for ALL Jules PRs (parallel and cycle)
    pr_mgr.reconcile_all_jules_prs(client, repo_info, dry_run)
