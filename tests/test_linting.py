"""Ensure the repository stays Ruff-clean via pytest."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("ruff")

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_ruff(*paths: str) -> subprocess.CompletedProcess[str]:
    """Execute ``ruff check`` for the given paths and capture output."""

    return subprocess.run(
        [sys.executable, "-m", "ruff", "check", *paths],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_repository_is_ruff_clean() -> None:
    """Fail the test suite when Ruff linting finds violations."""

    result = _run_ruff("src", "tests")
    if result.returncode != 0:
        pytest.fail(
            "Ruff linting failures detected:\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
