"""Jules Auto-Fixer."""

from typing import Any

from jules.client import JulesClient
from jules.github import fetch_failed_logs_summary, get_pr_details_via_gh


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
        return {
            "status": "skipped",
            "message": f"No session_id found for PR #{pr_number}. Auto-fix only works with existing Jules sessions.",
            "branch": details["branch"],
        }

    try:
        session = client.get_session(session_id)
        # Always send message to existing session, regardless of state
        client.send_message(
            session_id,
            f"Hi Jules! Please fix these issues in PR #{pr_number}:\n\n{feedback}{autonomous_instruction}",
        )
        return {"status": "success", "action": "messaged_existing_session", "session_id": session_id}
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to send message to session {session_id}: {e!s}",
            "session_id": session_id,
        }
