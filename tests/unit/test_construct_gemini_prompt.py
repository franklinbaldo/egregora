"""Tests for Gemini prompt construction script."""

import os
from pathlib import Path

import pytest


@pytest.fixture
def temp_files(tmp_path: Path) -> dict[str, Path]:
    """Create temporary files for testing."""
    # Create template
    template_path = tmp_path / "template.md"
    template_path.write_text(
        "# PR Review for {{REPOSITORY}}\n"
        "PR #{{PR_NUMBER}}: {{PR_TITLE}}\n"
        "Author: {{PR_AUTHOR}}\n"
        "{{USER_INSTRUCTIONS}}\n"
        "## Body\n{{PR_BODY}}\n"
        "## Commits\n{{COMMITS}}\n"
        "## Diff\n{{DIFF}}\n"
        "## Code Standards\n{{CLAUDE_MD}}"
    )

    # Create input files
    diff_path = tmp_path / "diff.txt"
    diff_path.write_text("+++ added line\n--- removed line")

    claude_md_path = tmp_path / "CLAUDE.md"
    claude_md_path.write_text("# Code Standards\nUse ruff for linting.")

    commits_path = tmp_path / "commits.txt"
    commits_path.write_text("abc123 fix: bug fix\ndef456 feat: new feature")

    output_path = tmp_path / "output.txt"

    return {
        "template": template_path,
        "diff": diff_path,
        "claude_md": claude_md_path,
        "commits": commits_path,
        "output": output_path,
        "tmp": tmp_path,
    }


def test_construct_prompt_with_all_data(temp_files: dict[str, Path]) -> None:
    """Test prompt construction with all data provided."""
    import subprocess

    env = {
        **os.environ,
        "TEMPLATE_PATH": str(temp_files["template"]),
        "DIFF_PATH": str(temp_files["diff"]),
        "CLAUDE_MD_PATH": str(temp_files["claude_md"]),
        "COMMITS_PATH": str(temp_files["commits"]),
        "OUTPUT_PATH": str(temp_files["output"]),
        "REPOSITORY": "owner/repo",
        "PR_NUMBER": "123",
        "PR_TITLE": "Fix bug",
        "PR_AUTHOR": "alice",
        "PR_BODY": "This fixes the bug",
        "TRIGGER_MODE": "manual",
        "USER_INSTRUCTIONS": "Check security",
    }

    result = subprocess.run(
        ["python3", ".github/scripts/construct_gemini_prompt.py"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert temp_files["output"].exists()

    output = temp_files["output"].read_text()
    assert "# PR Review for owner/repo" in output
    assert "PR #123: Fix bug" in output
    assert "Author: alice" in output
    assert "**User Request:** Check security" in output
    assert "This fixes the bug" in output
    assert "abc123 fix: bug fix" in output
    assert "+++ added line" in output
    assert "# Code Standards" in output


def test_construct_prompt_without_optional_data(temp_files: dict[str, Path]) -> None:
    """Test prompt construction without optional data."""
    import subprocess

    # Remove optional files
    temp_files["diff"].unlink()
    temp_files["commits"].unlink()

    env = {
        **os.environ,
        "TEMPLATE_PATH": str(temp_files["template"]),
        "DIFF_PATH": str(temp_files["diff"]),
        "CLAUDE_MD_PATH": str(temp_files["claude_md"]),
        "COMMITS_PATH": str(temp_files["commits"]),
        "OUTPUT_PATH": str(temp_files["output"]),
        "REPOSITORY": "owner/repo",
        "PR_NUMBER": "123",
        "PR_TITLE": "Fix bug",
        "PR_AUTHOR": "alice",
        "PR_BODY": "",
        "TRIGGER_MODE": "automatic",
        "USER_INSTRUCTIONS": "",
    }

    result = subprocess.run(
        ["python3", ".github/scripts/construct_gemini_prompt.py"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = temp_files["output"].read_text()

    # Should have defaults for missing data
    assert "(No diff available)" in output
    assert "(No commits available)" in output
    assert "(No description provided)" in output
    # User instructions should be empty (no text added)
    assert "**User Request:**" not in output


def test_construct_prompt_missing_template(temp_files: dict[str, Path]) -> None:
    """Test error handling when template is missing."""
    import subprocess

    env = {
        **os.environ,
        "TEMPLATE_PATH": str(temp_files["tmp"] / "missing.md"),
        "DIFF_PATH": str(temp_files["diff"]),
        "CLAUDE_MD_PATH": str(temp_files["claude_md"]),
        "COMMITS_PATH": str(temp_files["commits"]),
        "OUTPUT_PATH": str(temp_files["output"]),
        "REPOSITORY": "owner/repo",
        "PR_NUMBER": "123",
        "PR_TITLE": "Fix bug",
        "PR_AUTHOR": "alice",
    }

    result = subprocess.run(
        ["python3", ".github/scripts/construct_gemini_prompt.py"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Required file not found" in result.stderr


def test_construct_prompt_invalid_template_syntax(temp_files: dict[str, Path]) -> None:
    """Test error handling with invalid Jinja2 syntax."""
    import subprocess

    # Write invalid template
    temp_files["template"].write_text("{{UNDEFINED_VAR}}")

    env = {
        **os.environ,
        "TEMPLATE_PATH": str(temp_files["template"]),
        "DIFF_PATH": str(temp_files["diff"]),
        "CLAUDE_MD_PATH": str(temp_files["claude_md"]),
        "COMMITS_PATH": str(temp_files["commits"]),
        "OUTPUT_PATH": str(temp_files["output"]),
        "REPOSITORY": "owner/repo",
        "PR_NUMBER": "123",
        "PR_TITLE": "Fix bug",
        "PR_AUTHOR": "alice",
    }

    result = subprocess.run(
        ["python3", ".github/scripts/construct_gemini_prompt.py"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error rendering template" in result.stderr


def test_construct_prompt_creates_output_directory(temp_files: dict[str, Path]) -> None:
    """Test that output directory is created if it doesn't exist."""
    import subprocess

    output_path = temp_files["tmp"] / "nested" / "dir" / "output.txt"

    env = {
        **os.environ,
        "TEMPLATE_PATH": str(temp_files["template"]),
        "DIFF_PATH": str(temp_files["diff"]),
        "CLAUDE_MD_PATH": str(temp_files["claude_md"]),
        "COMMITS_PATH": str(temp_files["commits"]),
        "OUTPUT_PATH": str(output_path),
        "REPOSITORY": "owner/repo",
        "PR_NUMBER": "123",
        "PR_TITLE": "Fix bug",
        "PR_AUTHOR": "alice",
    }

    result = subprocess.run(
        ["python3", ".github/scripts/construct_gemini_prompt.py"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert output_path.exists()
    assert output_path.parent.exists()
