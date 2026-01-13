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

        # Direct Branching
        session_branch = branch_mgr.create_session_branch(
            base_branch=JULES_BRANCH,
            persona_id=next_p.id
        )

        request = SessionRequest(
            persona_id=next_p.id,
            title=f"{next_p.emoji} {next_p.id}: {track_name} task",
            prompt=next_p.prompt_body,
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
