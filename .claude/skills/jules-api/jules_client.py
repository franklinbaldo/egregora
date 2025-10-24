#!/usr/bin/env python3
"""
Jules API Client Helper
A simple Python client for interacting with Google's Jules API.
"""

import json
import os
import subprocess
import sys
from typing import Optional, Dict, Any
import requests


class JulesClient:
    """Client for Google Jules API."""

    BASE_URL = "https://jules.googleapis.com/v1alpha"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Jules client.

        Args:
            api_key: Jules API key. If not provided, will check JULES_API_KEY
                     environment variable, then fall back to gcloud auth.
        """
        self.api_key = api_key or os.environ.get('JULES_API_KEY')
        self.access_token = None
        self.using_oauth = False  # Track if we're using OAuth vs API key

    def _get_access_token(self) -> str:
        """Get authentication token - either API key or gcloud token."""
        # If API key is provided, use it directly
        if self.api_key:
            self.using_oauth = False
            return self.api_key

        # Otherwise fall back to cached token or gcloud
        if self.access_token:
            return self.access_token

        try:
            result = subprocess.run(
                ['gcloud', 'auth', 'print-access-token'],
                capture_output=True,
                text=True,
                check=True
            )
            self.access_token = result.stdout.strip()
            self.using_oauth = True  # Mark that we're using OAuth
            return self.access_token
        except subprocess.CalledProcessError as e:
            raise Exception(
                "Failed to get access token. Make sure you either:\n"
                "1. Set JULES_API_KEY environment variable, or\n"
                "2. Authenticate with gcloud: gcloud auth login"
            ) from e

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        token = self._get_access_token()

        # Use correct header based on auth type
        if self.using_oauth:
            # OAuth tokens from gcloud use Authorization: Bearer
            return {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
        else:
            # API keys use X-Goog-Api-Key
            return {
                'X-Goog-Api-Key': token,
                'Content-Type': 'application/json'
            }

    def create_session(
        self,
        prompt: str,
        owner: str,
        repo: str,
        branch: str = 'main',
        title: Optional[str] = None,
        require_plan_approval: bool = False,
        automation_mode: str = 'AUTO_CREATE_PR'
    ) -> Dict[str, Any]:
        """
        Create a new Jules session.

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
        url = f"{self.BASE_URL}/sessions"
        data = {
            'prompt': prompt,
            'sourceContext': {
                'source': f'sources/github/{owner}/{repo}',
                'githubRepoContext': {
                    'startingBranch': branch
                }
            },
            'automationMode': automation_mode
        }

        if title:
            data['title'] = title

        if require_plan_approval:
            data['requirePlanApproval'] = require_plan_approval

        response = requests.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return response.json()

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Get details of a specific session.

        Args:
            session_id: The session ID

        Returns:
            Session object
        """
        url = f"{self.BASE_URL}/sessions/{session_id}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def list_sessions(self) -> Dict[str, Any]:
        """
        List all sessions.

        Returns:
            List of session objects
        """
        url = f"{self.BASE_URL}/sessions"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def send_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """
        Send a message to an active session.

        Args:
            session_id: The session ID
            message: Message content

        Returns:
            Updated session object
        """
        url = f"{self.BASE_URL}/sessions/{session_id}:sendMessage"
        data = {'message': message}
        response = requests.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return response.json()

    def approve_plan(self, session_id: str) -> Dict[str, Any]:
        """
        Approve a plan for a session.

        Args:
            session_id: The session ID

        Returns:
            Updated session object
        """
        url = f"{self.BASE_URL}/sessions/{session_id}:approvePlan"
        response = requests.post(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_activities(self, session_id: str) -> Dict[str, Any]:
        """
        Get activities for a session.

        Args:
            session_id: The session ID

        Returns:
            List of activity objects
        """
        url = f"{self.BASE_URL}/sessions/{session_id}/activities"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()


def main():
    """CLI interface for Jules API."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python jules_client.py create <prompt> <owner> <repo> [branch]")
        print("  python jules_client.py get <session_id>")
        print("  python jules_client.py list")
        print("  python jules_client.py message <session_id> <message>")
        print("  python jules_client.py approve <session_id>")
        print("  python jules_client.py activities <session_id>")
        sys.exit(1)

    client = JulesClient()
    command = sys.argv[1]

    try:
        if command == 'create':
            if len(sys.argv) < 5:
                print("Usage: python jules_client.py create <prompt> <owner> <repo> [branch]")
                sys.exit(1)
            prompt = sys.argv[2]
            owner = sys.argv[3]
            repo = sys.argv[4]
            branch = sys.argv[5] if len(sys.argv) > 5 else 'main'

            result = client.create_session(prompt, owner, repo, branch)
            print(json.dumps(result, indent=2))

        elif command == 'get':
            if len(sys.argv) < 3:
                print("Usage: python jules_client.py get <session_id>")
                sys.exit(1)
            session_id = sys.argv[2]
            result = client.get_session(session_id)
            print(json.dumps(result, indent=2))

        elif command == 'list':
            result = client.list_sessions()
            print(json.dumps(result, indent=2))

        elif command == 'message':
            if len(sys.argv) < 4:
                print("Usage: python jules_client.py message <session_id> <message>")
                sys.exit(1)
            session_id = sys.argv[2]
            message = ' '.join(sys.argv[3:])
            result = client.send_message(session_id, message)
            print(json.dumps(result, indent=2))

        elif command == 'approve':
            if len(sys.argv) < 3:
                print("Usage: python jules_client.py approve <session_id>")
                sys.exit(1)
            session_id = sys.argv[2]
            result = client.approve_plan(session_id)
            print(json.dumps(result, indent=2))

        elif command == 'activities':
            if len(sys.argv) < 3:
                print("Usage: python jules_client.py activities <session_id>")
                sys.exit(1)
            session_id = sys.argv[2]
            result = client.get_activities(session_id)
            print(json.dumps(result, indent=2))

        else:
            print(f"Unknown command: {command}")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
