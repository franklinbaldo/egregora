"""Jules API Client."""

import os
import subprocess
from typing import Any, Optional

import requests
from pydantic import BaseModel, ConfigDict


class JulesSession(BaseModel):
    """Jules Session Model."""
    model_config = ConfigDict(extra="ignore")
    
    name: str  # sessions/UUID
    state: str
    createTime: str


class JulesClient:
    """Client for Google Jules API."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        """Initialize the Jules client."""
        self.api_key = api_key or os.environ.get("JULES_API_KEY")
        self.base_url = base_url or os.environ.get("JULES_BASE_URL", "https://jules.googleapis.com/v1alpha")
        self.access_token: Optional[str] = None

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Goog-Api-Key"] = self.api_key
        else:
            if not self.access_token:
                try:
                    # Fallback to gcloud if available (dev environment)
                    result = subprocess.run(
                        ["gcloud", "auth", "print-access-token"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    self.access_token = result.stdout.strip()
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Should ideally use google-auth, but keeping gcloud fallback for now
                    # or raise informative error
                    msg = "JULES_API_KEY not set and gcloud auth failed."
                    raise ValueError(msg)
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def create_session(
        self,
        prompt: str,
        owner: str,
        repo: str,
        branch: str = "main",
        title: Optional[str] = None,
        require_plan_approval: bool = False,
        automation_mode: str = "AUTO_CREATE_PR",
    ) -> dict[str, Any]:
        """Create a new Jules session."""
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
        """Get details of a specific session."""
        # Sanitize session_id if it's full resource name
        if session_id.startswith("sessions/"):
            session_id = session_id.split("/")[-1]
            
        url = f"{self.base_url}/sessions/{session_id}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def list_sessions(self) -> dict[str, Any]:
        """List all sessions."""
        url = f"{self.base_url}/sessions"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def send_message(self, session_id: str, message: str) -> dict[str, Any]:
        """Send a message to an active session."""
        if session_id.startswith("sessions/"):
            session_id = session_id.split("/")[-1]
            
        url = f"{self.base_url}/sessions/{session_id}:sendMessage"
        data = {"message": message}
        response = requests.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        return response.json()

    def approve_plan(self, session_id: str) -> dict[str, Any]:
        """Approve a plan for a session."""
        if session_id.startswith("sessions/"):
            session_id = session_id.split("/")[-1]
            
        url = f"{self.base_url}/sessions/{session_id}:approvePlan"
        response = requests.post(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_activities(self, session_id: str) -> dict[str, Any]:
        """Get activities for a session."""
        if session_id.startswith("sessions/"):
            session_id = session_id.split("/")[-1]

        url = f"{self.base_url}/sessions/{session_id}/activities"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
