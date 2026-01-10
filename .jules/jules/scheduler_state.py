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
    
    This ensures the state is persisted in the 'main' branch, which is the 
    canonical source of truth. The 'jules' branch will receive this update 
    during the sync_with_main() step at the start of each tick.
    """
    try:
        # Configure git user (for CI)
        print(f"[{datetime.now().isoformat()}] Preparing to persist slate to main...")
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
        
        # 1. Fetch latest main
        subprocess.run(["git", "fetch", "origin", "main"], check=True, capture_output=True)
        
        # 2. Add the file
        subprocess.run(["git", "add", str(state_path)], check=True, capture_output=True)
        
        # 3. Check for changes
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not status.stdout.strip():
            print("ℹ️ No changes to commit in cycle_state.json")
            return True

        # 4. Commit
        subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True)
        
        # 5. Push using explicit refspec to handle detached HEAD
        print(f"Pushing cycle state to origin main (HEAD:main)...")
        # Try pushing up to 3 times with rebase if needed
        for attempt in range(3):
            try:
                subprocess.run(["git", "push", "origin", "HEAD:main"], check=True, capture_output=True, text=True)
                print(f"✅ State persisted successfully: {message}")
                return True
            except subprocess.CalledProcessError as e:
                print(f"⚠️ Push attempt {attempt+1} failed. Rebasin and retrying...")
                subprocess.run(["git", "fetch", "origin", "main"], check=True)
                subprocess.run(["git", "rebase", "origin/main"], check=False)
        
        return False
    except Exception as e:
        print(f"❌ Error persisting cycle state: {e}")
        return False
