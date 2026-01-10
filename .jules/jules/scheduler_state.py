"""Persistent cycle state management for Jules scheduler."""

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class CycleStateEntry:
    """Entry in cycle history."""
    
    persona_id: str
    session_id: str
    pr_number: int | None
    created_at: str


@dataclass
class PersistentCycleState:
    """Persistent state for the cycle scheduler."""
    
    last_persona_id: str | None = None
    last_persona_index: int = 0
    last_session_id: str | None = None
    last_pr_number: int | None = None
    updated_at: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)
    
    @classmethod
    def load(cls, path: Path) -> "PersistentCycleState":
        """Load state from JSON file."""
        if not path.exists():
            return cls()
        
        try:
            with open(path) as f:
                data = json.load(f)
            return cls(
                last_persona_id=data.get("last_persona_id"),
                last_persona_index=data.get("last_persona_index", 0),
                last_session_id=data.get("last_session_id"),
                last_pr_number=data.get("last_pr_number"),
                updated_at=data.get("updated_at", ""),
                history=data.get("history", []),
            )
        except (json.JSONDecodeError, OSError):
            return cls()
    
    def save(self, path: Path) -> None:
        """Save state to JSON file."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)
    
    def record_session(
        self,
        persona_id: str,
        persona_index: int,
        session_id: str,
        pr_number: int | None = None,
    ) -> None:
        """Record a new session in state."""
        self.last_persona_id = persona_id
        self.last_persona_index = persona_index
        self.last_session_id = session_id
        self.last_pr_number = pr_number
        
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
        self.last_pr_number = pr_number
        if self.history:
            self.history[0]["pr_number"] = pr_number


def commit_cycle_state(state_path: Path, message: str = "chore: update cycle state") -> bool:
    """Commit the cycle state file to git.
    
    Args:
        state_path: Path to the state file
        message: Commit message
        
    Returns:
        True if commit succeeded, False otherwise
    """
    try:
        # Configure git user (for CI)
        subprocess.run(
            ["git", "config", "user.name", "Jules Bot"],
            check=False,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "jules-bot@google.com"],
            check=False,
            capture_output=True,
        )
        
        # Pull latest changes first
        subprocess.run(
            ["git", "pull", "--rebase", "origin", "main"],
            check=False,  # Don't fail if nothing to pull
            capture_output=True,
        )
        
        subprocess.run(
            ["git", "add", str(state_path)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", "main"],
            check=True,
            capture_output=True,
        )
        print(f"✅ Committed cycle state: {message}")
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else ""
        print(f"⚠️ Failed to commit cycle state: {stderr}")
        return False
