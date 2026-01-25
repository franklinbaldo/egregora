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
    """Merge Jules draft PRs that have passing checks.

    Returns:
        Number of PRs merged.
    """
    # Get open Jules PRs with check status
    try:
        result = subprocess.run(
            [
                "gh", "pr", "list",
                "--author", JULES_BOT_AUTHOR,
                "--state", "open",
                "--json", "number,isDraft,statusCheckRollup,mergeable",
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

        # Check if all checks pass
        checks = pr.get("statusCheckRollup") or []
        if checks:
            all_green = all(
                (c.get("conclusion") or "").upper() in ("SUCCESS", "NEUTRAL", "SKIPPED")
                for c in checks
            )
        else:
            # No checks (or none reported) -> assume ready if not conflicting
            all_green = True

        # Skip if not ready
        if not all_green:
            continue
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

            # Merge with squash
            subprocess.run(
                ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"],
                check=True,
                capture_output=True,
            )
            print(f"  PR #{pr_number}: merged")
            merged += 1

        except subprocess.CalledProcessError as e:
            print(f"  PR #{pr_number}: merge failed - {e.stderr if e.stderr else e}")

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
    1. Merges any completed Jules PRs
    2. Determines the next persona (round-robin)
    3. Renders the persona prompt with Jinja2
    4. Creates a Jules session

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

    # Step 1: Merge completed PRs
    print("\n1. Checking for PRs to merge...")
    if dry_run:
        print("  [DRY RUN] Skipping PR merge")
        merged = 0
    else:
        merged = merge_completed_prs()
    print(f"  Merged {merged} PR(s)")

    # Step 2: Find next persona
    print("\n2. Determining next persona...")
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

    # Step 3: Load and render persona
    print("\n3. Loading persona configuration...")
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

    # Step 4: Create session
    print("\n4. Creating Jules session...")
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
