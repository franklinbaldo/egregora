"""Jules Feedback Loop."""

import subprocess
import sys
from typing import Any

from jules.client import JulesClient
from jules.github import get_pr_details_via_gh, get_repo_info, run_gh_command


def should_trigger_feedback(pr_data: dict[str, Any]) -> bool:
    """Determine if a PR needs feedback."""
    # 1. Check CI Status - statusCheckRollup is a list of check results
    checks_rollup = pr_data.get("statusCheckRollup") or []

    # Check if any check has failed
    ci_failed = False
    for check in checks_rollup:
        status = check.get("conclusion") or check.get("status") or check.get("state")
        if status in ["FAILURE", "failure", "error", "timed_out", "ERROR"]:
            ci_failed = True
            break

    # 2. Check Reviews
    reviews = pr_data.get("latestReviews", [])
    changes_requested = any(r.get("state") == "CHANGES_REQUESTED" for r in reviews)

    return ci_failed or changes_requested


def should_skip_feedback(pr_data: dict[str, Any], comments: list[dict[str, Any]]) -> bool:
    """Check if we should skip feedback (loop prevention)."""
    if not comments:
        return False

    last_feedback_comment = None
    for c in reversed(comments):
        if "# Task: Fix Pull Request" in c["body"] or "<!-- # Task: Fix Pull Request -->" in c["body"]:
            last_feedback_comment = c
            break

    if not last_feedback_comment:
        return False

    commits = pr_data.get("commits", [])
    if not commits:
        return True

    last_commit = commits[-1]
    commit_date_str = last_commit.get("committedDate")
    comment_date_str = last_feedback_comment.get("createdAt")

    if commit_date_str and comment_date_str:
        # If comment is newer than commit, we already gave feedback for this state
        if comment_date_str > commit_date_str:
            return True

    return False


def construct_prompt(pr_data: dict[str, Any], ci_checks: list[dict[str, Any]]) -> str:
    """Construct the prompt for Jules."""
    pr_number = pr_data["number"]
    pr_title = pr_data["title"]
    branch = pr_data.get("headRefName") or pr_data.get("branch", "")

    # Analyze CI
    failed_checks = [c for c in ci_checks if c["state"] in ["FAILURE", "ERROR"]]
    ci_section = ""
    if failed_checks:
        ci_section = "## CI Failures\nThe following checks failed:\n"
        for check in failed_checks:
            ci_section += (
                f"- **{check['name']}**: {check.get('url') or check.get('target_url') or 'No URL'}\n"
            )
    else:
        ci_section = "## CI Status\nCI checks passed (or none failed yet).\n"

    # Analyze Reviews
    pr_data.get("reviews", [])  # Full review history
    latest_reviews = pr_data.get("latestReviews", [])
    comments = pr_data.get("comments", [])

    review_section = "## Review Feedback\n"

    # Get recent reviews (last 3 from latest state?)
    for review in latest_reviews[-3:]:
        if review["state"] in ["CHANGES_REQUESTED", "COMMENTED"]:
            review_section += (
                f"### Review by {review['author']['login']} ({review['state']})\n{review['body']}\n\n"
            )

    # Get recent comments (last 5)
    for comment in comments[-5:]:
        login = comment["author"]["login"]
        # Skip our own bot comments if possible, or include them for context
        review_section += f"**{login}**: {comment['body'][:500]}...\n\n"

    return f"""
# Task: Fix Pull Request #{pr_number}

Your Pull Request "{pr_title}" on branch `{branch}` has received feedback that needs attention.

{ci_section}

{review_section}

## Instructions
1. Analyze the feedback above.
2. Examine the code in the current branch (`{branch}`).
3. Fix the reported issues (CI failures or review comments).
4. Commit and push your changes.
"""


def run_feedback_loop(dry_run: bool = False, author_filter: str = "app/google-labs-jules") -> None:
    """Run the feedback loop."""
    repo_info = get_repo_info()
    owner, repo = repo_info["owner"], repo_info["repo"]

    if owner == "unknown" or repo == "unknown":
        sys.exit(1)

    # Fetch PRs
    try:
        prs = (
            run_gh_command(
                [
                    "pr",
                    "list",
                    "--author",
                    author_filter,
                    "--state",
                    "open",
                    "--json",
                    "number,title,headRefName,url,author,isDraft",
                ]
            )
            or []
        )
    except Exception:
        return

    if not prs:
        return

    client = None
    if not dry_run:
        try:
            client = JulesClient()
        except Exception:
            sys.exit(1)

    for pr_summary in prs:
        pr_num = pr_summary["number"]

        try:
            pr_details = get_pr_details_via_gh(pr_num)
        except Exception:
            continue

        comments = pr_details.get("comments", [])

        if should_skip_feedback(pr_data=pr_details, comments=comments):
            continue

        if should_trigger_feedback(pr_details):
            # Get detailed CI status manually if needed, or use rollup from details
            # feed_feedback.py used `gh pr checks` separately to get links
            try:
                checks = (
                    run_gh_command(["pr", "checks", str(pr_num), "--json", "name,state,url,target_url"]) or []
                )
            except Exception:
                checks = []

            prompt = construct_prompt(pr_details, checks)
            branch_name = pr_details["branch"]
            session_id = pr_details["session_id"]

            if not dry_run and client:
                try:
                    session_id_to_use = session_id

                    if session_id_to_use:
                        try:
                            client.send_message(session_id_to_use, prompt)
                        except Exception:
                            session_id_to_use = None  # Fallback to create new

                    if not session_id_to_use:
                        client.create_session(
                            prompt=prompt,
                            owner=owner,
                            repo=repo,
                            branch=branch_name,
                            title=f"Fix PR #{pr_num}: {pr_summary['title']}",
                            automation_mode="AUTO_CREATE_PR",
                            require_plan_approval=False,
                        )

                    marker_body = "🤖 Feedback sent to Jules session. \n<!-- # Task: Fix Pull Request -->"
                    subprocess.run(["gh", "pr", "comment", str(pr_num), "--body", marker_body], check=True)

                except Exception:
                    pass
        else:
            pass
