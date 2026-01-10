"""Track active reconciliation sessions to avoid duplicates."""

import json
from pathlib import Path
from datetime import datetime, timezone


class ReconciliationTracker:
    """Tracks active reconciliation sessions."""

    STATE_FILE = Path(".jules/state/reconciliation.json")

    def __init__(self):
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def is_reconciliation_active(self, sprint_number: int) -> bool:
        """Check if reconciliation is already running for this sprint."""
        if not self.STATE_FILE.exists():
            return False

        try:
            with open(self.STATE_FILE, "r") as f:
                state = json.load(f)
            return state.get("sprint") == sprint_number and state.get("status") == "active"
        except (json.JSONDecodeError, ValueError):
            return False

    def mark_reconciliation_active(self, sprint_number: int, session_id: str, pr_number: int):
        """Mark reconciliation as active."""
        state = {
            "sprint": sprint_number,
            "session_id": session_id,
            "pr_number": pr_number,
            "status": "active",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def mark_reconciliation_complete(self):
        """Mark reconciliation as complete."""
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE, "r") as f:
                    state = json.load(f)
                state["status"] = "completed"
                state["completed_at"] = datetime.now(timezone.utc).isoformat()
                with open(self.STATE_FILE, "w") as f:
                    json.dump(state, f, indent=2)
            except (json.JSONDecodeError, ValueError):
                pass
