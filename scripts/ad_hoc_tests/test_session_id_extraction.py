#!/usr/bin/env python3
"""Test session ID extraction logic with real Jules PRs from GitHub API."""

import json
import os
import subprocess
import sys
from typing import Any

# Import the extraction logic from repo module
sys.path.insert(0, ".team")
import repo.github as jules_github


def fetch_jules_prs() -> list[dict[str, Any]]:
    """Fetch PRs created by Jules bot using GitHub API via curl."""
    try:
        # Get token from environment
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            pass

        # Get repo from git remote
        cmd = ["git", "config", "--get", "remote.origin.url"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        remote_url = result.stdout.strip()

        # Extract owner/repo from URL
        # Handle formats: git@github.com:owner/repo.git or https://github.com/owner/repo.git
        if "github.com" in remote_url:
            parts = remote_url.split("github.com")[-1].strip("/:").replace(".git", "")
            owner, repo = parts.split("/")
        else:
            owner, repo = "franklinbaldo", "egregora"

        # Fetch PRs via GitHub API
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=20"
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
        import traceback

        traceback.print_exc()
        return []


def test_session_id_extraction() -> int | None:
    """Test session ID extraction with real Jules PRs."""
    prs = fetch_jules_prs()

    if not prs:
        return None

    success_count = 0
    fail_count = 0

    for pr in prs:
        pr.get("number")
        branch = pr.get("headRefName", "")
        body = pr.get("body", "")
        pr.get("title", "")
        pr.get("state", "")

        # Test extraction
        session_id = jules_github._extract_session_id(branch, body)

        if session_id:
            success_count += 1
        else:
            fail_count += 1

        if session_id:
            pass
        else:
            # Show first 200 chars of body for debugging
            pass

    if fail_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    exit_code = test_session_id_extraction()
    sys.exit(exit_code or 0)
