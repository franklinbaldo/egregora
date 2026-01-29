#!/usr/bin/env python3
"""
Checks that the root directory only contains allowed files and directories.
This ensures the repository root remains clean and focused on essential project files.
"""

import os
import subprocess
import sys
from pathlib import Path

# Allowlist of files and directories that are permitted in the root
ALLOWED_ITEMS = {
    # Directories
    "src",
    "tests",
    "docs",
    "scripts",
    "notes",
    "artifacts",
    ".git",
    ".github",
    ".venv",
    ".ruff_cache",
    ".pytest_cache",
    ".mypy_cache",
    ".uv",
    ".team",
    ".agent",
    ".claude",
    # Files
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "LICENSE",
    "SECURITY.md",
    "pyproject.toml",
    "uv.lock",
    ".pre-commit-config.yaml",
    ".gitignore",
    ".python-version",
    ".repomixignore",
    "mkdocs.yml",
    "renovate.json",
}


def get_suggestion(filename: str) -> str:
    """Returns a suggested directory for a given filename."""
    name_lower = filename.lower()

    # Artifacts / Logs / Diffs / Reports
    if any(
        x in name_lower
        for x in ["log", "diff", "report", "output", "zip", "json", "txt", "xml", "coverage", "dump"]
    ) and not name_lower.endswith(".md"):  # exclude markdown reports if they are more like notes
        if "test" in name_lower or "report" in name_lower or "log" in name_lower:
            return "artifacts/"
        return "artifacts/"

    # Notes / Plans / Documentation
    if name_lower.endswith(".md") or any(
        x in name_lower for x in ["plan", "todo", "idea", "draft", "analysis", "review"]
    ):
        return "notes/"

    # Scripts
    if name_lower.endswith((".py", ".sh")):
        return "scripts/"

    # Default fallback
    return "notes/ (if text) or artifacts/ (if generated data)"


def _is_git_ignored(root: Path, item: str) -> bool:
    """Return True if Git ignores the path."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", item],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return result.returncode == 0


def main():
    # Force UTF-8 for stdout/stderr to avoid UnicodeEncodeError on Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    root = Path(".")
    current_items = set(os.listdir(root))

    # Filter out items that are not in the allowed list
    unauthorized = []

    for item in current_items:
        if item in ALLOWED_ITEMS:
            continue

        # Ignore some common transient/IDE files/dirs if they happen to exist locally
        if item.startswith((".idea", ".vscode")) or item.endswith(".egg-info") or item == ".DS_Store":
            continue
        if _is_git_ignored(root, item):
            continue

        unauthorized.append(item)

    if unauthorized:
        print("❌ Root directory check failed!")
        print("The repository root should only contain essential project files.")
        print("Found the following unauthorized items:\n")

        for item in sorted(unauthorized):
            suggestion = get_suggestion(item)
            print(f"  - {item:<30} -> Move to: {suggestion}")

        print("\nALLOWED ROOT ITEMS:")
        print(", ".join(sorted(ALLOWED_ITEMS)))
        sys.exit(1)

    print("✅ Root directory check passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
