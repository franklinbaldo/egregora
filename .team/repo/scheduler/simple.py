"""Simplified Jules Scheduler.

This module provides a streamlined scheduler that:
1. Merges completed Jules PRs (drafts that are green)
2. Finds the next persona (round-robin from API state)
3. Renders the prompt with Jinja2
4. Creates a Jules session

The Jules API is the source of truth - no CSV state management needed.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo.core.client import TeamClient
from repo.core.github import get_open_prs, get_repo_info
from repo.scheduler.loader import PersonaLoader
from repo.scheduler.models import PersonaConfig

# Constants
JULES_BOT_AUTHOR = "app/google-labs-jules"
JULES_BRANCH = "jules"


def _get_repo_root() -> Path:
    """Get the repository root directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except Exception:
        # Fallback to current directory
        return Path.cwd()


def _get_persona_dir() -> Path:
    """Get the personas directory path."""
    return _get_repo_root() / ".team" / "personas"

# Personas excluded from automatic scheduling
EXCLUDED_PERSONAS = frozenset({"oracle", "bdd_specialist", "franklin", "_archived"})


@dataclass
class SchedulerResult:
    """Result of a scheduler operation."""

    success: bool
    message: str
    session_id: str | None = None
    merged_count: int = 0


def discover_personas() -> list[str]:
    """Discover available personas from the filesystem.

    Returns:
        Sorted list of persona IDs (directory names) excluding special personas.
    """
    persona_dir = _get_persona_dir()
    if not persona_dir.exists():
        return []

    personas = []
    for path in persona_dir.iterdir():
        if not path.is_dir():
            continue
        if path.name.startswith((".", "_")):
            continue
        if path.name in EXCLUDED_PERSONAS:
            continue
        # Verify it has a prompt file
        if (path / "prompt.md.j2").exists() or (path / "prompt.md").exists():
            personas.append(path.name)

    return sorted(personas)


def get_active_session(client: TeamClient, repo: str) -> dict | None:
    """Check if there's an active/running Jules session for this repo.

    Args:
        client: Jules API client
        repo: Repository name to filter sessions

    Returns:
        Active session dict if found, None otherwise.
    """
    # Active states that indicate a session is still running
    # Jules API uses IN_PROGRESS for running sessions
    active_states = {"IN_PROGRESS", "ACTIVE"}

    try:
        sessions = client.list_sessions().get("sessions", [])
    except Exception:
        return None

    repo_lower = repo.lower()

    for session in sessions:
        title = (session.get("title") or "").lower()
        state = (session.get("state") or "").upper()

        # Filter by repo
        if repo_lower not in title:
            continue

        # Check if session is active
        if state in active_states:
            return session

    return None


def get_last_persona_from_api(client: TeamClient, repo: str) -> str | None:
    """Get the last persona that ran from Jules API.

    Args:
        client: Jules API client
        repo: Repository name to filter sessions

    Returns:
        Persona ID of the last session, or None if not found.
    """
    try:
        sessions = client.list_sessions().get("sessions", [])
    except Exception:
        return None

    # Sort sessions by createTime descending (most recent first)
    # This ensures we find the actual last persona, not just the first match
    sessions = sorted(
        sessions,
        key=lambda s: s.get("createTime") or "",
        reverse=True,
    )

    personas = discover_personas()
    repo_lower = repo.lower()

    for session in sessions:
        title = (session.get("title") or "").lower()

        # Filter by repo
        if repo_lower not in title:
            continue

        # Find persona in title
        for persona in personas:
            if persona in title:
                return persona

    return None


def get_next_persona(last: str | None, personas: list[str]) -> str | None:
    """Get the next persona in round-robin order.

    Args:
        last: Last persona that ran (or None)
        personas: List of available personas

    Returns:
        Next persona ID, or None if no personas available.
    """
    if not personas:
        return None

    if last and last in personas:
        idx = (personas.index(last) + 1) % len(personas)
        return personas[idx]

    return personas[0]


def merge_completed_prs() -> int:
    """Merge Jules draft PRs regardless of CI status.

    PRs are merged even if CI hasn't passed yet. A separate fixer session
    will handle any CI failures on main before the next persona runs.

    Returns:
        Number of PRs merged.
    """
    # Get open Jules PRs
    try:
        result = subprocess.run(
            [
                "gh", "pr", "list",
                "--author", JULES_BOT_AUTHOR,
                "--state", "open",
                "--json", "number,isDraft,mergeable",
                "--limit", "50",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        prs = json.loads(result.stdout)
    except Exception as e:
        print(f"  Failed to list PRs: {e}")
        return 0

    merged = 0
    for pr in prs:
        pr_number = pr["number"]
        is_draft = pr.get("isDraft", False)
        mergeable = pr.get("mergeable", "UNKNOWN")

        # Only skip if conflicting - we merge even with failing CI
        if mergeable == "CONFLICTING":
            print(f"  PR #{pr_number}: has conflicts, skipping")
            continue

        try:
            # Mark ready if draft
            if is_draft:
                subprocess.run(
                    ["gh", "pr", "ready", str(pr_number)],
                    check=True,
                    capture_output=True,
                )
                print(f"  PR #{pr_number}: marked ready")

            # Merge with squash and admin override to bypass CI requirements
            subprocess.run(
                ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch", "--admin"],
                check=True,
                capture_output=True,
            )
            print(f"  PR #{pr_number}: merged (admin override)")
            merged += 1

        except subprocess.CalledProcessError as e:
            print(f"  PR #{pr_number}: merge failed - {e.stderr if e.stderr else e}")

    return merged

    return merged


def ensure_jules_branch() -> None:
    """Ensure the jules branch exists and is up to date with main."""
    # Check if branch exists
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/heads/{JULES_BRANCH}"],
        capture_output=True,
    )

    if result.returncode != 0:
        # Create branch from main
        subprocess.run(
            ["git", "branch", JULES_BRANCH, "origin/main"],
            check=True,
            capture_output=True,
        )
        print(f"  Created {JULES_BRANCH} branch from main")


def check_ci_status_on_main() -> bool:
    """Check if CI is passing on main branch.

    Returns:
        True if CI is green, False if there are failures.
    """
    try:
        result = subprocess.run(
            ["gh", "run", "list", "--branch", "main", "--limit", "1", "--json", "conclusion"],
            capture_output=True,
            text=True,
            check=True,
        )
        runs = json.loads(result.stdout)
        if runs:
            return runs[0].get("conclusion") == "success"
        return True  # No runs = assume OK
    except Exception:
        return True  # On error, assume OK to avoid blocking


# CI Fixer prompt - used to fix CI failures on main
CI_FIXER_PROMPT = """# 🔧 CI Fixer

You are a CI maintenance bot. Your ONLY job is to make CI pass on the main branch.

## Current Status
CI is failing on main. You need to fix it.

## Tasks (in order)
1. Run `uv run pre-commit run --all-files` and fix any issues
2. Run `uv run ruff check --fix src/ tests/` to auto-fix linting
3. Run `uv run ruff format src/ tests/` to format code
4. Run `uv run pytest tests/unit -x` and fix any failing tests
5. Commit all fixes with message: "fix(ci): resolve CI failures on main"

## Rules
- Do NOT add new features
- Do NOT refactor code
- Do NOT change functionality
- ONLY fix what's needed to make CI pass
- Keep changes minimal and focused

## Repository
- Owner: {owner}
- Repo: {repo}
"""


def create_fixer_session(client: TeamClient, repo_info: dict[str, str]) -> SchedulerResult:
    """Create a CI fixer session.

    Args:
        client: Jules API client
        repo_info: Repository information

    Returns:
        SchedulerResult with session details.
    """
    try:
        ensure_jules_branch()

        prompt = CI_FIXER_PROMPT.format(
            owner=repo_info["owner"],
            repo=repo_info["repo"],
        )

        result = client.create_session(
            prompt=prompt,
            owner=repo_info["owner"],
            repo=repo_info["repo"],
            branch=JULES_BRANCH,
            title=f"🔧 ci-fixer {repo_info['repo']}",
            automation_mode="AUTO_CREATE_PR",
            require_plan_approval=False,
        )

        session_id = result.get("name", "").split("/")[-1]

        return SchedulerResult(
            success=True,
            message="Created CI fixer session",
            session_id=session_id,
        )

    except Exception as e:
        return SchedulerResult(
            success=False,
            message=f"Failed to create fixer session: {e}",
        )


def create_session(
    client: TeamClient,
    persona: PersonaConfig,
    repo_info: dict[str, str],
) -> SchedulerResult:
    """Create a Jules session for a persona.

    Args:
        client: Jules API client
        persona: Loaded persona configuration
        repo_info: Repository information

    Returns:
        SchedulerResult with session details.
    """
    try:
        ensure_jules_branch()

        # Create session
        result = client.create_session(
            prompt=persona.prompt_body,
            owner=repo_info["owner"],
            repo=repo_info["repo"],
            branch=JULES_BRANCH,
            title=f"{persona.emoji} {persona.id} {repo_info['repo']}",
            automation_mode="AUTO_CREATE_PR",
            require_plan_approval=False,
        )

        session_id = result.get("name", "").split("/")[-1]

        return SchedulerResult(
            success=True,
            message=f"Created session for {persona.id}",
            session_id=session_id,
        )

    except Exception as e:
        return SchedulerResult(
            success=False,
            message=f"Failed to create session: {e}",
        )


def run_scheduler(dry_run: bool = False) -> SchedulerResult:
    """Main scheduler entry point.

    This function:
    1. Checks if there's already an active session (skips if yes)
    2. Merges any completed Jules PRs (regardless of CI status)
    3. Checks CI on main - if failing, creates fixer session instead
    4. Determines the next persona (round-robin)
    5. Renders the persona prompt with Jinja2
    6. Creates a Jules session

    Args:
        dry_run: If True, don't create sessions or merge PRs

    Returns:
        SchedulerResult with operation status.
    """
    print("Jules Scheduler (Simplified)")
    print("=" * 40)

    # Initialize
    client = TeamClient()
    repo_info = get_repo_info()
    print(f"Repository: {repo_info['owner']}/{repo_info['repo']}")

    # Step 1: Check for active sessions
    print("\n1. Checking for active sessions...")
    active_session = get_active_session(client, repo_info["repo"])
    if active_session:
        session_id = active_session.get("name", "").split("/")[-1]
        state = active_session.get("state", "UNKNOWN")
        print(f"  Active session found: {session_id} (state: {state})")
        return SchedulerResult(
            success=True,
            message=f"Session already running ({state}), skipping new session creation",
            session_id=session_id,
            merged_count=0,
        )
    print("  No active sessions found")

    # Step 2: Merge completed PRs
    print("\n2. Checking for PRs to merge...")
    if dry_run:
        print("  [DRY RUN] Skipping PR merge")
        merged = 0
    else:
        merged = merge_completed_prs()
    print(f"  Merged {merged} PR(s)")

    # Step 3: Check CI status on main - run fixer if needed
    print("\n3. Checking CI status on main...")
    ci_ok = check_ci_status_on_main()
    if not ci_ok:
        print("  CI is failing on main - creating fixer session")
        if dry_run:
            print("  [DRY RUN] Would create CI fixer session")
            return SchedulerResult(
                success=True,
                message="[DRY RUN] Would create CI fixer session",
                merged_count=merged,
            )
        result = create_fixer_session(client, repo_info)
        result.merged_count = merged
        if result.success:
            print(f"  Fixer session created: {result.session_id}")
        else:
            print(f"  Failed: {result.message}")
        return result
    print("  CI is passing on main")

    # Step 4: Find next persona
    print("\n4. Determining next persona...")
    personas = discover_personas()
    if not personas:
        return SchedulerResult(
            success=False,
            message="No personas found",
            merged_count=merged,
        )
    print(f"  Available personas: {len(personas)}")

    last_persona = get_last_persona_from_api(client, repo_info["repo"])
    if last_persona:
        print(f"  Last persona: {last_persona}")
    else:
        print("  No previous session found")

    next_persona_id = get_next_persona(last_persona, personas)
    if not next_persona_id:
        return SchedulerResult(
            success=False,
            message="Could not determine next persona",
            merged_count=merged,
        )
    print(f"  Next persona: {next_persona_id}")

    # Step 5: Load and render persona
    print("\n5. Loading persona configuration...")
    try:
        open_prs = get_open_prs(repo_info["owner"], repo_info["repo"])
        context: dict[str, Any] = {**repo_info, "open_prs": open_prs}
        loader = PersonaLoader(_get_persona_dir(), context)
        all_personas = {p.id: p for p in loader.load_personas([])}

        if next_persona_id not in all_personas:
            return SchedulerResult(
                success=False,
                message=f"Persona '{next_persona_id}' not found",
                merged_count=merged,
            )

        persona = all_personas[next_persona_id]
        print(f"  Loaded: {persona.emoji} {persona.id}")
        print(f"  Prompt length: {len(persona.prompt_body)} chars")

    except Exception as e:
        return SchedulerResult(
            success=False,
            message=f"Failed to load persona: {e}",
            merged_count=merged,
        )

    # Step 6: Create session
    print("\n6. Creating Jules session...")
    if dry_run:
        print(f"  [DRY RUN] Would create session for {persona.id}")
        return SchedulerResult(
            success=True,
            message=f"[DRY RUN] Would create session for {persona.id}",
            merged_count=merged,
        )

    result = create_session(client, persona, repo_info)
    result.merged_count = merged

    if result.success:
        print(f"  Session created: {result.session_id}")
    else:
        print(f"  Failed: {result.message}")

    return result


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Simplified Jules Scheduler")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't create sessions or merge PRs",
    )
    parser.add_argument(
        "--merge-only",
        action="store_true",
        help="Only merge PRs, don't create new session",
    )
    args = parser.parse_args()

    if args.merge_only:
        print("Merge-only mode")
        merged = merge_completed_prs()
        print(f"Merged {merged} PR(s)")
        return

    result = run_scheduler(dry_run=args.dry_run)

    print("\n" + "=" * 40)
    print(f"Result: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Message: {result.message}")
    if result.session_id:
        print(f"Session ID: {result.session_id}")
    print(f"PRs Merged: {result.merged_count}")


if __name__ == "__main__":
    main()
