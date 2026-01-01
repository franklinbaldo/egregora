"""Jules Auto-Fixer."""

import os
import subprocess
from pathlib import Path
from typing import Any

import jinja2

from jules.client import JulesClient
from jules.github import (
    fetch_failed_logs_summary,
    fetch_full_ci_logs,
    get_base_sha,
    get_pr_details_via_gh,
    get_repo_info,
)


def post_pr_comment(pr_number: int, comment: str, repo_path: str = ".") -> None:
    """Post a comment on a PR using gh CLI.

    Requires gh CLI to be installed and GH_TOKEN or GITHUB_TOKEN to be set.
    """
    try:
        cmd = ["gh", "pr", "comment", str(pr_number), "--body", comment]
        subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=repo_path)
        print(f"📝 Posted comment on PR #{pr_number}")
    except FileNotFoundError:
        print(f"⚠️  gh CLI not found - skipping PR comment")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Failed to post PR comment: {e.stderr if e.stderr else e}")
    except Exception as e:
        print(f"⚠️  Failed to post PR comment: {e}")
        # Don't fail the whole operation if comment posting fails


def auto_reply_to_jules(pr_number: int) -> dict[str, Any]:
    # Use repo root as cwd for git/gh commands
    repo_root = "."
    repo_info = get_repo_info()
    repo_full = repo_info["repo_full"]

    details = get_pr_details_via_gh(pr_number, repo_path=repo_root)

    if details.get("passed_all_checks") and not details.get("has_conflicts"):
        return {"status": "success", "message": "PR is healthy."}

    # Fetch failing logs
    logs_summary = ""
    full_ci_logs = ""
    if details.get("failed_check_names"):
        logs_summary = fetch_failed_logs_summary(pr_number, cwd=repo_root)
        full_ci_logs = fetch_full_ci_logs(
            pr_number=pr_number, branch=details.get("branch", ""), repo_full=repo_full, cwd=repo_root
        )

    feedback = _render_feedback_prompt(
        pr_number=pr_number,
        details=details,
        logs_summary=logs_summary,
        full_ci_logs=full_ci_logs,
    )

    client = JulesClient()
    session_id = details.get("session_id")

    autonomous_instruction = (
        "\n\n**🤖 CRITICAL - Full Autonomy Required:**\n"
        "- **NEVER ask humans for help, approval, or implementation decisions**\n"
        "- **ALWAYS make your own technical decisions** using your senior developer expertise\n"
        "- **If tests fail:** Debug, fix the issue, adjust your approach - don't ask for help\n"
        "- **You are a senior developer:** Trust your experience - ship working code confidently\n"
    )

    # Decision point: Send message to existing session OR create new session
    if not session_id:
        # PR is NOT from Jules - create a new session to fix it
        print(f"📋 No session_id found - creating NEW Jules session for PR #{pr_number}")

        # Get repo info from environment
        owner, repo = (
            repo_full.split("/") if "/" in repo_full else ("franklinbaldo", "egregora")
        )

        # Get base branch SHA for context
        base_sha = get_base_sha(details["base_branch"], repo_path=repo_root)
        files_list = "\n".join([f"- `{f}`" for f in details["changed_files"]])

        # Construct comprehensive prompt with all PR details and errors
        new_session_prompt = (
            f"# Fix Pull Request #{pr_number}: {details['title']}\n\n"
            f"## Context\n"
            f"- **PR Number**: #{pr_number}\n"
            f"- **Current Branch**: `{details['branch']}`\n"
            f"- **Base Branch**: `{details['base_branch']}`\n"
            f"- **Base Branch Current SHA**: `{base_sha}`\n"
            f"- **Author**: {details.get('author', {}).get('login', 'Unknown')}\n\n"
            f"## Changed Files\n"
            f"{files_list}\n\n"
            f"## Original PR Description\n"
            f"{details['body'] or '_(No description provided)_'}\n\n"
            f"## Problems to Fix\n"
            f"{feedback}"
            f"{autonomous_instruction}\n\n"
            f"## Your Task\n"
            f"1. Checkout the branch `{details['branch']}`\n"
            f"2. Investigate the failures and conflicts\n"
            f"3. Fix all issues\n"
            f"4. Run tests to verify fixes\n"
            f"5. Push your updates to the same branch\n\n"
            f"Start by checking out the branch and understanding the changes."
        )

        # Create new session
        try:
            new_session = client.create_session(
                prompt=new_session_prompt,
                owner=owner,
                repo=repo,
                branch=details["branch"],
                title=f"🔧 Auto-Fix PR #{pr_number}: {details['title'][:60]}",
                automation_mode="AUTO_CREATE_PR",
                require_plan_approval=False,
            )

            new_session_id = new_session.get("name", "").split("/")[-1] if new_session.get("name") else "unknown"
            print(f"✅ Created new session: {new_session_id}")

            # Post success comment
            comment = (
                f"## 🤖 Auto-Fix: New Session Created\n\n"
                f"✅ **Jules session created to fix this PR**\n\n"
                f"- **Session ID**: `{new_session_id}`\n"
                f"- **Branch**: `{details['branch']}`\n\n"
                f"### Issues to Fix:\n\n"
                f"{feedback}\n\n"
                f"Jules will:\n"
                f"1. Check out your branch\n"
                f"2. Investigate the failures\n"
                f"3. Fix the issues\n"
                f"4. Push updates to this branch\n\n"
                f"Track progress at: https://jules.google.com/sessions/{new_session_id}"
            )
            post_pr_comment(pr_number, comment)

            return {
                "status": "success",
                "action": "created_new_session",
                "session_id": new_session_id,
                "branch": details["branch"],
            }
        except Exception as e:
            error_msg = f"Failed to create new session for PR #{pr_number}: {e!s}"
            print(f"❌ {error_msg}")

            comment = (
                f"## 🤖 Auto-Fix: Failed to Create Session\n\n"
                f"❌ **Error creating Jules session**\n\n"
                f"- **Error**: {e!s}\n\n"
                f"The auto-fixer tried to create a new Jules session to fix this PR, "
                f"but encountered an error. This could be due to:\n"
                f"- Jules API unavailable\n"
                f"- Authentication issues\n"
                f"- Rate limiting\n\n"
                f"Check the workflow logs for more details."
            )
            post_pr_comment(pr_number, comment)

            return {
                "status": "error",
                "error_type": "create_session_failed",
                "message": error_msg,
            }

    # Step 1: Get the session (separate error handling)
    try:
        session = client.get_session(session_id)
        session_state = session.get("state", "UNKNOWN")
        print(f"📡 Session {session_id} state: {session_state}")
    except Exception as e:
        error_msg = f"Failed to retrieve session {session_id}: {e!s}"
        comment = (
            f"## 🤖 Auto-Fix: Failed\n\n"
            f"❌ **Error retrieving Jules session**\n\n"
            f"- **Session ID**: `{session_id}`\n"
            f"- **Error**: {e!s}\n\n"
            f"The session may have been deleted or the API request failed. "
            f"Check the workflow logs for more details."
        )
        post_pr_comment(pr_number, comment)

        return {
            "status": "error",
            "error_type": "get_session_failed",
            "message": error_msg,
            "session_id": session_id,
        }

    # Step 2: Send message to session (separate error handling)
    try:
        message_text = f"Hi Jules! Please fix these issues in PR #{pr_number}:\n\n{feedback}{autonomous_instruction}"
        response = client.send_message(session_id, message_text)

        # Validate response (send_message should return a dict)
        if not isinstance(response, dict):
            print(f"⚠️  Unexpected response from send_message: {response}")

        print(f"✅ Message sent successfully to session {session_id}")

        # Post success comment to PR
        comment = (
            f"## 🤖 Auto-Fix: Message Sent\n\n"
            f"✅ **Fix request sent to Jules**\n\n"
            f"- **Session ID**: `{session_id}`\n"
            f"- **Session State**: `{session_state}`\n\n"
            f"### Message Sent:\n\n"
            f"> {feedback}\n\n"
            f"Jules will process this request and update the PR. "
            f"Check the [Jules session](https://jules.google.com/sessions/{session_id}) for progress."
        )
        post_pr_comment(pr_number, comment)

        return {
            "status": "success",
            "action": "messaged_existing_session",
            "session_id": session_id,
            "session_state": session_state,
        }
    except Exception as e:
        error_msg = f"Failed to send message to session {session_id} (state: {session_state}): {e!s}"
        comment = (
            f"## 🤖 Auto-Fix: Failed\n\n"
            f"❌ **Error sending message to Jules session**\n\n"
            f"- **Session ID**: `{session_id}`\n"
            f"- **Session State**: `{session_state}`\n"
            f"- **Error**: {e!s}\n\n"
            f"The message failed to send. This could be due to:\n"
            f"- Network/API timeout\n"
            f"- Session in invalid state\n"
            f"- API rate limiting\n\n"
            f"Check the workflow logs for more details."
        )
        post_pr_comment(pr_number, comment)

        return {
            "status": "error",
            "error_type": "send_message_failed",
            "message": error_msg,
            "session_id": session_id,
            "session_state": session_state,
        }


def _render_feedback_prompt(
    pr_number: int, details: dict[str, Any], logs_summary: str, full_ci_logs: str
) -> str:
    """Render the feedback prompt using Jinja for clarity and flexibility."""
    env = jinja2.Environment(
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja2.StrictUndefined,
    )

    template_path = Path(__file__).parent / "templates" / "autofix_prompt.jinja"
    template = env.from_string(template_path.read_text())

    failed_check_names = details.get("failed_check_names") or []
    has_conflicts = bool(details.get("has_conflicts"))

    context = {
        "pr_number": pr_number,
        "has_conflicts": has_conflicts,
        "failed_check_names": failed_check_names,
        "logs_summary": logs_summary,
        "full_ci_logs": full_ci_logs,
    }

    return template.render(**context)
