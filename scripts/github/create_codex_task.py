#!/usr/bin/env python3
"""Create a Codex reconciliation task when the auto-rebase workflow fails."""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import urllib.error
import urllib.request
from typing import Any, Dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report a failed automatic rebase to the Codex reconciliation API.",
    )
    parser.add_argument("--pr-number", required=True, help="Pull request number to report.")
    parser.add_argument("--author", required=True, help="GitHub handle of the PR author.")
    parser.add_argument(
        "--pr-url",
        required=True,
        help="URL to the pull request so the Codex task links back to GitHub.",
    )
    parser.add_argument(
        "--log-file",
        required=True,
        help="Path to a file containing the git rebase output to include in the task.",
    )
    parser.add_argument(
        "--api-url",
        default="https://api.openai.com/v1/codex/reconciliation-tasks",
        help="Codex API endpoint for reconciliation tasks.",
    )
    parser.add_argument(
        "--max-log-bytes",
        type=int,
        default=60_000,
        help="Maximum number of bytes from the rebase log to include in the payload.",
    )
    return parser.parse_args()


def load_log(path: str, limit: int) -> str:
    try:
        with open(path, "rb") as handle:
            data = handle.read(limit)
            remainder = handle.read(1)
    except OSError as exc:
        raise RuntimeError(f"Unable to read rebase log at {path}: {exc}") from exc

    text = data.decode("utf-8", errors="replace")
    if remainder:
        text += "\n…\n[truncated log output]"
    return text


def build_payload(args: argparse.Namespace, log_excerpt: str) -> Dict[str, Any]:
    summary = textwrap.dedent(
        f"""
        Pull request #{args.pr_number} by @{args.author} failed to rebase onto the base branch.
        The automation attempted to rebase and reported the following log output:
        {log_excerpt}
        """
    ).strip()

    return {
        "pr_number": args.pr_number,
        "author": args.author,
        "pr_url": args.pr_url,
        "summary": summary,
        "log_excerpt": log_excerpt,
    }


def post_task(api_url: str, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    request = urllib.request.Request(api_url, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(payload).encode("utf-8")

    with urllib.request.urlopen(request, data=data, timeout=30) as response:
        body = response.read()
        if response.getcode() >= 300:
            raise RuntimeError(
                f"Codex API returned status {response.getcode()}: {body.decode('utf-8', errors='replace')}"
            )
        return json.loads(body)


def main() -> None:
    args = parse_args()

    token = os.environ.get("CODEX_API_TOKEN")
    if not token:
        raise RuntimeError("CODEX_API_TOKEN secret is not available to create a Codex task.")

    log_excerpt = load_log(args.log_file, args.max_log_bytes)
    payload = build_payload(args, log_excerpt)

    try:
        response = post_task(args.api_url, token, payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Codex API request failed with status {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unable to reach Codex API: {exc.reason}") from exc

    task_id = response.get("id", "<unknown>")
    print(f"Created Codex reconciliation task {task_id} for PR #{args.pr_number}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # pragma: no cover - defensive logging for CI
        print(f"::error::{error}")
        sys.exit(1)
