#!/usr/bin/env python3
"""
Pre-commit hook to validate that newly hired personas are voted for.

Rules:
1. If you hire a new persona (create new prompt file), you MUST vote for them
2. The new hire MUST be your TOP choice (first in the candidates list)

Detects new persona files in staged changes and checks votes.csv for matching votes.
"""

import subprocess
import sys
from pathlib import Path

# Add .team to path for imports
sys.path.insert(0, ".team")


def get_active_persona() -> str | None:
    """Get the currently active persona from session."""
    try:
        from repo.features.session import SessionManager

        sm = SessionManager()
        return sm.get_active_persona()
    except Exception:
        return None


def get_newly_hired_personas() -> list[str]:
    """Get list of newly created persona prompt files in staged changes."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=A"], capture_output=True, text=True
    )
    if result.returncode != 0:
        return []

    new_hires = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        path = Path(line)
        # Check if it's a new persona prompt file
        if ".team/personas/" in str(path) and "prompt.md" in path.name:
            # Extract persona ID from path like .team/personas/<id>/prompt.md.j2
            parts = path.parts
            try:
                personas_idx = parts.index("personas")
                if personas_idx + 1 < len(parts):
                    new_hires.append(parts[personas_idx + 1])
            except ValueError:
                pass
    return new_hires


def get_votes_for_sequence(voter_sequence: str) -> list[tuple[str, list[str]]]:
    """Get all votes from a voter sequence. Returns list of (sequence_cast, candidates)."""
    votes_file = Path(".team/votes.csv")
    if not votes_file.exists():
        return []

    import csv

    votes = []
    with open(votes_file, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["voter_sequence"] == voter_sequence:
                candidates = [c.strip() for c in row.get("candidates", "").split(",")]
                votes.append((row["sequence_cast"], candidates))
    return votes


def get_current_sequence(persona_id: str) -> str | None:
    """Get the currently active sequence for a persona."""
    try:
        from repo.features.voting import VoteManager

        vm = VoteManager()
        return vm.get_current_sequence(persona_id)
    except Exception:
        return None


def main():
    new_hires = get_newly_hired_personas()
    if not new_hires:
        # No new persona files, nothing to validate
        return 0

    active_persona = get_active_persona()
    if not active_persona:
        print("\n❌ HIRE VALIDATION ERROR")
        print("=" * 50)
        print("Cannot determine active persona to check votes.")
        print("=" * 50)
        return 1

    voter_sequence = get_current_sequence(active_persona)
    if not voter_sequence:
        print("\n❌ HIRE VALIDATION ERROR")
        print("=" * 50)
        print("Cannot determine current sequence for vote validation.")
        print("=" * 50)
        return 1

    votes = get_votes_for_sequence(voter_sequence)

    violations = []
    for new_hire in new_hires:
        # Check if there's a vote with this new hire as TOP choice
        found_as_top = False
        for _seq_cast, candidates in votes:
            if candidates and candidates[0] == new_hire:
                found_as_top = True
                break

        if not found_as_top:
            violations.append(new_hire)

    if violations:
        print("\n❌ HIRE WITHOUT VOTE VIOLATION")
        print("=" * 60)
        print("You hired new personas but did NOT vote for them as TOP choice!\n")
        for v in violations:
            print(f"  ❌ Missing vote for: {v}")
        print()
        print("─" * 60)
        print("HOW TO FIX:")
        print()
        print("  Option 1: CAST THE VOTE (recommended)")
        print("  Vote for your new hire as #1 choice:")
        for v in violations:
            print(f"    my-tools vote --persona {v} --persona <others...> --password <pwd>")
        print("  Note: New votes overwrite previous votes for the same sequence.")
        print()
        print("  Option 2: DELETE THE NEW HIRE")
        print("  Unstage or remove the persona files:")
        for v in violations:
            print(f"    git restore --staged .team/personas/{v}/")
            print(f"    rm -rf .team/personas/{v}/")
        print()
        print("=" * 60)
        return 1

    print(f"✅ Hire validation passed: {', '.join(new_hires)} voted as top choice")
    return 0


if __name__ == "__main__":
    sys.exit(main())
