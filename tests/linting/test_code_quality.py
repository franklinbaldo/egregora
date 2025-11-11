"""Code quality tests integrated with pytest.

These tests run code quality checks (vulture, radon, bandit) as part of the
test suite. They can be run with:

    pytest tests/linting/test_code_quality.py        # Run all quality tests
    pytest -m quality                                 # Run all quality tests
    pytest -m complexity                              # Run only complexity tests
    pytest -m deadcode                                # Run only dead code tests
    pytest -m security                                # Run only security tests

Skip quality tests with:
    pytest -m "not quality"                           # Skip all quality tests
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=PROJECT_ROOT)
    return result.returncode, result.stdout, result.stderr


@pytest.mark.quality
@pytest.mark.complexity
def test_no_high_complexity_functions():
    """Test that no functions have D or F grade complexity (>= 21)."""
    exit_code, stdout, stderr = run_command(
        ["uv", "run", "radon", "cc", "src/egregora", "-s", "-n", "D", "--total-average"]
    )

    # Radon returns 0 even with D+ functions, so check output
    assert exit_code == 0, f"Radon failed: {stderr}"

    # Check for D or F grade functions
    high_complexity = [line for line in stdout.split("\n") if " - D " in line or " - F " in line]

    if high_complexity:
        functions = "\n".join(high_complexity)
        pytest.fail(
            f"Found {len(high_complexity)} high complexity functions (D or F grade):\n{functions}\n\n"
            f"Please refactor these functions to reduce complexity below 21.\n"
            f"See REFACTORING_FINAL_SUMMARY.md for refactoring patterns."
        )


@pytest.mark.quality
@pytest.mark.complexity
def test_average_complexity_acceptable():
    """Test that average complexity is acceptable (< 10)."""
    exit_code, stdout, stderr = run_command(
        ["uv", "run", "radon", "cc", "src/egregora", "-s", "--total-average"]
    )

    assert exit_code == 0, f"Radon failed: {stderr}"

    # Extract average complexity from output
    for line in stdout.split("\n"):
        if "Average complexity:" in line:
            # Extract the number after "Average complexity: X ("
            try:
                avg = float(line.split("Average complexity: ")[1].split(" ")[0])
                assert avg < 10, (
                    f"Average complexity is {avg:.2f}, which is too high (threshold: 10.0)\n"
                    f"Consider refactoring complex functions."
                )
            except (IndexError, ValueError):
                pytest.skip("Could not parse average complexity from radon output")


@pytest.mark.quality
@pytest.mark.deadcode
def test_no_dead_code():
    """Test that vulture finds no dead code (with 80% confidence threshold)."""
    exit_code, stdout, _stderr = run_command(
        ["uv", "run", "vulture", "src", "tests", "--min-confidence", "80"]
    )

    # Vulture returns non-zero if it finds dead code
    if exit_code != 0:
        pytest.fail(
            f"Vulture found potential dead code:\n{stdout}\n\n"
            f"If these are false positives, consider:\n"
            f"1. Adding them to a vulture whitelist file\n"
            f"2. Using them (if they're meant to be used)\n"
            f"3. Removing them (if they're truly dead code)"
        )


@pytest.mark.quality
@pytest.mark.security
def test_no_security_issues():
    """Test that bandit finds no medium+ severity security issues."""
    exit_code, stdout, _stderr = run_command(
        ["uv", "run", "bandit", "-r", "src", "--severity-level", "medium", "-q"]
    )

    # Bandit returns non-zero if it finds issues
    if exit_code != 0:
        # Parse output to count real issues (not just nosec suppressions)
        lines = stdout.split("\n")
        issue_lines = [line for line in lines if "Issue:" in line or "Severity:" in line]

        if issue_lines:
            pytest.fail(
                f"Bandit found security issues:\n{stdout}\n\n"
                f"Please review and fix these issues, or add # nosec comments with justification."
            )


@pytest.mark.quality
def test_linting_passes():
    """Test that ruff linting passes."""
    exit_code, stdout, _stderr = run_command(["uv", "run", "ruff", "check", ".", "--output-format=concise"])

    if exit_code != 0:
        pytest.fail(f"Ruff linting failed:\n{stdout}\n\nRun 'uv run ruff check . --fix' to auto-fix issues.")


@pytest.mark.quality
@pytest.mark.slow
def test_dependencies_clean():
    """Test that deptry finds no major dependency issues.

    Note: This test allows some false positives (internal imports, dev tools)
    but fails on significant issues.
    """
    exit_code, stdout, _stderr = run_command(["uv", "run", "deptry", "."])

    if exit_code != 0:
        # Count real issues (not internal 'egregora' imports)
        lines = stdout.split("\n")
        real_issues = [
            line
            for line in lines
            if "DEP" in line and "'egregora' imported" not in line and "DEP002" not in line  # Unused deps
        ]

        # Allow up to 10 false positives (dev tools, test fixtures, etc.)
        if len(real_issues) > 10:
            pytest.fail(
                f"Deptry found {len(real_issues)} dependency issues:\n{stdout}\n\n"
                f"Please review and fix significant dependency problems."
            )


# Convenience test collection functions
def pytest_collection_modifyitems(config, items):
    """Add quality marker to all tests in this module."""
    for item in items:
        if "test_code_quality" in str(item.fspath):
            item.add_marker(pytest.mark.quality)
