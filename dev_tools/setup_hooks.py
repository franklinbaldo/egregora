#!/usr/bin/env python3
"""Cross-platform development environment setup script.

This script sets up the development environment including installing pre-commit hooks.
Works on Windows, Linux, and macOS.

Usage:
    uv run dev_tools/setup_hooks.py
    # or
    python dev_tools/setup_hooks.py
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> None:
    """Run a command and print status."""
    print(f"🔧 Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=check, capture_output=False)


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
    print("🚀 Setting up development environment...\n")

    # Check if we're in the project root
    project_root = Path(__file__).parent.parent
    if not (project_root / "pyproject.toml").exists():
        print("❌ Error: pyproject.toml not found. Are you in the project root?")
        return 1

    # Check for uv
    if not check_uv_available():
        print("❌ Error: uv is not installed or not in PATH")
        print("📦 Install it from: https://github.com/astral-sh/uv")
        return 1

    try:
        # Sync dependencies with lint extras
        print("📦 Installing dependencies with lint extras...")
        run_command(["uv", "sync", "--extra", "lint", "--extra", "test"])

        # Install pre-commit hooks
        print("\n🔧 Installing pre-commit hooks...")
        run_command(["uv", "run", "pre-commit", "install"])

        print("\n✅ Development environment ready!")
        print("💡 Pre-commit hooks will now run automatically on git commit")
        print("\nAvailable commands:")
        print("  uv run pytest                    # Run tests")
        print("  uv run pre-commit run --all-files  # Run all linting checks")
        print("  uv run ruff format .             # Format code")
        print("  uv run ruff check --fix .        # Lint and auto-fix")

        return 0

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error during setup: {e}")
        print(f"Command that failed: {' '.join(e.cmd)}")
        print(f"Return code: {e.returncode}")
        return 1


def main() -> int:
    """Entry point."""
    return setup_dev_environment()


if __name__ == "__main__":
    sys.exit(main())
