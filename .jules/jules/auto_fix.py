"""Jules Auto-Fixer."""

from typing import Any

from jules.client import JulesClient
from jules.github import fetch_failed_logs_summary, get_base_sha, get_pr_details_via_gh


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

    # 1. Try to message active session
    if session_id:
        try:
            session = client.get_session(session_id)
            state = session.get("state")
            if state not in ["COMPLETED", "FAILED"]:
                client.send_message(
                    session_id,
                    f"Hi Jules! Please fix these issues in PR #{pr_number}:\n\n{feedback}{autonomous_instruction}",
                )
                return {"status": "success", "action": "messaged_active_session", "session_id": session_id}
        except Exception:
            pass

    # 2. Start a NEW session
    base_sha = get_base_sha(details["base_branch"], repo_path=repo_root)
    files_list = "\n".join([f"- {f}" for f in details["changed_files"]])

    new_prompt = (
        f"FIX REQUEST for Pull Request #{pr_number}: {details['title']}\n\n"
        f"## Context\n"
        f"- **PR Number:** {pr_number}\n"
        f"- **Current Branch:** `{details['branch']}`\n"
        f"- **Base Branch:** `{details['base_branch']}`\n"
        f"- **Base Branch Current SHA:** `{base_sha}`\n"
        f"- **Changed Files in this PR:**\n{files_list}\n\n"
        f"## Original PR Description\n"
        f"{details['body']}\n\n"
        f"## Detected Problems to Fix\n"
        f"{feedback}"
        f"{autonomous_instruction}\n"
        f"Please checkout the branch `{details['branch']}`, investigate the failures, fix them, and push an update."
    )

    try:
        new_session = client.create_session(
            prompt=new_prompt,
            owner="franklinbaldo",  # TODO: parameterize
            repo="egregora",  # TODO: parameterize
            branch=details["branch"],
            title=f"Fix #{pr_number}: {details['title']}",
            automation_mode="AUTO_CREATE_PR",
        )
        return {
            "status": "success",
            "action": "created_new_session",
            "new_session_id": new_session.get("name"),  # Resource name
            "branch": details["branch"],
        }
    except Exception as e:
        return {"error": f"Failed to start new session: {e!s}"}
