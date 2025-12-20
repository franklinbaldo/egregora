#!/usr/bin/env python3
import os
import sys
import argparse
import glob
from datetime import datetime
from pathlib import Path

# Dependencies (assumed to be available via uv run --with ...)
import frontmatter
import jinja2

# Expect JulesClient to be importable via PYTHONPATH
try:
    from jules_client import JulesClient
except ImportError:
    print("Error: Could not import JulesClient. Make sure PYTHONPATH includes .claude/skills/jules-api", file=sys.stderr)
    sys.exit(1)

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
    Check if current time matches cron schedule.
    Uses croniter for robust cron expression parsing.
    Supports full cron syntax: *, ranges (1-5), lists (1,3,5), steps (*/15).
    """
    if not schedule_str:
        return False

    try:
        from croniter import croniter
        now = datetime.utcnow()
        cron = croniter(schedule_str, now)
        prev_time = cron.get_prev(datetime)
        # Check if we're within the current minute window
        time_diff = (now - prev_time).total_seconds()
        return time_diff < 60  # Within the last minute
    except ImportError:
        # Fallback to basic parser if croniter not available
        return _basic_schedule_check(schedule_str)
    except (KeyError, ValueError):
        # Invalid cron expression
        return False


def _basic_schedule_check(schedule_str: str) -> bool:
    """
    Basic cron checker fallback.
    Supports: "* * * * *" format (min hour dom month dow)
    Limitation: Only supports "*" or specific integer values.
    """
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
        py_dow = now.weekday()  # 0=Mon
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

    if not prompts_dir.exists():
        print(f"Prompts directory {prompts_dir} not found")
        sys.exit(1)

    print(f"Repo context: {repo_info}")

    prompt_files = list(prompts_dir.glob("*.md"))

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
            if args.all or (args.prompt_id == pid):
                should_run = True
            elif args.command == "tick":
                if check_schedule(config.get("schedule", "* * * * *")):
                    should_run = True

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
