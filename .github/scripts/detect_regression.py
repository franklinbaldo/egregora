#!/usr/bin/env python3
"""Detect code regressions by comparing file hashes with recent git history.

This script identifies when files being committed match earlier versions,
which could indicate accidental reversions of recent work.

Reduces false positives by:
- Using AST comparison for Python files (ignores formatting)
- Skipping commits with formatting-related messages
- Filtering out whitespace-only changes
"""
import ast
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple


def get_file_hash(commit: str, file: str) -> Optional[str]:
    """Get git hash of file content at specific commit."""
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{file}"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Hash the content
        hash_result = subprocess.run(
            ["git", "hash-object", "--stdin"],
            input=result.stdout,
            capture_output=True,
            text=True,
            check=True,
        )
        return hash_result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_staged_file_hash(file: str) -> Optional[str]:
    """Get hash of staged file content."""
    try:
        result = subprocess.run(
            ["git", "hash-object", file],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_staged_files() -> List[str]:
    """Get list of files staged for commit."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def is_formatting_commit(message: str) -> bool:
    """Check if commit message indicates formatting-only changes."""
    formatting_keywords = [
        "ruff format",
        "black format",
        "formatting",
        "chore: format",
        "style:",
        "apply ruff",
        "apply black",
        "code style",
        "linting fixes",
        "pre-commit",
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in formatting_keywords)


def normalize_python_code(code: str) -> Optional[str]:
    """Parse Python code to AST and dump it (ignores formatting).

    Returns normalized AST dump, or None if parsing fails.
    """
    try:
        tree = ast.parse(code)
        return ast.dump(tree, indent=None)
    except SyntaxError:
        return None


def get_file_content(commit: str, file: str) -> Optional[str]:
    """Get file content at specific commit."""
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:{file}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None


def get_staged_file_content(file: str) -> Optional[str]:
    """Get staged file content."""
    try:
        with open(file, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def files_semantically_equal(file1_content: str, file2_content: str, filepath: str) -> bool:
    """Compare files semantically, ignoring formatting differences.

    For Python files: uses AST comparison
    For other files: uses normalized whitespace comparison
    """
    if filepath.endswith(".py"):
        # Python: compare ASTs
        ast1 = normalize_python_code(file1_content)
        ast2 = normalize_python_code(file2_content)

        if ast1 is None or ast2 is None:
            # Couldn't parse, fall back to exact match
            return file1_content == file2_content

        return ast1 == ast2
    else:
        # Other files: normalize whitespace and compare
        norm1 = " ".join(file1_content.split())
        norm2 = " ".join(file2_content.split())
        return norm1 == norm2


def find_regression(
    file: str, staged_hash: str, lookback_days: int = 30, semantic: bool = True
) -> Optional[Tuple[str, str, str, str]]:
    """Find if staged file matches recent commit (potential regression).

    Args:
        file: File path to check
        staged_hash: Git hash of staged file content
        lookback_days: How far back to check
        semantic: If True, use semantic comparison (ignores formatting)

    Returns:
        Tuple of (commit_hash, date, author, message) if regression found, None otherwise
    """
    since_date = (datetime.now() - timedelta(days=lookback_days)).isoformat()

    # Get recent history for this file
    result = subprocess.run(
        [
            "git",
            "log",
            "--all",
            f"--since={since_date}",
            "--pretty=format:%H|%ci|%an|%s",
            "--",
            file,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    # Get staged content for semantic comparison
    staged_content = get_staged_file_content(file) if semantic else None

    for line in result.stdout.strip().split("\n"):
        if not line:
            continue

        parts = line.split("|", 3)
        if len(parts) != 4:
            continue

        commit, date, author, message = parts

        # Skip formatting-only commits
        if is_formatting_commit(message):
            continue

        # First try hash comparison (fast path)
        old_hash = get_file_hash(commit, file)
        if old_hash == staged_hash:
            # Exact match found - check if it's just formatting
            if semantic and staged_content:
                old_content = get_file_content(commit, file)
                if old_content and files_semantically_equal(staged_content, old_content, file):
                    # Content is semantically identical, likely just formatting
                    continue

            # Found a real regression!
            return (commit, date, author, message)

    return None


def main(lookback_days: int = 30, interactive: bool = True, semantic: bool = True) -> int:
    """Main regression detection logic.

    Args:
        lookback_days: How far back to check for regressions
        interactive: If True, prompt user for confirmation
        semantic: If True, use semantic comparison (ignores formatting)

    Returns:
        0 if no regressions or user confirmed, 1 if regressions found and rejected
    """
    staged_files = get_staged_files()
    if not staged_files:
        return 0

    regressions = []

    for file in staged_files:
        # Skip non-code files
        if any(
            file.endswith(ext)
            for ext in [".md", ".txt", ".json", ".csv", ".lock", ".gitignore"]
        ):
            continue

        staged_hash = get_staged_file_hash(file)
        if not staged_hash:
            continue

        regression = find_regression(file, staged_hash, lookback_days, semantic=semantic)
        if regression:
            regressions.append((file, regression))

    if not regressions:
        return 0

    # Print warning
    print("⚠️  WARNING: Potential code regression detected!\n")
    print("The following files match earlier commits:\n")

    for file, (commit, date, author, message) in regressions:
        print(f"📄 {file}")
        print(f"   Matches commit: {commit[:7]}")
        print(f"   From: {date}")
        print(f"   Author: {author}")
        print(f'   Message: "{message}"')
        print()

    print("❓ This could be:")
    print("   1. ✅ Intentional revert (OK)")
    print("   2. ❌ Accidental regression (BAD)")
    print()

    if not interactive:
        # Non-interactive mode (CI): just warn and fail
        print("❌ Regression check failed in non-interactive mode")
        return 1

    # Interactive mode: ask user
    try:
        response = input("Continue with commit anyway? (y/N): ").strip().lower()
        if response in ["y", "yes"]:
            print("✅ Proceeding with commit...")
            return 0
        else:
            print("❌ Commit aborted")
            return 1
    except (EOFError, KeyboardInterrupt):
        print("\n❌ Commit aborted")
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Detect code regressions in git commits (with smart filtering for formatting changes)"
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=30,
        help="Number of days to look back for regressions (default: 30)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode (fail without prompting)",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Disable semantic comparison (exact hash matching only, more false positives)",
    )
    args = parser.parse_args()

    sys.exit(
        main(
            lookback_days=args.lookback_days,
            interactive=not args.non_interactive,
            semantic=not args.no_semantic,
        )
    )
