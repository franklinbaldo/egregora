"""GitHub utilities for Jules."""

import json
import os
import re
import subprocess
from typing import Any


def run_gh_command(args: list[str], cwd: str = ".") -> Any:
    """Run a gh CLI command and return JSON."""
    cmd = ["gh", *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=cwd)
        # Handle cases where output is empty
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except subprocess.CalledProcessError:
        raise


def get_open_prs(owner: str, repo: str) -> list[dict[str, Any]]:
    """Fetch open PRs using gh CLI."""
    if not os.environ.get("GITHUB_TOKEN") and not os.environ.get("GH_TOKEN"):
        # If no token, we probably can't run gh commands unless authenticated
        return []

    try:
        return (
            run_gh_command(
                [
                    "pr",
                    "list",
                    "--repo",
                    f"{owner}/{repo}",
                    "--state",
                    "open",
                    "--json",
                    "number,title,headRefName,url,author,isDraft",
                    "--limit",
                    "50",
                ]
            )
            or []
        )
    except Exception:
        return []


def get_pr_details_via_gh(pr_number: int, repo_path: str = ".") -> dict[str, Any]:
    """Retrieve PR details using the gh CLI."""
    try:
        pr_data = run_gh_command(
            [
                "pr",
                "view",
                str(pr_number),
                "--json",
                "title,body,headRefName,baseRefName,isDraft,mergeable,statusCheckRollup,files,comments,reviews,latestReviews,commits,author",
            ],
            cwd=repo_path,
        )
    except Exception:
        msg = f"Failed to view PR {pr_number}"
        raise Exception(msg)

    if not pr_data:
        msg = f"PR {pr_number} not found"
        raise Exception(msg)

    # Extract session ID
    branch = pr_data.get("headRefName", "")
    body = pr_data.get("body", "")
    session_id = _extract_session_id(branch, body)

    # Check CI
    checks_rollup = pr_data.get("statusCheckRollup", [])
    all_passed, failed_check_names = _analyze_checks(checks_rollup)

    # Enrich with more raw data for feedback loop
    return {
        "number": pr_number,
        "title": pr_data.get("title"),
        "body": body,
        "session_id": session_id,
        "branch": branch,
        "base_branch": pr_data.get("baseRefName"),
        "is_draft": pr_data.get("isDraft"),
        "has_conflicts": pr_data.get("mergeable") == "CONFLICTING",
        "passed_all_checks": all_passed,
        "failed_check_names": failed_check_names,
        "changed_files": [f["path"] for f in pr_data.get("files", [])],
        # Raw fields needed for feedback loop
        "reviews": pr_data.get("reviews", []),
        "latestReviews": pr_data.get("latestReviews", []),
        "comments": pr_data.get("comments", []),
        "commits": pr_data.get("commits", []),
        "author": pr_data.get("author", {}),
        "statusCheckRollup": checks_rollup,
    }


def get_base_sha(base_branch: str, repo_path: str = ".") -> str:
    """Get the current SHA of the base branch (origin)."""
    cmd = ["git", "rev-parse", f"origin/{base_branch}"]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=repo_path)
    if result.returncode == 0:
        return result.stdout.strip()
    return "Unknown"


def _extract_session_id(branch: str, body: str) -> str | None:
    """Extract Jules session ID from branch name or PR body."""
    # Try branch regex: numeric ID at the end
    numeric_match = re.search(r"-(\d{15,})$", branch)
    if numeric_match:
        return numeric_match.group(1)

    # If not in branch, try body regex for different URL formats
    if body:
        # jules.google.com/session/SESSION_ID or jules.google/sessions/SESSION_ID
        body_match = re.search(r"jules\.google(?:\.com)?/(?:session|sessions)/(\d+)", body)
        if body_match:
            return body_match.group(1)

        # /task/SESSION_ID
        task_match = re.search(r"/task/(\d+)", body)
        if task_match:
            return task_match.group(1)

    return None


def _analyze_checks(checks_rollup: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """Analyze status checks to determine pass/fail status."""
    all_passed = True
    failed_check_names = []
    for check in checks_rollup:
        status = check.get("conclusion") or check.get("status") or check.get("state")
        # GitHub Actions 'failure', Status API 'error'/'failure'
        if status in ["FAILURE", "failure", "error", "timed_out"]:
            all_passed = False
            failed_check_names.append(check.get("name") or check.get("context"))
    return all_passed, failed_check_names


def fetch_failed_logs_summary(pr_number: int, cwd: str = ".") -> str:
    """Fetch logs summary using gh CLI."""
    # This might fail if logs are expired or not available
    try:
        cmd = ["gh", "pr", "checks", str(pr_number), "--failing"]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=cwd)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def get_repo_info() -> dict[str, str]:
    """Get owner and repo from environment."""
    return {
        "owner": os.environ.get("GITHUB_REPOSITORY_OWNER", "unknown"),
        "repo": os.environ.get("GITHUB_REPOSITORY", "unknown").split("/")[-1]
        if "/" in os.environ.get("GITHUB_REPOSITORY", "")
        else "unknown",
        "repo_full": os.environ.get("GITHUB_REPOSITORY", "unknown/unknown"),
    }
