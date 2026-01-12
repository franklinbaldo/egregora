"""Persistent cycle state management for Jules scheduler."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class PersistentCycleState:
    """Persistent state for the cycle scheduler.
    
    Simplified to only store history. Last session info is derived from history.
    """

    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def last_persona_id(self) -> str | None:
        """Get the persona ID from the most recent session."""
        return self.history[0].get("persona_id") if self.history else None

    @property
    def last_session_id(self) -> str | None:
        """Get the session ID from the most recent session."""
        return self.history[0].get("session_id") if self.history else None

    @property
    def last_pr_number(self) -> int | None:
        """Get the PR number from the most recent session."""
        return self.history[0].get("pr_number") if self.history else None

    @classmethod
    def load(cls, path: Path) -> "PersistentCycleState":
        """Load state from JSON file."""
        if not path.exists():
            return cls()

        try:
            with open(path) as f:
                data = json.load(f)
            
            # Handle legacy format if necessary
            if isinstance(data, dict) and "history" in data:
                return cls(history=data.get("history", []))
            elif isinstance(data, list):
                return cls(history=data)
            else:
                return cls()
        except (json.JSONDecodeError, OSError):
            return cls()

    def save(self, path: Path) -> None:
        """Save state to JSON file, keeping only the history key."""
        with open(path, "w") as f:
            json.dump({"history": self.history}, f, indent=2)

    def record_session(
        self,
        persona_id: str,
        persona_index: int,
        session_id: str,
        pr_number: int | None = None,
    ) -> None:
        """Record a new session in state."""
        # Add to history (keep full audit trail)
        entry = {
            "persona_id": persona_id,
            "session_id": session_id,
            "pr_number": pr_number,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.history.insert(0, entry)

    def update_pr_number(self, pr_number: int) -> None:
        """Update the PR number for the last session."""
        if self.history:
            self.history[0]["pr_number"] = pr_number


def commit_cycle_state(state_path: Path, message: str = "chore: update cycle state") -> bool:
    """Commit the cycle state file to git via GitHub API.

    This updates the state ONLY in the 'jules' branch as requested.
    Using the API is more reliable than 'git push' in CI.
    """
    from jules.github import GitHubClient
    from jules.scheduler import JULES_BRANCH

    client = GitHubClient()
    if not client.token:
        print("⚠️ No GITHUB_TOKEN found, skipping remote state persistence.")
        return False

    owner = "franklinbaldo"
    repo = "egregora"
    path = ".jules/cycle_state.json"

    try:
        with open(state_path) as f:
            content = f.read()

        # Update ONLY the jules branch
        branch = JULES_BRANCH
        
        # Get current file info for SHA
        file_info = client.get_file_contents(owner, repo, path, ref=branch)
        sha = file_info.get("sha") if file_info else None

        if client.create_or_update_file(
            owner=owner,
            repo=repo,
            path=path,
            content=content,
            message=message,
            branch=branch,
            sha=sha
        ):
            print(f"✅ Updated cycle state on branch '{branch}' via API")
            return True
        else:
            print(f"⚠️ Failed to update cycle state on branch '{branch}'")
            return False

    except Exception as e:
        print(f"❌ Error persisting cycle state via API: {e}")
        return False
