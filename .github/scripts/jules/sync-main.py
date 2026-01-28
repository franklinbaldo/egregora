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


def main() -> None:
    # Ensure we have latest refs
    subprocess.run(["git", "fetch", "origin", "main", "jules"], check=True)

    # Perform the merge
    merge_jules_into_main()


if __name__ == "__main__":
    main()
