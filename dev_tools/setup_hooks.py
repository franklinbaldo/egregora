#!/usr/bin/env python3
"""Cross-platform development environment setup script.

This script sets up the development environment including installing pre-commit hooks.
Works on Windows, Linux, and macOS.

Usage:
    uv run devtools/setup_hooks.py
    # or
    python devtools/setup_hooks.py
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, check=check, capture_output=False)


def check_uv_available() -> bool:
    """Check if uv is available."""
    try:
        subprocess.run(
            ["uv", "--version"],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def setup_dev_environment() -> int:
    """Set up the development environment."""
    # Check if we're in the project root
    project_root = Path(__file__).parent.parent
    if not (project_root / "pyproject.toml").exists():
        return 1

    # Check for uv
    if not check_uv_available():
        return 1

    try:
        # Sync dependencies with lint extras
        run_command(["uv", "sync", "--extra", "lint", "--extra", "test"])

        # Install pre-commit hooks
        run_command(["uv", "run", "pre-commit", "install"])

        return 0

    except subprocess.CalledProcessError:
        return 1


def main() -> int:
    """Entry point."""
    return setup_dev_environment()


if __name__ == "__main__":
    sys.exit(main())
