#!/usr/bin/env python3
"""Sync jules branch into main if clean (no conflicts)."""

import subprocess
import sys

# Add .team to path for imports
sys.path.insert(0, ".team")

from repo.scheduler_managers import BranchManager


def main() -> None:
    # Ensure we have latest refs
    subprocess.run(["git", "fetch", "origin", "main", "jules"], check=True)

    # Use BranchManager to handle the merge
    mgr = BranchManager()
    mgr.merge_jules_into_main_direct()


if __name__ == "__main__":
    main()
