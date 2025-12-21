#!/usr/bin/env python3
"""
Feed Jules Feedback Script
Checks open PRs from Jules, analyzes CI results and reviews, and feeds feedback back to Jules.
"""
import os
import sys
import argparse
import requests
import json
import re
from pathlib import Path
from urllib.parse import urlparse

# Add .claude/skills/jules-api to sys.path to import JulesClient
jules_api_path = Path(__file__).parent.parent / ".claude" / "skills" / "jules-api"
sys.path.append(str(jules_api_path))

try:
    from jules_client import JulesClient
except ImportError:
    # If the path assumption failed, try standard import if pythonpath is set
    try:
        from jules_client import JulesClient
    except ImportError:
        print(f"Error: Could not import JulesClient. Make sure {jules_api_path} exists or PYTHONPATH is set.", file=sys.stderr)
        # We don't exit here immediately to allow running 'gh' checks if needed, but it will fail later.

def get_repo_info():
    """Get owner and repo from environment or git config."""
    repo_full = os.environ.get("GITHUB_REPOSITORY")
    if repo_full:
        owner, repo = repo_full.split("/")
        return owner, repo

    # Fallback to local git
    import subprocess
    try:
        url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"], text=True).strip()
        # Support HTTPS/HTTP URLs like https://github.com/owner/repo(.git)
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.hostname == "github.com":
            path = parsed.path.lstrip("/")
            if path.endswith(".git"):
                path = path[:-4]
            owner, repo = path.split("/", 1)
            return owner, repo
        # Support SSH URLs like git@github.com:owner/repo(.git)
        if "@github.com:" in url:
            _, path_part = url.split("@github.com:", 1)
            path = path_part.lstrip("/")
            if path.endswith(".git"):
                path = path[:-4]
            owner, repo = path.split("/", 1)
            return owner, repo
    except Exception:
        pass
    return None, None

def run_gh_command(args):
    """Run a gh CLI command and return JSON."""
    import subprocess
    cmd = ["gh"] + args + ["--json", "number,title,author,headRefName,url,commits,reviews,statusCheckRollup,latestReviews"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running gh command: {e.stderr}", file=sys.stderr)
        return []

def get_pr_ci_status(pr_number):
    """Get detailed CI status for a PR."""
    import subprocess
    # gh pr checks <number> --json bucket,name,conclusion,url
    cmd = ["gh", "pr", "checks", str(pr_number), "--json", "bucket,name,conclusion,url"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching checks for PR {pr_number}: {e.stderr}", file=sys.stderr)
        return []

def get_pr_comments(pr_number):
    """Get comments and reviews for a PR."""
    import subprocess
    # gh pr view <number> --json comments,reviews
    cmd = ["gh", "pr", "view", str(pr_number), "--json", "comments,reviews"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching comments for PR {pr_number}: {e.stderr}", file=sys.stderr)
        return {}

def should_trigger_feedback(pr):
    """Determine if a PR needs feedback."""
    # 1. Check CI Status
    # statusCheckRollup gives a high level view, but we might want specifics
    status = pr.get("statusCheckRollup") or {}
    state = status.get("state", "PENDING")

    ci_failed = state == "FAILURE"

    # 2. Check Reviews
    reviews = pr.get("latestReviews", [])
    changes_requested = any(r["state"] == "CHANGES_REQUESTED" for r in reviews)

    # We only want to trigger if:
    # - CI is completely done and failed
    # - OR Review requests changes

    if not (ci_failed or changes_requested):
        return False

    # Heuristic Loop Prevention:
    # Check if the latest comment on the PR is already a feedback prompt from us.
    # Since we can't easily identify "our" comments without a specific marker,
    # we can check if the last comment body starts with "# Task: Fix Pull Request".
    # This isn't perfect but prevents immediate re-triggering if nothing else happened.

    # We need comments data here, but this function only takes 'pr'.
    # We'll assume the caller might handle this or we fetch it.
    # Since we fetch detailed comments later, let's defer this check or do a lightweight check.
    # Actually, 'pr' object from 'gh pr view' includes 'latestReviews'.
    # But it doesn't include the timeline of comments unless we asked for it.

    # Simpler approach: Check if we have already commented on the current commit SHA.
    # We can't know that easily without state.

    # Let's rely on the caller to not spam.
    # But wait, the plan required loop prevention.
    return True

def construct_prompt(pr, ci_checks, comments_data):
    """Construct the prompt for Jules."""
    pr_number = pr["number"]
    pr_title = pr["title"]
    branch = pr["headRefName"]

    # Analyze CI
    failed_checks = [c for c in ci_checks if c["conclusion"] == "FAILURE"]
    ci_section = ""
    if failed_checks:
        ci_section = "## CI Failures\nThe following checks failed:\n"
        for check in failed_checks:
            ci_section += f"- **{check['name']}**: {check['url']}\n"
    else:
        ci_section = "## CI Status\nCI checks passed (or none failed yet).\n"

    # Analyze Reviews
    reviews = comments_data.get("reviews", [])
    comments = comments_data.get("comments", [])

    review_section = "## Review Feedback\n"

    # Get recent reviews (last 3)
    for review in reviews[-3:]:
        if review["state"] in ["CHANGES_REQUESTED", "COMMENTED"]:
             review_section += f"### Review by {review['author']['login']} ({review['state']})\n{review['body']}\n\n"

    # Get recent comments (last 5)
    for comment in comments[-5:]:
        # Filter out comments that look like Jules' own logs if possible, but hard to know
        review_section += f"**{comment['author']['login']}**: {comment['body'][:500]}...\n\n"

    prompt = f"""
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
    return prompt

def extract_session_id(branch_name: str) -> str | None:
    """
    Extract session ID from branch name.
    Assumption: branch ends with the session ID (often UUID-like)
    Pattern usually: feature-branch-SESSION_ID or jules/branch-SESSION_ID
    Let's look for a UUID or a long alphanumeric string at the end.
    """
    # Regex for typical UUID or session ID at end of string
    # Try finding UUID v4
    uuid_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$', branch_name)
    if uuid_match:
        return uuid_match.group(1)

    # Fallback: try finding something that looks like a session ID after a separator
    # This might match 'main' if not careful, but branches are usually hyphenated.
    parts = branch_name.split('-')
    if len(parts) > 1:
        last_part = parts[-1]
        # Heuristic: Session IDs are usually long (>10 chars)
        if len(last_part) > 10:
             return last_part

    return None

def main():
    parser = argparse.ArgumentParser(description="Feed Jules Feedback")
    parser.add_argument("--dry-run", action="store_true", help="Do not create sessions")
    parser.add_argument("--author", default="jules-bot", help="Filter PRs by author")
    args = parser.parse_args()

    owner, repo = get_repo_info()
    if not owner or not repo:
        print("Error: Could not determine repo owner/name", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning PRs for {owner}/{repo} by author {args.author}...")

    # Find PRs
    # gh pr list --author <author> --state open
    cmd = ["pr", "list", "--author", args.author, "--state", "open"]
    try:
        prs = run_gh_command(cmd)
    except FileNotFoundError:
        print("Error: 'gh' command not found. Ensure GitHub CLI is installed.", file=sys.stderr)
        sys.exit(1)

    if not prs:
        print("No open PRs found for this author.")
        return

    client = None
    if not args.dry_run:
        try:
            client = JulesClient()
        except Exception as e:
            print(f"Failed to initialize JulesClient: {e}", file=sys.stderr)
            sys.exit(1)

    for pr in prs:
        print(f"Checking PR #{pr['number']}: {pr['title']}")

        # Get detailed PR info
        import subprocess
        try:
             res = subprocess.run(["gh", "pr", "view", str(pr['number']), "--json", "number,title,headRefName,statusCheckRollup,latestReviews,author"], capture_output=True, text=True, check=True)
             pr_data = json.loads(res.stdout)
        except Exception as e:
            print(f"Failed to view PR {pr['number']}: {e}")
            continue

        # Pre-fetch comments to check for loops
        comments_data = get_pr_comments(pr['number'])

        # Loop Prevention: Check if the last comment is already a feedback prompt
        last_comment_body = ""
        if comments_data.get("comments"):
            last_comment_body = comments_data["comments"][-1]["body"]

        if "# Task: Fix Pull Request" in last_comment_body:
             print(f"-> PR #{pr['number']} already has pending feedback (last comment). Skipping.")
             continue

        if should_trigger_feedback(pr_data):
            print(f"-> PR #{pr['number']} needs feedback.")

            # Fetch details
            ci_checks = get_pr_ci_status(pr['number'])
            # comments_data already fetched

            prompt = construct_prompt(pr_data, ci_checks, comments_data)
            branch_name = pr_data["headRefName"]
            session_id = extract_session_id(branch_name)

            print(f"   Branch: {branch_name}")
            print(f"   Extracted Session ID: {session_id}")

            print("-------- PROMPT PREVIEW --------")
            print(prompt)
            print("--------------------------------")

            if not args.dry_run and client:
                try:
                    if session_id:
                        print(f"Sending message to existing session {session_id}...")
                        client.send_message(session_id, prompt)
                        print("Message sent.")
                    else:
                        print("No session ID found in branch name. Creating new session...")
                        resp = client.create_session(
                            prompt=prompt,
                            owner=owner,
                            repo=repo,
                            branch=branch_name,
                            title=f"Fix PR #{pr['number']}: {pr['title']}",
                            automation_mode="AUTO_CREATE_PR"
                        )
                        print(f"Session created: {resp.get('name')}")

                    # Mark the PR as having received feedback to prevent loops
                    # We post a comment so the next run detects it via loop prevention check
                    print("Posting comment to PR to mark feedback loop...")
                    marker_body = f"🤖 Feedback sent to Jules session. \n<!-- # Task: Fix Pull Request -->"
                    subprocess.run(["gh", "pr", "comment", str(pr['number']), "--body", marker_body], check=True)

                except Exception as e:
                    print(f"Failed to communicate with Jules or update PR: {e}")
                    # If sending message fails (e.g. session closed), maybe fallback to create?
                    # For now, let's log and continue.
        else:
            print(f"-> PR #{pr['number']} seems fine or pending.")

if __name__ == "__main__":
    main()
