#!/usr/bin/env python3
"""Test session ID extraction logic with real Jules PRs from GitHub API."""

import json
import os
import subprocess
import sys
from typing import Any

# Import the extraction logic from jules module
sys.path.insert(0, ".jules")
from jules.github import _extract_session_id


def fetch_jules_prs() -> list[dict[str, Any]]:
    """Fetch PRs created by Jules bot using GitHub API via curl."""
    try:
        # Get token from environment
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            print("⚠️  No GITHUB_TOKEN or GH_TOKEN found. API rate limits will apply.")

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
        jules_prs = [
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

        return jules_prs
    except Exception as e:
        print(f"Error fetching PRs: {e}")
        import traceback

        traceback.print_exc()
        return []


def test_session_id_extraction():
    """Test session ID extraction with real Jules PRs."""
    print("=" * 80)
    print("Testing Session ID Extraction with Real Jules PRs")
    print("=" * 80)

    prs = fetch_jules_prs()

    if not prs:
        print("❌ No Jules PRs found or error fetching PRs")
        return

    print(f"\nFound {len(prs)} Jules PRs\n")

    success_count = 0
    fail_count = 0

    for pr in prs:
        pr_number = pr.get("number")
        branch = pr.get("headRefName", "")
        body = pr.get("body", "")
        title = pr.get("title", "")
        state = pr.get("state", "")

        # Test extraction
        session_id = _extract_session_id(branch, body)

        status = "✅" if session_id else "❌"
        if session_id:
            success_count += 1
        else:
            fail_count += 1

        print(f"{status} PR #{pr_number} ({state}): {title[:60]}")
        print(f"   Branch: {branch}")

        if session_id:
            print(f"   Session ID: {session_id}")
        else:
            print(f"   Session ID: NOT FOUND")
            # Show first 200 chars of body for debugging
            print(f"   Body preview: {body[:200]!r}...")

        print()

    print("=" * 80)
    print(f"Summary: {success_count} successful, {fail_count} failed")
    print("=" * 80)

    if fail_count > 0:
        print("\n⚠️  Some Jules PRs are missing session IDs!")
        print("This means the auto-fixer would skip them.")
        return 1
    else:
        print("\n✅ All Jules PRs have extractable session IDs!")
        return 0


if __name__ == "__main__":
    exit_code = test_session_id_extraction()
    sys.exit(exit_code or 0)
