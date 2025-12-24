import os
import sys
import json
import subprocess
import re
from typing import Any

# Add the skill path to sys.path to import JulesClient
skill_path = "/home/user/workspace/egregora/.claude/skills/jules-api"
if skill_path not in sys.path:
    sys.path.append(skill_path)

from jules_client import JulesClient


def get_pr_details_via_gh(pr_number: int, repo_path: str = "/home/user/workspace/egregora") -> dict[str, Any]:
    """Retrieve PR details using the gh CLI."""
    cmd = [
        "gh", "pr", "view", str(pr_number), 
        "--json", "title,body,headRefName,baseRefName,isDraft,mergeable,statusCheckRollup,files"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path)
    if result.returncode != 0:
        raise Exception(f"gh pr view failed: {result.stderr.strip()}")
    
    pr_data = json.loads(result.stdout)
    
    # Extract session ID
    branch = pr_data.get("headRefName", "")
    body = pr_data.get("body", "")
    session_id = None
    match = re.search(r"-(\d{15,})$", branch)
    if match:
        session_id = match.group(1)
    if not session_id:
        match = re.search(r"jules\.google\.com/task/(\d+)", body)
        if match:
            session_id = match.group(1)
        else:
            match = re.search(r"task \[(\d+)\]", body)
            if match:
                session_id = match.group(1)

    # Check CI
    checks_rollup = pr_data.get("statusCheckRollup", [])
    all_passed = True
    failed_check_names = []
    for check in checks_rollup:
        status = check.get("conclusion") or check.get("status") or check.get("state")
        if status == "FAILURE":
            all_passed = False
            failed_check_names.append(check.get("name") or check.get("context"))

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
        "changed_files": [f["path"] for f in pr_data.get("files", [])]
    }


def get_base_sha(base_branch: str, repo_path: str = "/home/user/workspace/egregora") -> str:
    """Get the current SHA of the base branch (origin)."""
    cmd = ["git", "rev-parse", f"origin/{base_branch}"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path)
    if result.returncode == 0:
        return result.stdout.strip()
    return "Unknown"


def auto_reply_to_jules(pr_number: int) -> dict[str, Any]:
    print(f"--- Analyzing PR #{pr_number} ---")
    details = get_pr_details_via_gh(pr_number)
    
    if details.get("passed_all_checks") and not details.get("has_conflicts"):
        return {"status": "success", "message": "PR is healthy."}

    # Fetch failing logs summary via gh
    logs_summary = ""
    if details.get("failed_check_names"):
        cmd = ["gh", "pr", "checks", str(pr_number), "--failing"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/user/workspace/egregora")
        if result.returncode == 0:
            logs_summary = result.stdout.strip()

    # Construct the feedback message
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
                print(f"Sending feedback to active Jules Session {session_id}...")
                client.send_message(session_id, f"Hi Jules! Please fix these issues in PR #{pr_number}:\n\n{feedback}{autonomous_instruction}")
                return {"status": "success", "action": "messaged_active_session", "session_id": session_id}
            else:
                print(f"Session {session_id} is {state}. Starting a new follow-up session...")
        except Exception as e:
            print(f"Could not message session {session_id}: {e}. Falling back to new session.")

    # 2. Start a NEW session with enhanced context and autonomy mandate
    print("Creating a new Jules session for fixes...")
    base_sha = get_base_sha(details["base_branch"])
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
            owner="franklinbaldo",
            repo="egregora",
            branch=details["branch"],
            title=f"Fix #{pr_number}: {details['title']}",
            automation_mode="AUTO_CREATE_PR"
        )
        return {
            "status": "success", 
            "action": "created_new_session", 
            "new_session_id": new_session["id"],
            "branch": details["branch"],
            "prompt_sent": new_prompt
        }
    except Exception as e:
        return {"error": f"Failed to start new session: {str(e)}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    result = auto_reply_to_jules(int(sys.argv[1]))
    print(json.dumps(result, indent=2))