"""Jules Auto-Fixer."""

import subprocess
from typing import Any

from jules.client import JulesClient
from jules.github import fetch_failed_logs_summary, get_pr_details_via_gh


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

    details = get_pr_details_via_gh(pr_number, repo_path=repo_root)

    if details.get("passed_all_checks") and not details.get("has_conflicts"):
        return {"status": "success", "message": "PR is healthy."}

    # Fetch failing logs
    logs_summary = ""
    if details.get("failed_check_names"):
        logs_summary = fetch_failed_logs_summary(pr_number, cwd=repo_root)

    # Construct feedback message
    feedback = f"Issues detected in Pull Request #{pr_number}:\n"
    if details.get("has_conflicts"):
        feedback += "- **Merge Conflicts** detected. Please rebase and resolve them.\n"
    if details.get("failed_check_names"):
        failed_list = ", ".join(details["failed_check_names"])
        feedback += f"- **CI Failures**: {failed_list}\n"
        if logs_summary:
            feedback += f"\nSummary of failing checks:\n```\n{logs_summary}\n```\n"

    client = JulesClient()
    session_id = details.get("session_id")

    autonomous_instruction = (
        "\n\n**🤖 CRITICAL - Full Autonomy Required:**\n"
        "- **NEVER ask humans for help, approval, or implementation decisions**\n"
        "- **ALWAYS make your own technical decisions** using your senior developer expertise\n"
        "- **If tests fail:** Debug, fix the issue, adjust your approach - don't ask for help\n"
        "- **You are a senior developer:** Trust your experience - ship working code confidently\n"
    )

    # Only send message to existing session - never create new sessions
    if not session_id:
        comment = (
            "## 🤖 Auto-Fix: Skipped\n\n"
            "⚠️ **No session ID found** - This PR was not created by Jules or the session ID could not be extracted.\n\n"
            "Auto-fix only works with PRs created by Jules that have an associated session ID."
        )
        post_pr_comment(pr_number, comment)

        return {
            "status": "skipped",
            "message": f"No session_id found for PR #{pr_number}. Auto-fix only works with existing Jules sessions.",
            "branch": details["branch"],
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
            f"Check the [Jules session](https://jules.google.com) for progress."
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
