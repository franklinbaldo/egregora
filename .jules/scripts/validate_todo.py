#!/usr/bin/env python3
"""Validate TODO.ux.toml structure and content."""

import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def validate_todo_toml(todo_path: Path) -> list[str]:
    """
    Validate TODO.ux.toml structure and return list of errors.

    Returns:
        List of error messages (empty list if valid)
    """
    errors = []

    if not todo_path.exists():
        return [f"TODO.ux.toml not found at {todo_path}"]

    try:
        with open(todo_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        return [f"Failed to parse TOML: {e}"]

    # Validate required top-level sections
    required_sections = ["metadata", "workflow", "lighthouse", "references"]
    for section in required_sections:
        if section not in data:
            errors.append(f"Missing required section: [{section}]")

    # Validate metadata
    if "metadata" in data:
        required_meta = ["version", "last_updated", "vision_doc", "template_location"]
        for field in required_meta:
            if field not in data["metadata"]:
                errors.append(f"Missing metadata.{field}")

    # Validate tasks structure
    if "tasks" not in data:
        errors.append("Missing [tasks] section")
    else:
        tasks = data["tasks"]
        required_task_categories = ["high_priority", "medium_priority", "low_priority"]
        for category in required_task_categories:
            if category not in tasks:
                errors.append(f"Missing tasks.{category} section")
            elif not isinstance(tasks[category], list):
                errors.append(f"tasks.{category} must be a list (array of tables)")

        # Completed is optional (may be empty initially)
        if "completed" in tasks and not isinstance(tasks["completed"], list):
            errors.append("tasks.completed must be a list (array of tables)")

    # Validate individual task structure
    valid_statuses = {"pending", "in_progress", "completed"}
    valid_assignees = {"curator", "forge", "both"}

    # Check all categories that exist
    categories_to_check = ["high_priority", "medium_priority", "low_priority"]
    if "tasks" in data and "completed" in data["tasks"]:
        categories_to_check.append("completed")

    for category in categories_to_check:
        if "tasks" in data and category in data["tasks"]:
            for i, task in enumerate(data["tasks"][category]):
                task_path = f"tasks.{category}[{i}]"

                # Required fields for all tasks
                if "id" not in task:
                    errors.append(f"{task_path}: missing 'id' field")
                elif not isinstance(task["id"], str) or not task["id"]:
                    errors.append(f"{task_path}: 'id' must be non-empty string")

                if "title" not in task:
                    errors.append(f"{task_path}: missing 'title' field")

                if "status" not in task:
                    errors.append(f"{task_path}: missing 'status' field")
                elif task["status"] not in valid_statuses:
                    errors.append(
                        f"{task_path}: invalid status '{task['status']}'. "
                        f"Must be one of: {', '.join(sorted(valid_statuses))}"
                    )

                # Validate category-specific requirements
                if category == "completed":
                    if task.get("status") != "completed":
                        errors.append(f"{task_path}: completed tasks must have status='completed'")
                    if "completed_date" not in task:
                        errors.append(f"{task_path}: completed tasks must have 'completed_date'")
                else:
                    # Non-completed tasks should have assignee and category
                    if "assignee" not in task:
                        errors.append(f"{task_path}: missing 'assignee' field")
                    elif task["assignee"] not in valid_assignees:
                        errors.append(
                            f"{task_path}: invalid assignee '{task['assignee']}'. "
                            f"Must be one of: {', '.join(sorted(valid_assignees))}"
                        )

                    if "category" not in task:
                        errors.append(f"{task_path}: missing 'category' field")

    # Validate lighthouse sections
    if "lighthouse" in data:
        for section in ["baseline", "target", "current"]:
            if section not in data["lighthouse"]:
                errors.append(f"Missing lighthouse.{section} section")
            else:
                metrics = ["performance", "accessibility", "best_practices", "seo"]
                for metric in metrics:
                    if metric not in data["lighthouse"][section]:
                        errors.append(f"Missing lighthouse.{section}.{metric}")

    # Validate references
    if "references" in data:
        if not isinstance(data["references"], list):
            errors.append("references must be a list (array of tables)")
        else:
            for i, ref in enumerate(data["references"]):
                if "name" not in ref:
                    errors.append(f"references[{i}]: missing 'name'")
                if "url" not in ref:
                    errors.append(f"references[{i}]: missing 'url'")
                if "strength" not in ref:
                    errors.append(f"references[{i}]: missing 'strength'")

    return errors


def main() -> int:
    """Main entry point."""
    repo_root = Path(__file__).parent.parent.parent
    todo_path = repo_root / "TODO.ux.toml"

    errors = validate_todo_toml(todo_path)

    if errors:
        print("❌ TODO.ux.toml validation failed:\n")
        for error in errors:
            print(f"  • {error}")
        return 1
    else:
        print("✅ TODO.ux.toml is valid")
        return 0


if __name__ == "__main__":
    sys.exit(main())
