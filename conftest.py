"""Root conftest.py for pytest configuration and hooks.

This file provides session-level fixtures and hooks that apply to all tests.
"""

from __future__ import annotations

import os
import subprocess


def pytest_sessionstart(session):
    """Hook that runs before the test session starts.

    Auto-formats code with ruff before running tests (DEFAULT behavior).
    Set PYTEST_FORMAT=0 to skip formatting for faster test runs.

    Usage:
        # Format before running tests (default)
        pytest

        # Skip formatting for faster runs
        PYTEST_FORMAT=0 pytest
    """
    if os.getenv("PYTEST_FORMAT") != "0":
        print("\n🎨 Auto-formatting code with ruff before tests...")
        result = subprocess.run(
            ["uv", "run", "ruff", "format", "src", "tests", "dev_tools"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            print("✅ Code formatting complete")
        else:
            print(f"⚠️  Formatting had issues:\n{result.stderr}")
