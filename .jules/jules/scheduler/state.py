"""Persistent cycle state management for Jules scheduler."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TrackState:
    """State for a single execution track."""
    persona_id: str | None = None
    session_id: str | None = None
    pr_number: int | None = None
    updated_at: str | None = None


@dataclass
class PersistentCycleState:
    """Persistent state for the cycle scheduler.
    
    Supports both legacy single-cycle history and new multi-track state.
    """

    history: dict[str, dict[str, Any]] = field(default_factory=dict)
    tracks: dict[str, TrackState] = field(default_factory=dict)

    @property
    def sorted_history_keys(self) -> list[str]:
        """Get history keys sorted as integers in descending order."""
        return sorted(self.history.keys(), key=lambda x: int(x), reverse=True)

    @property
    def persona_id(self) -> str | None:
        """Get the persona ID from the most recent session (Legacy/Default)."""
        keys = self.sorted_history_keys
        return self.history[keys[0]].get("persona_id") if keys else None

    @property
    def session_id(self) -> str | None:
        """Get the session ID from the most recent session (Legacy/Default)."""
        keys = self.sorted_history_keys
        return self.history[keys[0]].get("session_id") if keys else None

    @property
    def pr_number(self) -> int | None:
        """Get the PR number from the most recent session (Legacy/Default)."""
        keys = self.sorted_history_keys
        return self.history[keys[0]].get("pr_number") if keys else None

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
                history_data = data.get("history", {})
                if isinstance(history_data, list):
                    # Convert legacy list history to dict
                    # In legacy list, history[0] was the latest.
                    # We want history["0"] to be the oldest for sequential growth.
                    state.history = {str(i): entry for i, entry in enumerate(reversed(history_data))}
                else:
                    state.history = history_data

                # Load tracks
                tracks_data = data.get("tracks", {})
                for name, t_data in tracks_data.items():
                    # Handle legacy 'last_' prefix in saved JSON if necessary
                    clean_data = {}
                    for k, v in t_data.items():
                        new_k = k.replace("last_", "")
                        clean_data[new_k] = v
                    state.tracks[name] = TrackState(**clean_data)
            elif isinstance(data, list):
                # Convert legacy list-only format to dict
                state.history = {str(i): entry for i, entry in enumerate(reversed(data))}

            return state
        except (json.JSONDecodeError, OSError, TypeError):
            return cls()

    def save(self, path: Path) -> None:
        """Save state to JSON file."""
        # Sort history by keys as integers before saving
        sorted_history = {
            k: self.history[k] 
            for k in sorted(self.history.keys(), key=lambda x: int(x))
        }
        
        data = {
            "history": sorted_history,
            "tracks": {
                name: {
                    "persona_id": t.persona_id,
                    "session_id": t.session_id,
                    "pr_number": t.pr_number,
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

        # Add to global audit history using sequential integer keys
        entry = {
            "persona_id": persona_id,
            "session_id": session_id,
            "pr_number": pr_number,
            "created_at": timestamp,
            "track": track_name
        }
        
        # Find the next sequential index
        if not self.history:
            next_idx = 0
        else:
            next_idx = max(int(k) for k in self.history.keys()) + 1
        
        self.history[str(next_idx)] = entry

        # Update track specific state
        if track_name:
            track = self.get_track(track_name)
            track.persona_id = persona_id
            track.session_id = session_id
            track.pr_number = pr_number
            track.updated_at = timestamp

    def update_pr_number(self, pr_number: int, track_name: str | None = None) -> None:
        """Update the PR number for the last session."""
        keys = self.sorted_history_keys
        if keys:
            self.history[keys[0]]["pr_number"] = pr_number

        if track_name and track_name in self.tracks:
            self.tracks[track_name].pr_number = pr_number


def commit_cycle_state(state_path: Path, message: str = "chore: update cycle state") -> bool:
    """Commit the cycle state file to git via GitHub API."""
    from jules.core.github import GitHubClient
    from jules.scheduler.legacy import JULES_BRANCH

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
