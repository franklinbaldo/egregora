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
    """Execute one tick of the cycle scheduler.

    In cycle mode, the scheduler:
    1. Ensures the Jules integration branch exists
    2. Finds the last cycle session (if any)
    3. If last session has a green PR, merges it and advances
    4. If last session is stuck, attempts to unstick it
    5. Starts the next persona in the cycle

    The cycle advances sequentially through all personas, merging PRs
    before moving to the next. When a full cycle completes, the sprint
    number increments.

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
        print(f"\n📍 Last cycle: {persistent_state.last_persona_id} (from state file)")
    else:
        # Fallback to API-based detection
        state = cycle_mgr.find_last_cycle_session(client, repo_info, open_prs)
        next_idx = state.next_persona_index
        next_persona_id = state.next_persona_id
        should_increment = state.should_increment_sprint
        if state.last_session_id:
            print(f"\n📍 Last cycle: {state.last_persona_id} (from API)")
        else:
            print("\n📍 No previous cycle found. Starting fresh.")

    print(f"➡️  Next persona: {next_persona_id}")
    print()

    # === HANDLE PREVIOUS SESSION ===
    last_session_id = persistent_state.last_session_id
    if last_session_id:
        pr = pr_mgr.find_by_session_id(open_prs, last_session_id)

        if pr:
            # Found open PR for last session
            pr_number = pr["number"]
            print(f"Found PR #{pr_number}: {pr['title']}")
            
            # Update persistent state with PR number if missing
            if persistent_state.last_pr_number != pr_number:
                persistent_state.update_pr_number(pr_number)
                persistent_state.save(CYCLE_STATE_PATH)
                # Don't commit state yet, wait for session change or merge

            pr_details = get_pr_details_via_gh(pr_number)

            # Check if PR is draft - auto-mark as ready if session is complete
            if pr_mgr.is_draft(pr_details):
                print(f"📝 PR #{pr_number} is a draft. Checking session status...")
                try:
                    session_details = client.get_session(last_session_id)
                    session_state = session_details.get("state")

                    if session_state == "COMPLETED":
                        # Session done but PR still draft - mark as ready
                        print(f"✅ Session completed. Auto-marking PR as ready for review...")
                        if not dry_run:
                            pr_mgr.mark_ready(pr_number)
                        # Re-fetch PR details after marking ready
                        pr_details = get_pr_details_via_gh(pr_number)

                        # Verify PR is no longer draft (GitHub API might have delay)
                        if pr_mgr.is_draft(pr_details):
                            print(f"⏳ PR still shows as draft after marking ready. Waiting for next tick...")
                            return
                    else:
                        print(f"⏳ Session state: {session_state}. Waiting for completion...")
                        return
                except Exception as e:
                    print(f"❌ Error checking session: {e}. Waiting for next tick.")
                    return

            # Check if PR is green
            if not pr_mgr.is_green(pr_details):
                print(f"❌ PR #{pr_number} is not green. Waiting for CI to pass.")
                return

            # Final safety check: ensure PR is not a draft before merging
            if pr_mgr.is_draft(pr_details):
                print(f"⚠️  PR #{pr_number} is still a draft. Cannot merge. Waiting...")
                return

            # PR is ready - merge it!
            print(f"✅ PR #{pr_number} is green! Merging into '{JULES_BRANCH}'...")
            if not dry_run:
                pr_mgr.merge_into_jules(pr_number)

                # Sync with main to capture external changes
                print(f"📥 Syncing '{JULES_BRANCH}' with main...")
                drift_info = branch_mgr.sync_with_main()

                # Handle drift if it occurred
                if drift_info:
                    handle_drift_reconciliation(
                        drift_info, client, repo_info, branch_mgr, pr_mgr, dry_run
                    )
                    return  # Stop here - reconciliation will continue on next tick

            # Check if we should increment sprint
            if should_increment:
                old_sprint = sprint_manager.get_current_sprint()
                new_sprint = sprint_manager.increment_sprint()
                print(f"🎉 Cycle completed! Sprint: {old_sprint} → {new_sprint}")

            print(f"✨ Ready to start next persona: {next_persona_id}")
            print()

        else:
            # PR not found in open PRs - check if merged or stuck
            print(f"PR for session {last_session_id} not found in open PRs.")
            print("Checking if session is stuck or PR already merged...")

            from jules.github import get_pr_by_session_id_any_state

            pr_any_state = get_pr_by_session_id_any_state(
                repo_info["owner"], repo_info["repo"], last_session_id
            )

            if pr_any_state and pr_any_state.get("mergedAt"):
                # PR already merged - advance!
                print(f"✅ PR already merged. Continuing to {next_persona_id}")

                # Sync with main to ensure we have latest changes
                if not dry_run:
                    print(f"📥 Syncing '{JULES_BRANCH}' with main...")
                    drift_info = branch_mgr.sync_with_main()

                    # Handle drift if it occurred
                    if drift_info:
                        handle_drift_reconciliation(
                            drift_info, client, repo_info, branch_mgr, pr_mgr, dry_run
                        )
                        return  # Stop here - reconciliation will continue on next tick

                if should_increment:
                    sprint_manager.increment_sprint()
                print()

            elif pr_any_state and (pr_any_state.get("state") or "").lower() == "closed":
                # PR was closed without merging - skip it
                print(f"⚠️  PR was closed without merging. Skipping to {next_persona_id}")
                if should_increment:
                    sprint_manager.increment_sprint()
                print()

            else:
                # Session might be stuck - check state first
                print("🔧 Checking session state...")
                try:
                    session_details = client.get_session(last_session_id)
                    session_state = session_details.get("state")

                    # Handle terminal states
                    if session_state == "CANCELLED":
                        # Intentionally cancelled - skip to next persona
                        print(f"⚠️  Session {last_session_id} was cancelled. Advancing to next persona.")
                        if should_increment:
                            sprint_manager.increment_sprint()
                        print()
                        # Don't return - continue to create next session
                    elif session_state in ["COMPLETED", "FAILED"]:
                        # Completed/failed but no PR - ask Jules to finalize
                        print(f"⚠️  Session {last_session_id} is in state '{session_state}' but no PR was created.")
                        print("Sending message to request PR creation...")
                        if not dry_run:
                            finalize_message = (
                                "A sessão está em estado terminal mas nenhuma PR foi criada. "
                                "Por favor, finalize o trabalho criando uma Pull Request com as mudanças realizadas, "
                                "ou se não há mudanças a fazer, finalize a sessão adequadamente."
                            )
                            client.send_message(last_session_id, finalize_message)
                            print(f"Finalization message sent to session {last_session_id}.")
                        return  # Wait for Jules to respond
                    else:
                        # Session is stuck - try to unstick
                        print(f"🔧 Session state: {session_state}. Attempting to unstick...")
                        orchestrator.handle_stuck_session(last_session_id)
                        return  # Don't start new session, wait for stuck one to complete
                except Exception as e:
                    print(f"❌ Error checking session {last_session_id}: {e}", file=sys.stderr)
                    return

    # === START NEXT SESSION ===
    next_persona = personas[next_idx]
    print(f"🚀 Starting session for {next_persona.emoji} {next_persona.id}")

    # Create session request (using jules branch directly)
    title = f"{next_persona.emoji} {next_persona.id}: automated cycle task for {repo_info['repo']}"
    request = SessionRequest(
        persona_id=next_persona.id,
        title=title,
        prompt=next_persona.prompt_body,
        branch=JULES_BRANCH,  # Use jules directly instead of intermediate branch
        owner=repo_info["owner"],
        repo=repo_info["repo"],
        automation_mode="AUTO_CREATE_PR",
        require_plan_approval=False,
    )

    # Create session
    session_id = orchestrator.create_session(request)
    print(f"✅ Created session: {session_id}")

    # === SAVE PERSISTENT STATE ===
    if not dry_run and session_id != "[DRY RUN]":
        persistent_state.record_session(
            persona_id=next_persona.id,
            persona_index=next_idx,
            session_id=session_id,
        )
        persistent_state.save(CYCLE_STATE_PATH)
        commit_cycle_state(
            CYCLE_STATE_PATH,
            f"chore(jules): cycle state → {next_persona.id} (session {session_id[:12]})"
        )

    # Check if we should increment sprint
    if should_increment:
        old_sprint = sprint_manager.get_current_sprint()
        new_sprint = sprint_manager.increment_sprint()
        print(f"🎉 Cycle completed! Sprint: {old_sprint} → {new_sprint}")

    print()
    print("=" * 70)


def execute_scheduled_tick(
    run_all: bool = False, prompt_id: str | None = None, dry_run: bool = False
) -> None:
    """Execute scheduled personas based on cron schedules.

    In scheduled mode, the scheduler:
    1. Loads all personas
    2. Checks which ones should run (based on cron or flags)
    3. Creates sessions for matching personas

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
    personas = loader.load_personas([])  # Empty list = load all

    # Load schedules
    registry = load_schedule_registry(Path(".jules/schedules.toml"))
    schedules = registry.get("schedules", {})

    orchestrator = SessionOrchestrator(client, dry_run)

    print(f"Loaded {len(personas)} personas")
    print(f"Current time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print()

    # === FILTER AND RUN PERSONAS ===
    sessions_created = 0

    for persona in personas:
        # Check if persona should run
        should_run = False
        reason = ""

        if run_all:
            should_run = True
            reason = "--all flag"
        elif prompt_id and prompt_id in {persona.id, persona.path}:
            should_run = True
            reason = f"--prompt-id={prompt_id}"
        else:
            # Check schedule
            schedule_str = schedules.get(persona.id, "")
            if schedule_str and check_schedule(schedule_str):
                should_run = True
                reason = f"schedule: {schedule_str}"

        if not should_run:
            continue

        # Run this persona
        print(f"▶️  {persona.emoji} {persona.id} ({reason})")

        # Create session request
        title = f"{persona.emoji} {persona.id}: scheduled task for {repo_info['repo']}"
        request = SessionRequest(
            persona_id=persona.id,
            title=title,
            prompt=persona.prompt_body,
            branch="main",  # Scheduled mode uses main
            owner=repo_info["owner"],
            repo=repo_info["repo"],
            automation_mode="AUTO_CREATE_PR",
            require_plan_approval=False,
        )

        # Create session
        session_id = orchestrator.create_session(request)
        print(f"   ✅ Session: {session_id}")
        print()
        sessions_created += 1

    if sessions_created == 0:
        print("No personas matched the criteria. Nothing to run.")
    else:
        print(f"✅ Created {sessions_created} session(s)")

    print("=" * 70)


def run_scheduler(
    command: str, run_all: bool = False, dry_run: bool = False, prompt_id: str | None = None
) -> None:
    """Main scheduler entry point.

    Routes to either cycle or scheduled mode based on command and configuration.

    Args:
        command: Command to run ("tick", etc.)
        run_all: Run all personas (scheduled mode only)
        dry_run: Print actions without executing
        prompt_id: Run specific persona (scheduled mode only)
    """
    # Load registry to check for cycle mode
    registry = load_schedule_registry(Path(".jules/schedules.toml"))
    cycle_list = registry.get("cycle", [])

    # Determine mode
    is_cycle_mode = command == "tick" and not run_all and not prompt_id and bool(cycle_list)

    if is_cycle_mode:
        execute_cycle_tick(dry_run)
    else:
        execute_scheduled_tick(run_all, prompt_id, dry_run)
