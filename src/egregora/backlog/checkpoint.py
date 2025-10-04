"""Checkpoint helpers to persist backlog processing progress."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(slots=True)
class CheckpointState:
    """Serializable state stored between batch executions."""

    last_processed_date: Optional[str] = None
    total_processed: int = 0
    total_pending: int = 0
    started_at: Optional[str] = None
    last_updated: Optional[str] = None
    failed_dates: list[str] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_updated = datetime.now(timezone.utc).isoformat()
        if self.started_at is None:
            self.started_at = self.last_updated


class CheckpointManager:
    """Read and write :class:`CheckpointState` objects from disk."""

    def __init__(self, path: Path, *, backup: bool = True) -> None:
        self.path = path
        self.backup = backup
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> CheckpointState:
        if not self.path.exists():
            return CheckpointState()

        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except json.JSONDecodeError:
            backup_path = self.path.with_suffix(self.path.suffix + ".corrupted")
            self.path.rename(backup_path)
            return CheckpointState()

        if not isinstance(data, dict):
            return CheckpointState()

        state = CheckpointState()
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state

    def save(self, state: CheckpointState) -> None:
        state.touch()
        payload = json.dumps(asdict(state), indent=2, ensure_ascii=False)

        if self.backup and self.path.exists():
            backup_path = self.path.with_suffix(self.path.suffix + ".bak")
            self.path.replace(backup_path)

        self.path.write_text(payload, encoding="utf-8")


__all__ = ["CheckpointManager", "CheckpointState"]
