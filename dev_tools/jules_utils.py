import re
import os
from typing import Any
import requests


def get_jules_pr_details(
    owner: str, 
    repo: str, 
    pr_number: int, 
    token: str | None = None
) -> dict[str, Any]:
    """Retrieve comprehensive info about a Jules PR using the GitHub REST API.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request number.
        token: GitHub personal access token (optional for public repos, 
               but required for logs and private details).

    Returns:
        A dictionary with session_id, branch, status, checks, conflicts, and failed_logs.
    """
    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    # 1. Fetch Pull Request Info
    pr_resp = requests.get(f"{base_url}/pulls/{pr_number}", headers=headers)
    pr_resp.raise_for_status()
    pr_data = pr_resp.json()

    body = pr_data.get("body", "")
    branch = pr_data.get("head", {}).get("ref", "")
    is_draft = pr_data.get("draft", False)
    mergeable = pr_data.get("mergeable") # True, False, or None
    has_conflicts = mergeable is False
    head_sha = pr_data.get("head", {}).get("sha")

    # 2. Extract Jules Session ID
    session_id = None
    if branch:
        match = re.search(r"-(\d{15,})$", branch)
        if match:
            session_id = match.group(1)
    if not session_id and body:
        match = re.search(r"jules\.google\.com/task/(\d+)", body)
        if match:
            session_id = match.group(1)
        else:
            match = re.search(r"task \[(\d+)\]", body)
            if match:
                session_id = match.group(1)

    # 3. Fetch Check Runs
    checks_resp = requests.get(f"{base_url}/commits/{head_sha}/check-runs", headers=headers)
    checks_resp.raise_for_status()
    checks_data = checks_resp.json()

    all_passed = True
    failed_checks = []
    for run in checks_data.get("check_runs", []):
        conclusion = run.get("conclusion")
        status = run.get("status")
        
        if status == "completed":
            if conclusion not in ["success", "skipped", "neutral"]:
                all_passed = False
                if conclusion == "failure":
                    failed_checks.append({
                        "name": run.get("name"),
                        "id": run.get("id"),
                        "details_url": run.get("details_url")
                    })
        else:
            # If any check is still in progress, we can't say "passed all"
            all_passed = False

    # 4. Fetch Logs for Failed Checks (GitHub Actions)
    failed_logs = {}
    for check in failed_checks:
        # For GitHub Actions, the details_url contains the job ID
        # Pattern: .../actions/runs/RUN_ID/job/JOB_ID
        details_url = check.get("details_url", "")
        job_match = re.search(r"/job/(\d+)", details_url)
        if job_match:
            job_id = job_match.group(1)
            log_url = f"{base_url}/actions/jobs/{job_id}/logs"
            log_resp = requests.get(log_url, headers=headers)
            if log_resp.status_code == 200:
                failed_logs[check["name"]] = log_resp.text
            else:
                failed_logs[check["name"]] = f"Could not fetch logs (HTTP {log_resp.status_code})"
        else:
            failed_logs[check["name"]] = "No Job ID found in details_url"

    return {
        "session_id": session_id,
        "branch": branch,
        "is_draft": is_draft,
        "is_ready": not is_draft,
        "passed_all_checks": all_passed,
        "has_conflicts": has_conflicts,
        "failed_check_names": [c["name"] for c in failed_checks],
        "failed_logs": failed_logs
    }


if __name__ == "__main__":
    # Note: Requires 'requests' library. Run: pip install requests
    # Example usage:
    try:
        # Attempt to get token from env if available
        gh_token = os.environ.get("GITHUB_TOKEN")
        details = get_jules_pr_details("franklinbaldo", "egregora", 1581, token=gh_token)
        
        print(f"Jules Session ID: {details['session_id']}")
        print(f"Branch:           {details['branch']}")
        print(f"Status:           {'Draft' if details['is_draft'] else 'Ready'}")
        print(f"CI Passed:        {details['passed_all_checks']}")
        print(f"Has Conflicts:    {details['has_conflicts']}")
        print(f"Failed Checks:    {', '.join(details['failed_check_names'])}")
        
        if details['failed_logs']:
            print("\n--- Failed Logs Snippets ---")
            for name, log in details['failed_logs'].items():
                snippet = log[-500:] if len(log) > 500 else log
                print(f"[{name}]\n...{snippet}\n")
                
    except Exception as e:
        print(f"Error: {e}")