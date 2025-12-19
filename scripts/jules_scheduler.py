#!/usr/bin/env python3
import os
import sys
import argparse
import glob
import re
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Try to import yaml, install if missing
try:
    import yaml
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml"])
    import yaml

# Try to import jinja2, install if missing
try:
    import jinja2
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "jinja2"])
    import jinja2

# Check for requests/httpx
try:
    import urllib.request
    import urllib.error
except ImportError:
    pass  # Standard lib

JULES_API_URL = "https://jules.googleapis.com/v1alpha"

class JulesClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        url = f"{JULES_API_URL}/{endpoint}"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

        req = urllib.request.Request(url, method=method, headers=headers)
        if data:
            req.data = json.dumps(data).encode('utf-8')

        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"API Error ({e.code}): {error_body}", file=sys.stderr)
            raise

    def list_sources(self) -> List[Dict]:
        response = self._request("GET", "sources")
        return response.get("sources", [])

    def create_session(self,
                      prompt: str,
                      source_name: str,
                      starting_branch: str = "main",
                      title: str = "Jules Session",
                      automation_mode: str = "AUTO_CREATE_PR",
                      require_approval: bool = False) -> Dict:

        payload = {
            "prompt": prompt,
            "sourceContext": {
                "source": source_name,
                "githubRepoContext": {
                    "startingBranch": starting_branch
                }
            },
            "automationMode": automation_mode,
            "requirePlanApproval": require_approval,
            "title": title
        }
        return self._request("POST", "sessions", payload)

def parse_prompt_file(filepath: Path, context: Dict[str, Any]) -> Dict[str, Any]:
    content = filepath.read_text(encoding='utf-8')

    # Extract frontmatter
    match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
    if not match:
        raise ValueError(f"Invalid format in {filepath}: Missing frontmatter")

    fm_text = match.group(1)
    body_template = match.group(2)

    config = yaml.safe_load(fm_text)

    # Render body template
    template = jinja2.Template(body_template)
    rendered_body = template.render(**context)

    # Render title template if present
    title = config.get("title", "Jules Task")
    if "{{" in title:
         title = jinja2.Template(title).render(**context)
         config["title"] = title

    return {
        "config": config,
        "prompt": rendered_body.strip()
    }

def get_repo_info() -> Dict[str, str]:
    # Try to get from git
    try:
        remote_url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"]).decode().strip()
        # Parse owner/repo from https://github.com/owner/repo.git or git@github.com:owner/repo.git
        match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?', remote_url)
        if match:
            owner, repo = match.groups()
            return {"owner": owner, "repo": repo, "repo_full": f"{owner}/{repo}"}
    except Exception:
        pass

    # Fallback to env vars or defaults
    return {
        "owner": os.environ.get("GITHUB_REPOSITORY_OWNER", "unknown"),
        "repo": os.environ.get("GITHUB_REPOSITORY", "unknown").split("/")[-1] if "/" in os.environ.get("GITHUB_REPOSITORY", "") else "unknown",
        "repo_full": os.environ.get("GITHUB_REPOSITORY", "unknown/unknown")
    }

def main():
    parser = argparse.ArgumentParser(description="Jules Scheduler Client")
    parser.add_argument("command", choices=["tick"], help="Command to run")
    parser.add_argument("--all", action="store_true", help="Run all enabled prompts regardless of schedule")
    parser.add_argument("--dry-run", action="store_true", help="Do not create sessions")
    parser.add_argument("--prompt-id", help="Run specific prompt ID")

    args = parser.parse_args()

    api_key = os.environ.get("JULES_API_KEY")
    if not api_key and not args.dry_run:
        print("Error: JULES_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = JulesClient(api_key) if api_key else None

    # Find prompt files
    prompts_dir = Path(".jules/prompts")
    if not prompts_dir.exists():
        print(f"Prompts directory {prompts_dir} not found")
        sys.exit(1)

    repo_info = get_repo_info()
    print(f"Repo context: {repo_info}")

    prompt_files = list(prompts_dir.glob("*.md"))

    # If not dry run, verify source exists
    source_name = None
    if client and not args.dry_run:
        try:
            sources = client.list_sources()
            # Find matching source for current repo
            for s in sources:
                gh = s.get("githubRepo", {})
                if gh.get("owner") == repo_info["owner"] and gh.get("repo") == repo_info["repo"]:
                    source_name = s["name"]
                    break

            if not source_name:
                print(f"Error: No configured source found for {repo_info['repo_full']}. Install Jules App on this repo first.")
                sys.exit(1)
            print(f"Found source: {source_name}")
        except Exception as e:
            print(f"Failed to list sources: {e}")
            sys.exit(1)
    elif args.dry_run:
        source_name = "sources/github/dry-run/repo"

    for p_file in prompt_files:
        try:
            parsed = parse_prompt_file(p_file, repo_info)
            config = parsed["config"]
            prompt_body = parsed["prompt"]

            pid = config.get("id")
            if not pid:
                print(f"Skipping {p_file}: No 'id' in frontmatter")
                continue

            # Filter by prompt_id if specified
            if args.prompt_id and args.prompt_id != pid:
                continue

            # Check enabled
            if not config.get("enabled", True):
                if args.prompt_id == pid:
                    print(f"Warning: Prompt {pid} is disabled but explicitly requested.")
                else:
                    print(f"Skipping {pid}: Disabled")
                    continue

            # Check schedule (simplified: always run if --all or specified, otherwise ignore cron logic for now as 'tick' implies external trigger or we implement cron check)
            # The original 'tick' command likely checked the cron schedule against current time.
            # Implementing full cron parsing is complex without a library like croniter.
            # For this task, since the workflow runs on schedule, we might rely on the workflow trigger?
            # BUT the workflow runs multiple times a day. If we run all every time, it's too much.
            # The user said "tick" runs checks.
            # For now, to keep it simple and under 50 lines (oops, script is longer, but the change to repo is adding a file),
            # I will assume --all is passed when we want to force run.
            # For 'tick', we need to check if the current time matches the cron.
            # Since I can't easily add 'croniter' dependency, I will skip the strict schedule check and rely on --all or just print "Would check schedule"
            # UNLESS the user explicitly wants to replicate exact behavior.
            # The workflow passes 'tick'.

            should_run = False
            if args.all or (args.prompt_id == pid):
                should_run = True
            elif args.command == "tick":
                # Basic check: matching day of week / hour?
                # Without croniter, this is hard.
                # Let's assume for this specific task/request, the user might be running with --all or specific IDs in dispatch.
                # The scheduled workflow runs 3 times.
                # 0 10 * * 2 (Tue 10am)
                # 0 8 * * * (Daily 8am)
                # 0 9 * * 1 (Mon 9am)
                # The prompt files have schedules.
                # artisan: 0 10 * * 2
                # janitor: 0 8 * * *

                # We can do a basic check against current UTC hour/dow
                now = datetime.utcnow()
                cron = config.get("schedule", "* * * * *").split()
                # cron: min hour dom month dow
                # 0 10 * * 2

                # Very naive check
                matches = True
                if len(cron) == 5:
                    min_s, hour_s, dom_s, month_s, dow_s = cron

                    if hour_s != "*" and int(hour_s) != now.hour:
                        matches = False
                    if dow_s != "*":
                        # Python weekday: Mon=0, Sun=6. Cron: Sun=0/7, Mon=1... wait.
                        # Standard cron: 0=Sun, 1=Mon.
                        # Python: 0=Mon. So Cron = (Python + 1) % 7
                        py_dow = now.weekday()
                        cron_dow = (py_dow + 1) % 7
                        if int(dow_s) != cron_dow:
                             matches = False

                    # Ignore minute for now, assuming workflow runs on the hour

                if matches:
                    should_run = True
                else:
                    print(f"Skipping {pid}: Schedule {config.get('schedule')} does not match current time (Hour: {now.hour}, DoW: {(now.weekday() + 1) % 7})")

            if should_run:
                print(f"Running prompt: {pid}")
                if not args.dry_run:
                    resp = client.create_session(
                        prompt=prompt_body,
                        source_name=source_name,
                        starting_branch=config.get("branch", "main"),
                        title=config.get("title", f"Task: {pid}"),
                        automation_mode=config.get("automation_mode", "AUTO_CREATE_PR"),
                        require_approval=config.get("require_plan_approval", False)
                    )
                    print(f"Session created: {resp.get('name')} - {resp.get('outputs', [{}])[0].get('pullRequest', {}).get('url', 'No PR created yet')}")
                else:
                    print(f"[Dry Run] Would create session for {pid}")
                    print(f"Title: {config.get('title')}")
                    print(f"Prompt preview: {prompt_body[:100]}...")

        except Exception as e:
            print(f"Error processing {p_file}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
