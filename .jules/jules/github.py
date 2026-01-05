"""GitHub utilities for Jules."""

import json
import os
import re
import subprocess
from typing import Any
from jules.exceptions import GitHubError

JULES_BOT_LOGINS = {"google-labs-jules[bot]", "app/google-labs-jules", "google-labs-jules"}


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
    except Exception as e:
        raise GitHubError(f"Failed to view PR {pr_number}: {e}") from e

    if not pr_data:
        raise GitHubError(f"PR {pr_number} not found")

    # Extract session ID
    branch = pr_data.get("headRefName", "")
    body = pr_data.get("body", "")
    session_id = _extract_session_id(branch, body)
    commits = pr_data.get("commits", [])
    last_commit_author = _get_last_commit_author_login(commits)

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
        "last_commit_author_login": last_commit_author,
        "last_commit_by_jules": _is_jules_login(last_commit_author),
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
    session_id = None
    # Try branch regex: -(\d{15,})$ or UUID
    # UUID regex from feed_feedback.py
    uuid_match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$", branch)
    if uuid_match:
        return uuid_match.group(1)

    # Numeric ID regex
    match = re.search(r"-(\d{15,})$", branch)
    if match:
        session_id = match.group(1)

    if not session_id:
        # Try body regex: jules.google.com/task/(\d+)
        match = re.search(r"jules\.google\.com/task/(\d+)", body)
        if match:
            session_id = match.group(1)
        else:
            # Try other patterns
            match = re.search(r"/task/([a-zA-Z0-9-]+)", body)
            if match:
                session_id = match.group(1)
            else:
                match = re.search(r"/sessions/([a-zA-Z0-9-]+)", body)
                if match:
                    session_id = match.group(1)

    return session_id


def _get_last_commit_author_login(commits: list[dict[str, Any]] | None) -> str | None:
    """Return the login of the last commit author, if available."""
    if not commits:
        return None

    last_commit = commits[-1] or {}
    author = last_commit.get("author")
    if isinstance(author, dict):
        login = author.get("login")
        if login:
            return login

    for commit_author in last_commit.get("authors") or []:
        if not isinstance(commit_author, dict):
            continue

        user = commit_author.get("user")
        if isinstance(user, dict):
            login = user.get("login")
            if login:
                return login

        login = commit_author.get("login")
        if login:
            return login

    return None


def _is_jules_login(login: str | None) -> bool:
    """Check whether a login belongs to the Jules bot account."""
    if not login:
        return False
    return login in JULES_BOT_LOGINS


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


def fetch_full_ci_logs(pr_number: int, branch: str, repo_full: str, cwd: str = ".") -> str:
    """Fetch full CI logs for the latest failing workflow run on the branch.

    The logs are fetched via the GitHub CLI by first locating recent workflow runs for the
    branch, then retrieving the log output for the newest failing run. If anything goes wrong
    (missing CLI, permissions, or decode errors), an empty string is returned so callers can
    gracefully fall back to summaries.
    """

    if not branch or not repo_full:
        return ""

    try:
        runs_result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo_full}/actions/runs",
                "-F",
                f"branch={branch}",
                "-F",
                "event=pull_request",
                "-F",
                "per_page=5",
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""

    try:
        runs_payload = json.loads(runs_result.stdout)
    except json.JSONDecodeError:
        return ""

    workflow_runs = runs_payload.get("workflow_runs", [])
    failing_runs = [run for run in workflow_runs if run.get("conclusion") == "failure"]

    if not failing_runs:
        return ""

    logs_sections: list[str] = []

    for run in failing_runs[:1]:
        run_id = run.get("id")
        if not run_id:
            continue

        try:
            log_result = subprocess.run(
                [
                    "gh",
                    "run",
                    "view",
                    str(run_id),
                    "--log",
                    "--repo",
                    repo_full,
                ],
                check=True,
                capture_output=True,
                text=True,
                cwd=cwd,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

        log_text = log_result.stdout.strip()
        if not log_text:
            continue

        workflow_name = run.get("name") or "Workflow"
        logs_sections.append(f"### {workflow_name} (Run ID: {run_id})\n\n{log_text}")

    return "\n\n".join(logs_sections)


def get_repo_info() -> dict[str, str]:
    """Get owner and repo from environment."""
    return {
        "owner": os.environ.get("GITHUB_REPOSITORY_OWNER", "unknown"),
        "repo": os.environ.get("GITHUB_REPOSITORY", "unknown").split("/")[-1]
        if "/" in os.environ.get("GITHUB_REPOSITORY", "")
        else "unknown",
        "repo_full": os.environ.get("GITHUB_REPOSITORY", "unknown/unknown"),
    }
