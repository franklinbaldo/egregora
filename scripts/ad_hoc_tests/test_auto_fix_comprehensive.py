#!/usr/bin/env python3
"""Comprehensive test for Jules auto-fix logic."""

import json
import os
import re
import subprocess
import sys
from typing import Any

# Import the extraction logic from repo module
sys.path.insert(0, ".team")

import repo.github as jules_github

SessionIdPatterns = dict[str, list[tuple[int | None, str, str | None] | tuple[int | None, str]]]


def fetch_jules_prs() -> list[dict[str, Any]]:
    """Fetch PRs created by Jules bot using GitHub API via curl."""
    try:
        # Get token from environment
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

        # Get repo from git remote
        cmd = ["git", "config", "--get", "remote.origin.url"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
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

        result = subprocess.run(curl_cmd, capture_output=True, text=True, check=True)
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
    patterns = {
        "numeric_15plus": [],  # -(\d{15,})$
        "uuid": [],  # -UUID$
        "from_body_jules_url": [],  # jules.google.com/task/(\d+)
        "from_body_task": [],  # /task/ID
        "from_body_sessions": [],  # /sessions/ID
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

    if patterns["uuid"]:
        for _pr_num, _branch, _sid in patterns["uuid"][:3]:
            continue

    if patterns["numeric_15plus"]:
        for _pr_num, _branch, _sid in patterns["numeric_15plus"][:3]:
            continue

    if patterns["from_body_jules_url"]:
        for _pr_num, _branch, _sid in patterns["from_body_jules_url"][:3]:
            continue

    if patterns["not_found"]:
        for _pr_num, _branch in patterns["not_found"]:
            continue

    return patterns


def test_auto_fix_behavior() -> tuple[int, int] | None:
    """Test what would happen with auto-fix for recent Jules PRs."""
    prs = fetch_jules_prs()

    if not prs:
        return 0, 0

    would_fix = 0
    would_skip = 0

    for pr in prs[:10]:  # Test first 10
        pr.get("number")
        branch = pr.get("headRefName", "")
        body = pr.get("body", "")
        pr.get("state", "")

        session_id = jules_github._extract_session_id(branch, body)

        if session_id:
            would_fix += 1
        else:
            would_skip += 1

    return would_fix, would_skip


def main() -> int:
    """Run all tests."""
    # Test 1: Pattern analysis
    analyze_session_id_patterns()

    # Test 2: Auto-fix behavior
    would_fix, would_skip = test_auto_fix_behavior()

    # Final verdict

    would_fix + would_skip

    if would_skip == 0:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
