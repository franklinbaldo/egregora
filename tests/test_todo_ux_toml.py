"""Tests for TODO.ux.toml validation."""

import sys
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / ".jules" / "scripts"))

from validate_todo import validate_todo_toml


def test_todo_ux_toml_exists():
    """Test that TODO.ux.toml exists."""
    repo_root = Path(__file__).parent.parent
    todo_path = repo_root / "TODO.ux.toml"
    assert todo_path.exists(), "TODO.ux.toml not found"


def test_todo_ux_toml_is_valid():
    """Test that TODO.ux.toml passes validation."""
    repo_root = Path(__file__).parent.parent
    todo_path = repo_root / "TODO.ux.toml"

    errors = validate_todo_toml(todo_path)

    if errors:
        error_msg = "TODO.ux.toml validation errors:\n" + "\n".join(f"  • {e}" for e in errors)
        pytest.fail(error_msg)


def test_todo_ux_toml_has_required_sections():
    """Test that TODO.ux.toml has all required sections."""
    import tomllib

    repo_root = Path(__file__).parent.parent
    todo_path = repo_root / "TODO.ux.toml"

    with open(todo_path, "rb") as f:
        data = tomllib.load(f)

    # Required top-level sections
    assert "metadata" in data, "Missing [metadata] section"
    assert "workflow" in data, "Missing [workflow] section"
    assert "tasks" in data, "Missing [tasks] section"
    assert "lighthouse" in data, "Missing [lighthouse] section"
    assert "references" in data, "Missing [references] section"

    # Required task categories
    assert "high_priority" in data["tasks"], "Missing tasks.high_priority"
    assert "medium_priority" in data["tasks"], "Missing tasks.medium_priority"
    assert "low_priority" in data["tasks"], "Missing tasks.low_priority"
    # Note: completed is optional (may be empty initially)


def test_todo_ux_toml_task_structure():
    """Test that all tasks have required fields."""
    import tomllib

    repo_root = Path(__file__).parent.parent
    todo_path = repo_root / "TODO.ux.toml"

    with open(todo_path, "rb") as f:
        data = tomllib.load(f)

    valid_statuses = {"pending", "in_progress", "completed"}

    for category in ["high_priority", "medium_priority", "low_priority"]:
        tasks = data["tasks"][category]
        for task in tasks:
            # Required fields
            assert "id" in task, f"Task missing 'id' in {category}"
            assert "title" in task, f"Task {task.get('id', 'UNKNOWN')} missing 'title'"
            assert "status" in task, f"Task {task['id']} missing 'status'"
            assert "category" in task, f"Task {task['id']} missing 'category'"
            assert "assignee" in task, f"Task {task['id']} missing 'assignee'"

            # Valid status
            assert task["status"] in valid_statuses, \
                f"Task {task['id']} has invalid status: {task['status']}"

            # Non-empty strings
            assert task["id"].strip(), f"Task has empty 'id' in {category}"
            assert task["title"].strip(), f"Task {task['id']} has empty 'title'"


def test_todo_ux_toml_no_duplicate_ids():
    """Test that all task IDs are unique."""
    import tomllib

    repo_root = Path(__file__).parent.parent
    todo_path = repo_root / "TODO.ux.toml"

    with open(todo_path, "rb") as f:
        data = tomllib.load(f)

    all_ids = []
    for category in ["high_priority", "medium_priority", "low_priority"]:
        for task in data["tasks"][category]:
            all_ids.append(task["id"])

    # Add completed tasks if section exists
    if "completed" in data["tasks"]:
        for task in data["tasks"]["completed"]:
            all_ids.append(task["id"])

    # Check for duplicates
    duplicates = [id for id in all_ids if all_ids.count(id) > 1]
    assert not duplicates, f"Duplicate task IDs found: {set(duplicates)}"


def test_todo_ux_toml_lighthouse_sections():
    """Test that lighthouse sections have required metrics."""
    import tomllib

    repo_root = Path(__file__).parent.parent
    todo_path = repo_root / "TODO.ux.toml"

    with open(todo_path, "rb") as f:
        data = tomllib.load(f)

    metrics = ["performance", "accessibility", "best_practices", "seo"]

    for section in ["baseline", "target", "current"]:
        assert section in data["lighthouse"], f"Missing lighthouse.{section}"
        for metric in metrics:
            assert metric in data["lighthouse"][section], \
                f"Missing lighthouse.{section}.{metric}"


def test_todo_ux_toml_references_structure():
    """Test that references have required fields."""
    import tomllib

    repo_root = Path(__file__).parent.parent
    todo_path = repo_root / "TODO.ux.toml"

    with open(todo_path, "rb") as f:
        data = tomllib.load(f)

    assert isinstance(data["references"], list), "references must be a list"

    for ref in data["references"]:
        assert "name" in ref, "Reference missing 'name'"
        assert "url" in ref, "Reference missing 'url'"
        assert "strength" in ref, "Reference missing 'strength'"
