"""Tests for check_root_structure pre-commit hook helpers."""

import sys
from pathlib import Path

# Add scripts/dev_tools to path
sys.path.insert(0, str(Path(__file__).parents[3] / "scripts" / "dev_tools"))

from check_root_structure import _is_git_ignored


def test_is_git_ignored_returns_true_when_git_ignores(monkeypatch) -> None:
    """Git ignored paths should return True."""
    calls = []

    def fake_run(cmd, check, stdout, stderr):
        calls.append(cmd)

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("check_root_structure.subprocess.run", fake_run)

    assert _is_git_ignored(Path("/repo"), ".egregora") is True
    # Handle both forward and backward slashes for Windows compatibility
    assert [cmd[2].replace("\\", "/") for cmd in calls] == ["/repo"]


def test_is_git_ignored_returns_false_when_not_ignored(monkeypatch) -> None:
    """Non-ignored paths should return False."""

    def fake_run(cmd, check, stdout, stderr):
        class Result:
            returncode = 1

        return Result()

    monkeypatch.setattr("check_root_structure.subprocess.run", fake_run)

    assert _is_git_ignored(Path("/repo"), "README.md") is False


def test_is_git_ignored_returns_false_on_oserror(monkeypatch) -> None:
    """Failures to execute git should return False."""

    def fake_run(cmd, check, stdout, stderr):
        raise OSError("git missing")

    monkeypatch.setattr("check_root_structure.subprocess.run", fake_run)

    assert _is_git_ignored(Path("/repo"), ".egregora") is False
