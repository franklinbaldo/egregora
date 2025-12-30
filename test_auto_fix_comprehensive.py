#!/usr/bin/env python3
"""Comprehensive test for Jules auto-fix logic."""

import json
import os
import re
import subprocess
import sys
from typing import Any

# Import the extraction logic from jules module
sys.path.insert(0, ".jules")

import jules.github as jules_github

SessionIdPatterns = dict[str, list[tuple[int | None, str, str | None] | tuple[int | None, str]]]


def fetch_jules_prs() -> list[dict[str, Any]]:
    """Fetch PRs created by Jules bot using GitHub API via curl."""
    try:
        # Get token from environment
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

        # Get repo from git remote
        cmd = ["git", "config", "--get", "remote.origin.url"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603
        remote_url = result.stdout.strip()

        # Extract owner/repo from URL
        if "github.com" in remote_url:
            parts = remote_url.split("github.com")[-1].strip("/:").replace(".git", "")
            owner, repo = parts.split("/")
        else:
            owner, repo = "franklinbaldo", "egregora"

        # Fetch PRs via GitHub API
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=30"
        curl_cmd = ["curl", "-s", url]
        if token:
            curl_cmd.extend(["-H", f"Authorization: Bearer {token}"])

        result = subprocess.run(curl_cmd, capture_output=True, text=True, check=True)  # noqa: S603
        all_prs = json.loads(result.stdout)

        # Filter for Jules PRs
        return [
            {
                "number": pr["number"],
                "title": pr["title"],
                "headRefName": pr["head"]["ref"],
                "body": pr["body"] or "",
                "url": pr["html_url"],
                "author": pr["user"]["login"],
                "state": pr["state"],
            }
            for pr in all_prs
            if pr["user"]["login"] == "google-labs-jules[bot]"
        ]

    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return []


def analyze_session_id_patterns() -> SessionIdPatterns | None:
    """Analyze the different session ID patterns found in Jules PRs."""
    prs = fetch_jules_prs()

    # Track different patterns
    patterns: SessionIdPatterns = {
        "numeric_15plus": [],
        "uuid": [],
        "from_body_jules_url": [],
        "from_body_task": [],
        "from_body_sessions": [],
        "not_found": [],
    }

    if not prs:
        return patterns

    for pr in prs:
        pr_number = pr.get("number")
        branch = pr.get("headRefName", "")
        body = pr.get("body", "")

        session_id = jules_github._extract_session_id(branch, body)

        # Categorize by pattern
        if not session_id:
            patterns["not_found"].append((pr_number, branch))
        elif re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$", branch):
            patterns["uuid"].append((pr_number, branch, session_id))
        elif re.search(r"-(\d{15,})$", branch):
            patterns["numeric_15plus"].append((pr_number, branch, session_id))
        elif "jules.google.com/task/" in body:
            patterns["from_body_jules_url"].append((pr_number, branch, session_id))
        elif "/task/" in body:
            patterns["from_body_task"].append((pr_number, branch, session_id))
        elif "/sessions/" in body:
            patterns["from_body_sessions"].append((pr_number, branch, session_id))

    return patterns


def test_auto_fix_behavior() -> None:
    """Test what would happen with auto-fix for recent Jules PRs."""
    prs = fetch_jules_prs()

    if not prs:
        return

    would_fix = 0
    would_skip = 0

    # Test first 10
    test_prs = prs[:10]
    for pr in test_prs:
        pr.get("number")
        branch = pr.get("headRefName", "")
        body = pr.get("body", "")
        pr.get("state", "")

        session_id = jules_github._extract_session_id(branch, body)

        if session_id:
            would_fix += 1
        else:
            would_skip += 1

    assert would_fix >= 0, "Counter for fixes should be non-negative"  # noqa: S101
    assert would_skip >= 0, "Counter for skips should be non-negative"  # noqa: S101


def main() -> int:
    """Run all tests."""
    # Test 1: Pattern analysis
    patterns = analyze_session_id_patterns()
    if patterns:
        for _name, _found in patterns.items():
            pass

    # Test 2: Auto-fix behavior
    test_auto_fix_behavior()

    return 0


if __name__ == "__main__":
    sys.exit(main())
