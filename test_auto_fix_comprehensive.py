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
from jules.github import _extract_session_id, get_pr_details_via_gh


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
        return []


def analyze_session_id_patterns():
    """Analyze the different session ID patterns found in Jules PRs."""
    print("=" * 80)
    print("Session ID Pattern Analysis")
    print("=" * 80)

    prs = fetch_jules_prs()

    if not prs:
        print("❌ No Jules PRs found")
        return

    # Track different patterns
    patterns = {
        "numeric_15plus": [],  # -(\d{15,})$
        "uuid": [],  # -UUID$
        "from_body_jules_url": [],  # jules.google.com/task/(\d+)
        "from_body_task": [],  # /task/ID
        "from_body_sessions": [],  # /sessions/ID
        "not_found": [],
    }

    for pr in prs:
        pr_number = pr.get("number")
        branch = pr.get("headRefName", "")
        body = pr.get("body", "")

        session_id = _extract_session_id(branch, body)

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

    print("\n📊 Pattern Distribution:\n")

    print(f"UUID in branch name: {len(patterns['uuid'])} PRs")
    if patterns["uuid"]:
        for pr_num, branch, sid in patterns["uuid"][:3]:
            print(f"  - PR #{pr_num}: ...{branch[-50:]}")

    print(f"\nNumeric ID (15+ digits) in branch: {len(patterns['numeric_15plus'])} PRs")
    if patterns["numeric_15plus"]:
        for pr_num, branch, sid in patterns["numeric_15plus"][:3]:
            print(f"  - PR #{pr_num}: ...{branch[-50:]} → {sid}")

    print(f"\nFrom body (jules.google.com/task/): {len(patterns['from_body_jules_url'])} PRs")
    if patterns["from_body_jules_url"]:
        for pr_num, branch, sid in patterns["from_body_jules_url"][:3]:
            print(f"  - PR #{pr_num}: {sid}")

    print(f"\nFrom body (/task/): {len(patterns['from_body_task'])} PRs")
    print(f"From body (/sessions/): {len(patterns['from_body_sessions'])} PRs")

    print(f"\n⚠️  NOT FOUND: {len(patterns['not_found'])} PRs")
    if patterns["not_found"]:
        for pr_num, branch in patterns["not_found"]:
            print(f"  - PR #{pr_num}: {branch}")

    print("\n" + "=" * 80)
    return patterns


def test_auto_fix_behavior():
    """Test what would happen with auto-fix for recent Jules PRs."""
    print("=" * 80)
    print("Auto-Fix Behavior Test")
    print("=" * 80)

    prs = fetch_jules_prs()

    if not prs:
        print("❌ No Jules PRs found")
        return

    print(f"\nTesting auto-fix behavior for {len(prs)} Jules PRs:\n")

    would_fix = 0
    would_skip = 0

    for pr in prs[:10]:  # Test first 10
        pr_number = pr.get("number")
        branch = pr.get("headRefName", "")
        body = pr.get("body", "")
        state = pr.get("state", "")

        session_id = _extract_session_id(branch, body)

        if session_id:
            would_fix += 1
            print(f"✅ PR #{pr_number} ({state}): Would send fix message to session {session_id}")
        else:
            would_skip += 1
            print(f"⚠️  PR #{pr_number} ({state}): Would SKIP (no session_id)")

    print("\n" + "=" * 80)
    print(f"Summary: {would_fix} would fix, {would_skip} would skip")
    print("=" * 80)

    return would_fix, would_skip


def main():
    """Run all tests."""
    print("\n🧪 Comprehensive Auto-Fix Testing\n")

    # Test 1: Pattern analysis
    patterns = analyze_session_id_patterns()

    print("\n")

    # Test 2: Auto-fix behavior
    would_fix, would_skip = test_auto_fix_behavior()

    # Final verdict
    print("\n" + "=" * 80)
    print("Final Analysis")
    print("=" * 80)

    total_checked = would_fix + would_skip

    if would_skip == 0:
        print("\n✅ SUCCESS: All Jules PRs have extractable session IDs!")
        print("   The auto-fixer will work correctly for all Jules PRs.")
        return 0
    else:
        print(f"\n⚠️  WARNING: {would_skip}/{total_checked} Jules PRs would be skipped!")
        print("   The session ID extraction logic may need improvement.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
