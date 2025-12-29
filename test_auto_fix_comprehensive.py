#!/usr/bin/env python3
"""Comprehensive test for Jules auto-fix logic."""

import os
import re
import subprocess
import sys
from typing import Any, cast

import requests

# Import the extraction logic from jules module
sys.path.insert(0, ".jules")
from jules.github import extract_session_id


def fetch_jules_prs() -> list[dict[str, Any]]:
    """Fetch PRs created by Jules bot using GitHub API."""
    try:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        cmd = ["git", "config", "--get", "remote.origin.url"]
        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, check=True, timeout=10
        )
        remote_url = result.stdout.strip()

        if "github.com" in remote_url:
            parts = remote_url.split("github.com")[-1].strip("/:").replace(".git", "")
            owner, repo = parts.split("/")
        else:
            owner, repo = "franklinbaldo", "egregora"

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=30"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        all_prs = response.json()

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
            if pr.get("user", {}).get("login") == "google-labs-jules[bot]"
        ]
    except (subprocess.CalledProcessError, requests.RequestException, KeyError):
        return []


def analyze_session_id_patterns() -> dict[str, list[Any]] | None:
    """Analyze the different session ID patterns found in Jules PRs."""
    prs = fetch_jules_prs()
    if not prs:
        return None

    patterns: dict[str, list[Any]] = {
        "numeric_15plus": [],
        "uuid": [],
        "from_body_jules_url": [],
        "from_body_task": [],
        "from_body_sessions": [],
        "not_found": [],
    }

    for pr in prs:
        pr_number = pr.get("number")
        branch = pr.get("headRefName", "")
        body = pr.get("body", "")
        session_id = extract_session_id(branch, body)

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


def test_auto_fix_behavior() -> tuple[int, int] | None:
    """Test what would happen with auto-fix for recent Jules PRs."""
    prs = fetch_jules_prs()
    if not prs:
        return None

    would_fix = 0
    would_skip = 0

    for pr in prs[:10]:
        branch = pr.get("headRefName", "")
        body = pr.get("body", "")
        session_id = extract_session_id(branch, body)

        if session_id:
            would_fix += 1
        else:
            would_skip += 1

    return would_fix, would_skip


def main() -> int:
    """Run all tests."""
    analyze_session_id_patterns()
    behavior_result = test_auto_fix_behavior()
    if behavior_result:
        would_fix, would_skip = cast("tuple[int, int]", behavior_result)
        if would_skip == 0 and would_fix > 0:
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
