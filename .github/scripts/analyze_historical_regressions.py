#!/usr/bin/env python3
"""Analyze historical commits to find regressions.

This script checks the last N commits to identify where files were
reverted to earlier states (potential regressions).

Reduces false positives by filtering out formatting-only commits.
"""
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_file_hash(commit: str, file: str) -> Optional[str]:
    """Get git hash of file content at specific commit."""
    try:
        # Get file content in binary mode
        result = subprocess.run(
            ["git", "show", f"{commit}:{file}"],
            capture_output=True,
            check=True,
        )
        # Hash the binary content
        hash_result = subprocess.run(
            ["git", "hash-object", "--stdin"],
            input=result.stdout,
            capture_output=True,
            check=True,
        )
        # Decode only the hash output
        return hash_result.stdout.decode('utf-8').strip()
    except (subprocess.CalledProcessError, UnicodeDecodeError):
        return None


def get_commit_info(commit: str) -> Tuple[str, str, str, str]:
    """Get commit metadata."""
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=format:%ci|%an|%s", commit],
        capture_output=True,
        text=True,
        check=True,
    )
    date, author, message = result.stdout.split("|", 2)
    return (commit[:7], date, author, message)


def get_changed_files(commit: str) -> List[str]:
    """Get files changed in a commit."""
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
        capture_output=True,
        text=True,
        check=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def get_recent_commits(limit: int = 1000) -> List[str]:
    """Get list of recent commit hashes."""
    result = subprocess.run(
        ["git", "log", f"-{limit}", "--pretty=format:%H"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip().split("\n")


def should_skip_file(file: str) -> bool:
    """Check if file should be skipped."""
    skip_extensions = [".md", ".txt", ".json", ".csv", ".lock", ".gitignore", ".yaml", ".yml"]
    skip_patterns = [".team/schedule.csv", ".team/tools_use.csv", ".team/logs/"]

    # Skip by extension
    if any(file.endswith(ext) for ext in skip_extensions):
        return True

    # Skip by pattern
    if any(pattern in file for pattern in skip_patterns):
        return True

    return False


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
        "modernize code with ruff",
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in formatting_keywords)


def analyze_commit_for_regressions(
    commit: str,
    commit_index: int,
    all_commits: List[str],
    file_history: Dict[str, List[Tuple[int, str, str]]],
    filter_formatting: bool = True,
) -> List[Dict]:
    """Analyze a single commit for regressions.

    Args:
        commit: Commit hash to analyze
        commit_index: Index of this commit in all_commits list
        all_commits: List of all commits being analyzed
        file_history: Dict mapping file -> list of (index, hash, commit) tuples
        filter_formatting: If True, skip formatting-only commits

    Returns:
        List of regression dicts
    """
    regressions = []

    # Get commit message to check if it's formatting-only
    _, _, _, commit_message = get_commit_info(commit)
    if filter_formatting and is_formatting_commit(commit_message):
        # Still track file history, but don't report as regression
        changed_files = get_changed_files(commit)
        for file in changed_files:
            if should_skip_file(file):
                continue
            current_hash = get_file_hash(commit, file)
            if current_hash:
                if file not in file_history:
                    file_history[file] = []
                file_history[file].append((commit_index, current_hash, commit))
        return []

    changed_files = get_changed_files(commit)

    for file in changed_files:
        if should_skip_file(file):
            continue

        current_hash = get_file_hash(commit, file)
        if not current_hash:
            continue

        # Check if this hash appeared earlier in history
        if file in file_history:
            for earlier_index, earlier_hash, earlier_commit in file_history[file]:
                if earlier_index < commit_index and earlier_hash == current_hash:
                    # Found a potential regression
                    early_short, early_date, early_author, early_msg = get_commit_info(earlier_commit)

                    # Skip if the earlier commit was also formatting-only
                    if filter_formatting and is_formatting_commit(early_msg):
                        continue

                    # Real regression! Current commit reverts to earlier state
                    curr_short, curr_date, curr_author, curr_msg = get_commit_info(commit)

                    regressions.append({
                        "file": file,
                        "current_commit": curr_short,
                        "current_date": curr_date,
                        "current_author": curr_author,
                        "current_message": curr_msg,
                        "original_commit": early_short,
                        "original_date": early_date,
                        "original_author": early_author,
                        "original_message": early_msg,
                        "commits_between": commit_index - earlier_index,
                    })
                    break  # Only report first match

        # Add this commit's hash to file history
        if file not in file_history:
            file_history[file] = []
        file_history[file].append((commit_index, current_hash, commit))

    return regressions


def main(limit: int = 1000, verbose: bool = False, filter_formatting: bool = True):
    """Analyze recent commits for regressions."""
    mode = "with formatting filter" if filter_formatting else "without formatting filter"
    print(f"🔍 Analyzing last {limit} commits for regressions ({mode})...\n")

    # Get commits (newest first)
    commits = get_recent_commits(limit)
    total = len(commits)

    print(f"Found {total} commits to analyze")
    print("This may take a few minutes...\n")

    # Track file hashes across commits
    file_history: Dict[str, List[Tuple[int, str, str]]] = defaultdict(list)
    all_regressions = []

    # Process commits (oldest to newest for proper history tracking)
    for i, commit in enumerate(reversed(commits)):
        if verbose and i % 100 == 0:
            print(f"Progress: {i}/{total} commits analyzed...")

        regressions = analyze_commit_for_regressions(
            commit, i, commits, file_history, filter_formatting=filter_formatting
        )
        all_regressions.extend(regressions)

    # Report findings
    print("\n" + "=" * 80)
    print(f"📊 REGRESSION ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Commits analyzed: {total}")
    print(f"Regressions found: {len(all_regressions)}\n")

    if not all_regressions:
        print("✅ No regressions detected in the analyzed commits!")
        return 0

    # Group by file
    by_file = defaultdict(list)
    for reg in all_regressions:
        by_file[reg["file"]].append(reg)

    print(f"Files affected: {len(by_file)}\n")
    print("=" * 80)
    print("🔴 REGRESSIONS DETECTED")
    print("=" * 80)

    for file, regressions in sorted(by_file.items()):
        print(f"\n📄 {file}")
        print(f"   {len(regressions)} regression(s) found:\n")

        for reg in regressions:
            print(f"   • Commit {reg['current_commit']} ({reg['current_date']})")
            print(f"     Author: {reg['current_author']}")
            print(f"     Message: {reg['current_message']}")
            print(f"     ⚠️  Reverted to: {reg['original_commit']} ({reg['commits_between']} commits earlier)")
            print(f"     Original: \"{reg['original_message']}\" by {reg['original_author']}")
            print()

    # Summary statistics
    print("=" * 80)
    print("📈 STATISTICS")
    print("=" * 80)

    # Most regressed files
    most_regressed = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)[:5]
    print("\nMost frequently regressed files:")
    for file, regs in most_regressed:
        print(f"  {len(regs)}x - {file}")

    # Recent regressions (last 10)
    print("\nMost recent regressions:")
    recent = sorted(all_regressions, key=lambda r: r["current_date"], reverse=True)[:10]
    for reg in recent:
        print(f"  {reg['current_commit']} ({reg['current_date'][:10]}): {reg['file']}")

    print("\n" + "=" * 80)

    return 1 if all_regressions else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze git history for code regressions (filters out formatting-only commits by default)"
    )
    parser.add_argument(
        "--commits",
        type=int,
        default=1000,
        help="Number of recent commits to analyze (default: 1000)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show progress updates",
    )
    parser.add_argument(
        "--no-filter-formatting",
        action="store_true",
        help="Disable formatting commit filter (may increase false positives)",
    )

    args = parser.parse_args()

    try:
        sys.exit(
            main(
                limit=args.commits,
                verbose=args.verbose,
                filter_formatting=not args.no_filter_formatting,
            )
        )
    except KeyboardInterrupt:
        print("\n\n❌ Analysis interrupted by user")
        sys.exit(1)
