#!/usr/bin/env python3
"""Bidirectional sync between jules and main branches.

Forward sync:  jules → main  (merge Jules work into main)
Reverse sync:  main → jules  (keep jules up to date with main)
"""

import subprocess
import sys


def _configure_git_identity() -> None:
    """Configure git user identity for commits (required in GitHub Actions)."""
    subprocess.run(
        ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "github-actions[bot]"],
        check=True,
    )


def merge_jules_into_main() -> None:
    """Merge jules branch into main if there are no conflicts.

    This performs a fast-forward merge if possible, otherwise a regular merge.
    """
    _configure_git_identity()

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


def sync_jules_to_main() -> None:
    """Update jules branch to match main (reverse sync).

    After merging jules → main, the jules branch may be behind main
    (e.g. if non-Jules PRs were merged directly to main). This updates
    jules to point to the same commit as main so the next Jules session
    starts from the latest code.

    SAFETY: Before resetting, verifies that all jules commits are already
    in main (i.e. origin/jules is an ancestor of origin/main). If jules
    has commits that main doesn't, the reset is skipped to prevent data loss.
    """
    print("\nSyncing jules branch to match main...")

    # Check if jules is already up to date with main
    result = subprocess.run(
        ["git", "rev-parse", "origin/main"],
        capture_output=True,
        text=True,
        check=True,
    )
    main_sha = result.stdout.strip()

    result = subprocess.run(
        ["git", "rev-parse", "origin/jules"],
        capture_output=True,
        text=True,
        check=True,
    )
    jules_sha = result.stdout.strip()

    if main_sha == jules_sha:
        print("Jules branch is already up to date with main.")
        return

    print(f"  main  @ {main_sha[:10]}")
    print(f"  jules @ {jules_sha[:10]}")

    # SAFETY CHECK: Verify jules is an ancestor of main (all jules commits
    # are in main). If jules has commits that main doesn't, resetting would
    # destroy them. The forward sync should have merged them, but this guard
    # prevents data loss if the forward sync failed silently or was skipped.
    ancestor_check = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "origin/jules", "origin/main"],
    )
    if ancestor_check.returncode != 0:
        print(
            "  WARNING: jules has commits not in main. "
            "Skipping reverse sync to prevent data loss.",
            file=sys.stderr,
        )
        print(
            "  Run the forward sync (jules → main) first to preserve these commits.",
            file=sys.stderr,
        )
        return

    # Update jules to point to same commit as main
    try:
        subprocess.run(["git", "checkout", "jules"], check=True)
        subprocess.run(["git", "reset", "--hard", "origin/main"], check=True)
        subprocess.run(["git", "push", "--force-with-lease", "origin", "jules"], check=True)
        print("Jules branch updated to match main!")
    except subprocess.CalledProcessError as e:
        print(f"Error syncing jules to main: {e}", file=sys.stderr)
        raise


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

    # Forward sync: jules → main
    merge_jules_into_main()

    # Re-fetch after push so origin/main is up to date locally
    subprocess.run(["git", "fetch", "origin", "main", "jules"], check=True)

    # Reverse sync: main → jules (keep jules current for next session)
    sync_jules_to_main()


if __name__ == "__main__":
    main()
