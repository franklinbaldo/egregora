#!/usr/bin/env python3
"""Check if there are pending high-priority tasks in TODO.ux.toml."""

import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def has_pending_high_priority_tasks(todo_path: Path) -> tuple[bool, int]:
    """
    Check if there are pending high-priority tasks.

    Returns:
        (has_pending, count) tuple
    """
    if not todo_path.exists():
        print(f"❌ TODO.ux.toml not found at {todo_path}", file=sys.stderr)
        return False, 0

    try:
        with open(todo_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        print(f"❌ Failed to parse TODO.ux.toml: {e}", file=sys.stderr)
        return False, 0

    if "tasks" not in data or "high_priority" not in data["tasks"]:
        print("❌ Missing tasks.high_priority section", file=sys.stderr)
        return False, 0

    pending_tasks = [
        task for task in data["tasks"]["high_priority"]
        if task.get("status") == "pending"
    ]

    return len(pending_tasks) > 0, len(pending_tasks)


def main() -> int:
    """
    Main entry point.

    Returns:
        0 if pending tasks exist (proceed with work)
        1 if no pending tasks (skip work)
    """
    repo_root = Path(__file__).parent.parent.parent
    todo_path = repo_root / "TODO.ux.toml"

    has_pending, count = has_pending_high_priority_tasks(todo_path)

    if has_pending:
        print(f"✅ Found {count} pending high-priority task(s)")
        return 0  # Success - has work to do
    else:
        print("ℹ️  No pending high-priority tasks")
        return 1  # Skip - no work to do


if __name__ == "__main__":
    sys.exit(main())
