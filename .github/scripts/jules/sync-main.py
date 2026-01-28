#!/usr/bin/env python3
"""Sync jules branch into main if clean (no conflicts)."""

import subprocess
import sys


def merge_jules_into_main() -> None:
    """Merge jules branch into main if there are no conflicts.

    This performs a fast-forward merge if possible, otherwise a regular merge.
    """
    # Get current branch to restore later
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    original_branch = result.stdout.strip()

    try:
        # Checkout main
        print("Checking out main branch...")
        subprocess.run(["git", "checkout", "main"], check=True)

        # Try to fast-forward merge
        print("Attempting to merge jules into main...")
        result = subprocess.run(
            ["git", "merge", "origin/jules", "--ff-only"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("Fast-forward merge successful!")
        else:
            # Try regular merge
            print("Fast-forward not possible, attempting regular merge...")
            subprocess.run(
                ["git", "merge", "origin/jules", "-m", "Merge jules branch into main"],
                check=True,
            )
            print("Merge successful!")

        # Push the changes
        print("Pushing to origin/main...")
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("Push successful!")

    except subprocess.CalledProcessError as e:
        print(f"Error during merge: {e}", file=sys.stderr)
        # Abort any in-progress merge
        subprocess.run(["git", "merge", "--abort"], capture_output=True)
        raise
    finally:
        # Restore original branch
        if original_branch and original_branch != "main":
            subprocess.run(["git", "checkout", original_branch], capture_output=True)


def create_jules_from_main() -> None:
    """Create jules branch from main if it doesn't exist on remote."""
    print("Creating jules branch from main...")

    # Fetch latest main
    subprocess.run(["git", "fetch", "origin", "main"], check=True)

    # Delete local jules branch if it exists (we only care about remote)
    subprocess.run(
        ["git", "branch", "-D", "jules"],
        capture_output=True,  # Ignore errors if branch doesn't exist
    )

    # Create jules branch pointing to origin/main
    subprocess.run(
        ["git", "branch", "jules", "origin/main"],
        check=True,
    )

    # Push jules branch to remote
    print("Pushing jules branch to origin...")
    subprocess.run(["git", "push", "-u", "origin", "jules"], check=True)
    print("Jules branch created successfully!")


def main() -> None:
    # Check if jules branch exists on remote
    result = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", "jules"],
        capture_output=True,
        text=True,
    )
    # Only create jules branch if ls-remote succeeded AND returned no output
    # If ls-remote fails (e.g., network issues), don't assume branch is missing
    if result.returncode != 0:
        print(f"Error checking remote: {result.stderr}", file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, result.args)
    if not result.stdout.strip():
        # Jules branch doesn't exist, create it from main
        print("No 'jules' branch found on remote. Creating from main...")
        create_jules_from_main()
        return

    # Ensure we have latest refs
    subprocess.run(["git", "fetch", "origin", "main", "jules"], check=True)

    # Perform the merge
    merge_jules_into_main()


if __name__ == "__main__":
    main()
