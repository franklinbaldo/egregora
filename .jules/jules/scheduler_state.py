"""Persistent cycle state management for Jules scheduler."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TrackState:
    """State for a single execution track."""
    last_persona_id: str | None = None
    last_session_id: str | None = None
    last_pr_number: int | None = None
    updated_at: str | None = None


@dataclass
class PersistentCycleState:
    """Persistent state for the cycle scheduler.
    
    Supports both legacy single-cycle history and new multi-track state.
    """

    history: list[dict[str, Any]] = field(default_factory=list)
    tracks: dict[str, TrackState] = field(default_factory=dict)

    @property
    def last_persona_id(self) -> str | None:
        """Get the persona ID from the most recent session (Legacy/Default)."""
        return self.history[0].get("persona_id") if self.history else None

    @property
    def last_session_id(self) -> str | None:
        """Get the session ID from the most recent session (Legacy/Default)."""
        return self.history[0].get("session_id") if self.history else None

    @property
    def last_pr_number(self) -> int | None:
        """Get the PR number from the most recent session (Legacy/Default)."""
        return self.history[0].get("pr_number") if self.history else None

    def get_track(self, track_name: str) -> TrackState:
        """Get state for a specific track, initializing if needed."""
        if track_name not in self.tracks:
            self.tracks[track_name] = TrackState()
        return self.tracks[track_name]

    @classmethod
    def load(cls, path: Path) -> "PersistentCycleState":
        """Load state from JSON file."""
        if not path.exists():
            return cls()

        try:
            with open(path) as f:
                data = json.load(f)
            
            state = cls()

            # Load history
            if isinstance(data, dict):
                state.history = data.get("history", [])

                # Load tracks
                tracks_data = data.get("tracks", {})
                for name, t_data in tracks_data.items():
                    state.tracks[name] = TrackState(**t_data)
            elif isinstance(data, list):
                state.history = data

            return state
        except (json.JSONDecodeError, OSError, TypeError):
            return cls()

    def save(self, path: Path) -> None:
        """Save state to JSON file."""
        data = {
            "history": self.history,
            "tracks": {
                name: {
                    "last_persona_id": t.last_persona_id,
                    "last_session_id": t.last_session_id,
                    "last_pr_number": t.last_pr_number,
                    "updated_at": t.updated_at
                }
                for name, t in self.tracks.items()
            }
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def record_session(
        self,
        persona_id: str,
        persona_index: int,
        session_id: str,
        pr_number: int | None = None,
        track_name: str | None = None,
    ) -> None:
        """Record a new session in state."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # Add to global audit history
        entry = {
            "persona_id": persona_id,
            "session_id": session_id,
            "pr_number": pr_number,
            "created_at": timestamp,
            "track": track_name
        }
        self.history.insert(0, entry)

        # Update track specific state
        if track_name:
            track = self.get_track(track_name)
            track.last_persona_id = persona_id
            track.last_session_id = session_id
            track.last_pr_number = pr_number
            track.updated_at = timestamp

    def update_pr_number(self, pr_number: int, track_name: str | None = None) -> None:
        """Update the PR number for the last session."""
        if self.history:
            self.history[0]["pr_number"] = pr_number

        if track_name and track_name in self.tracks:
            self.tracks[track_name].last_pr_number = pr_number


def commit_cycle_state(state_path: Path, message: str = "chore: update cycle state") -> bool:
    """Commit the cycle state file to git via GitHub API."""
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
