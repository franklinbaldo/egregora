#!/usr/bin/env python3
"""Jules API Client Helper
A simple Python client for interacting with Google's Jules API.
"""

import argparse
import os
import subprocess
import sys
from typing import Any

import requests


class JulesClient:
    """Client for Google Jules API."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        """Initialize the Jules client.

        Args:
            api_key: Jules API key. If not provided, will check JULES_API_KEY
                     environment variable, then fall back to gcloud auth.
            base_url: The base URL for the Jules API. If not provided, will
                      check JULES_BASE_URL environment variable, then fall back
                      to the default production URL.

        """
        self.api_key = api_key or os.environ.get("JULES_API_KEY")
        self.base_url = base_url or os.environ.get("JULES_BASE_URL", "https://jules.googleapis.com/v1alpha")
        self.access_token = None
        self.using_oauth = False  # Track if we're using OAuth vs API key

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Goog-Api-Key"] = self.api_key
        else:
            if not self.access_token:
                try:
                    result = subprocess.run(
                        ["gcloud", "auth", "print-access-token"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    self.access_token = result.stdout.strip()
                except subprocess.CalledProcessError as e:
                    msg = (
                        "Failed to get access token. Make sure you either:\n"
                        "1. Set JULES_API_KEY environment variable, or\n"
                        "2. Authenticate with gcloud: gcloud auth login"
                    )
                    raise Exception(msg) from e
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def create_session(  # noqa: PLR0913
        self,
        prompt: str,
        owner: str,
        repo: str,
        branch: str = "main",
        title: str | None = None,
        require_plan_approval: bool = False,
        automation_mode: str = "AUTO_CREATE_PR",
    ) -> dict[str, Any]:
        """Create a new Jules session.

        Args:
            prompt: The task description
            owner: GitHub repository owner
            repo: GitHub repository name
            branch: Starting branch name (default: main)
            title: Optional session title
            require_plan_approval: Whether to require manual plan approval
            automation_mode: Automation mode (AUTO_CREATE_PR or MANUAL)

        Returns:
            Session object with id, state, etc.

        """
        url = f"{self.base_url}/sessions"
        data = {
            "prompt": prompt,
            "sourceContext": {
                "source": f"sources/github/{owner}/{repo}",
                "githubRepoContext": {"startingBranch": branch},
            },
            "automationMode": automation_mode,
        }

        if title:
            data["title"] = title

        if require_plan_approval:
            data["requirePlanApproval"] = require_plan_approval

        response = requests.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return response.json()

    def get_session(self, session_id: str) -> dict[str, Any]:
        """Get details of a specific session.

        Args:
            session_id: The session ID

        Returns:
            Session object

        """
        url = f"{self.base_url}/sessions/{session_id}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def list_sessions(self) -> dict[str, Any]:
        """List all sessions.

        Returns:
            List of session objects

        """
        url = f"{self.base_url}/sessions"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def send_message(self, session_id: str, message: str) -> dict[str, Any]:
        """Send a message to an active session.

        Args:
            session_id: The session ID
            message: Message content

        Returns:
            Updated session object

        """
        url = f"{self.base_url}/sessions/{session_id}:sendMessage"
        data = {"message": message}
        response = requests.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return response.json()

    def approve_plan(self, session_id: str) -> dict[str, Any]:
        """Approve a plan for a session.

        Args:
            session_id: The session ID

        Returns:
            Updated session object

        """
        url = f"{self.base_url}/sessions/{session_id}:approvePlan"
        response = requests.post(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_activities(self, session_id: str) -> dict[str, Any]:
        """Get activities for a session.

        Args:
            session_id: The session ID

        Returns:
            List of activity objects

        """
        url = f"{self.base_url}/sessions/{session_id}/activities"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()


def main(argv: list[str] | None = None) -> None:
    """CLI interface for Jules API."""
    parser = argparse.ArgumentParser(description="Jules API Client Helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new Jules session")
    create_parser.add_argument("prompt", help="The task description")
    create_parser.add_argument("owner", help="GitHub repository owner")
    create_parser.add_argument("repo", help="GitHub repository name")
    create_parser.add_argument("--branch", default="main", help="Starting branch name")
    create_parser.add_argument("--title", help="Optional session title")
    create_parser.add_argument(
        "--require-plan-approval", action="store_true", help="Require manual plan approval"
    )
    create_parser.add_argument(
        "--automation-mode",
        default="AUTO_CREATE_PR",
        help="Automation mode (AUTO_CREATE_PR or MANUAL)",
    )

    # Get command
    get_parser = subparsers.add_parser("get", help="Get details of a specific session")
    get_parser.add_argument("session_id", help="The session ID")

    # List command
    subparsers.add_parser("list", help="List all sessions")

    # Message command
    message_parser = subparsers.add_parser("message", help="Send a message to an active session")
    message_parser.add_argument("session_id", help="The session ID")
    message_parser.add_argument("message", nargs="+", help="Message content")

    # Approve command
    approve_parser = subparsers.add_parser("approve-plan", help="Approve a plan for a session")
    approve_parser.add_argument("session_id", help="The session ID")

    # Activities command
    activities_parser = subparsers.add_parser("activities", help="Get activities for a session")
    activities_parser.add_argument("session_id", help="The session ID")

    args = parser.parse_args(argv)
    client = JulesClient()

    try:
        if args.command == "create":
            client.create_session(
                prompt=args.prompt,
                owner=args.owner,
                repo=args.repo,
                branch=args.branch,
                title=args.title,
                require_plan_approval=args.require_plan_approval,
                automation_mode=args.automation_mode,
            )
        elif args.command == "get":
            client.get_session(args.session_id)
        elif args.command == "list":
            client.list_sessions()
        elif args.command == "message":
            client.send_message(args.session_id, " ".join(args.message))
        elif args.command == "approve-plan":
            client.approve_plan(args.session_id)
        elif args.command == "activities":
            client.get_activities(args.session_id)
        else:
            parser.print_help()
            sys.exit(1)

    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
