#!/usr/bin/env python3
import os
import sys
import argparse
import glob
from datetime import datetime
from pathlib import Path
import tomllib

# Dependencies (assumed to be available via uv run --with ...)
import frontmatter
import jinja2

# Expect JulesClient to be importable via PYTHONPATH
try:
    from jules_client import JulesClient
except ImportError:
    print("Error: Could not import JulesClient. Make sure PYTHONPATH includes .claude/skills/jules-api", file=sys.stderr)
    sys.exit(1)

def load_schedule_registry(registry_path: Path) -> dict:
    if not registry_path.exists():
        return {}
    with open(registry_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("schedules", {})

def parse_prompt_file(filepath: Path, context: dict) -> dict:
    # Use python-frontmatter to parse
    post = frontmatter.load(filepath)
    config = post.metadata
    body_template = post.content

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

def get_repo_info() -> dict:
    return {
        "owner": os.environ.get("GITHUB_REPOSITORY_OWNER", "unknown"),
        "repo": os.environ.get("GITHUB_REPOSITORY", "unknown").split("/")[-1] if "/" in os.environ.get("GITHUB_REPOSITORY", "") else "unknown",
        "repo_full": os.environ.get("GITHUB_REPOSITORY", "unknown/unknown")
    }

def check_schedule(schedule_str: str) -> bool:
    """
    Basic cron checker.
    Supports: "* * * * *" format (min hour dom month dow)
    Limitation: Only supports "*" or specific integer values.
    """
    if not schedule_str:
        return False

    parts = schedule_str.split()
    if len(parts) != 5:
        return False

    min_s, hour_s, dom_s, month_s, dow_s = parts
    now = datetime.utcnow()

    # Check Hour
    if hour_s != "*" and int(hour_s) != now.hour:
        return False

    # Check Day of Week
    # Python: 0=Mon, 6=Sun
    # Cron: 0=Sun, 6=Sat (usually) OR 7=Sun.
    # Let's align with standard cron 0=Sun.
    if dow_s != "*":
        py_dow = now.weekday() # 0=Mon
        # Convert py_dow to cron_dow (0=Sun, 1=Mon)
        cron_dow = (py_dow + 1) % 7

        if int(dow_s) != cron_dow:
            return False

    return True

def main():
    parser = argparse.ArgumentParser(description="Jules Scheduler Runner")
    parser.add_argument("command", choices=["tick"], help="Command to run")
    parser.add_argument("--all", action="store_true", help="Run all enabled prompts regardless of schedule")
    parser.add_argument("--dry-run", action="store_true", help="Do not create sessions")
    parser.add_argument("--prompt-id", help="Run specific prompt ID")

    args = parser.parse_args()

    # Initialize client
    client = JulesClient()

    repo_info = get_repo_info()
    prompts_dir = Path(".jules/prompts")
    registry_path = Path(".jules/schedules.toml")

    if not prompts_dir.exists():
        print(f"Prompts directory {prompts_dir} not found")
        sys.exit(1)

    print(f"Repo context: {repo_info}")

    prompt_files = list(prompts_dir.glob("*.md"))
    registry = load_schedule_registry(registry_path)
    print(f"Loaded {len(registry)} schedules from registry.")

    for p_file in prompt_files:
        try:
            parsed = parse_prompt_file(p_file, repo_info)
            config = parsed["config"]
            prompt_body = parsed["prompt"]

            pid = config.get("id")
            if not pid:
                continue

            # Filter by prompt_id if specified
            if args.prompt_id and args.prompt_id != pid:
                continue

            # Check enabled
            if not config.get("enabled", True):
                if args.prompt_id == pid:
                    print(f"Warning: Prompt {pid} is disabled but explicitly requested.")
                else:
                    continue

            # Check schedule
            should_run = False
            
            # Determine schedule string: Registry > Frontmatter > Default (None)
            schedule_str = registry.get(pid)
            
            # Fallback to frontmatter if not in registry (backward compatibility)
            # but ONLY if explicitly defined (not empty)
            if not schedule_str and config.get("schedule"):
                schedule_str = config.get("schedule")
                print(f"Warning: Using deprecated frontmatter schedule for {pid}: {schedule_str}")

            if args.all or (args.prompt_id == pid):
                should_run = True
            elif args.command == "tick":
                if schedule_str and check_schedule(schedule_str):
                    should_run = True
                elif not schedule_str:
                     # No schedule found means MANUAL execution only
                     pass

            if should_run:
                print(f"Running prompt: {pid}")
                if not args.dry_run:
                    resp = client.create_session(
                        prompt=prompt_body,
                        owner=repo_info["owner"],
                        repo=repo_info["repo"],
                        branch=config.get("branch", "main"),
                        title=config.get("title", f"Task: {pid}"),
                        automation_mode=config.get("automation_mode", "AUTO_CREATE_PR"),
                        require_plan_approval=config.get("require_plan_approval", False)
                    )
                    print(f"Session created: {resp.get('name')}")
                else:
                    print(f"[Dry Run] Would create session for {pid}")

        except ValueError:
            pass # Skip invalid files
        except Exception as e:
            print(f"Error processing {p_file}: {e}")

if __name__ == "__main__":
    main()