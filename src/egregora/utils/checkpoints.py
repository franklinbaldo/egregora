"""Checkpoint storage for resumable pipeline runs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

logger = logging.getLogger(__name__)

DEFAULT_STEP_ORDER = ("enrichment", "writing", "profiles", "rag")


def _default_checkpoint(period: str) -> dict[str, Any]:
    return {
        "period": period,
        "steps": dict.fromkeys(DEFAULT_STEP_ORDER, "pending"),
        "timestamp": None,
    }


@dataclass(slots=True)
class CheckpointStore:
    """Manage per-period checkpoints under ``output_dir/.egregora``."""

    root: Path
    step_order: tuple[str, ...] = field(default_factory=lambda: DEFAULT_STEP_ORDER)

    def __post_init__(self) -> None:
        resolved = self.root.expanduser()
        resolved.mkdir(parents=True, exist_ok=True)
        self.root = resolved
        logger.debug("Checkpoint store initialized at %s", self.root)

    def path_for_period(
        self,
        period: Annotated[str, "The period identifier, e.g., '2024-01-01'"],
    ) -> Annotated[Path, "The full path to the checkpoint file"]:
        return self.root / f"{period}.json"

    def load(
        self,
        period: Annotated[str, "The period identifier to load"],
    ) -> Annotated[dict[str, Any], "The loaded or default checkpoint data"]:
        """Load checkpoint data or return default structure."""
        path = self.path_for_period(period)
        if not path.exists():
            return _default_checkpoint(period)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Checkpoint file corrupted, resetting: %s", path)
            return _default_checkpoint(period)

        # Ensure required keys exist
        data.setdefault("period", period)
        steps = data.setdefault("steps", {})
        for step in self.step_order:
            steps.setdefault(step, "pending")

        return data

    def save(
        self,
        period: Annotated[str, "The period identifier to save"],
        data: Annotated[dict[str, Any], "The checkpoint data to save"],
    ) -> None:
        """Persist checkpoint to disk."""
        path = self.path_for_period(period)
        data = dict(data)  # shallow copy
        data["period"] = period
        data.setdefault("steps", {})
        data["timestamp"] = datetime.now(UTC).isoformat()

        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)
        logger.debug("Checkpoint saved: %s", path)

    def update_step(
        self,
        period: Annotated[str, "The period identifier to update"],
        step: Annotated[str, "The pipeline step to update"],
        status: Annotated[str, "The new status for the step"],
    ) -> Annotated[dict[str, Any], "The updated checkpoint data"]:
        """Update status for ``step`` and persist changes."""
        data = self.load(period)
        data.setdefault("steps", {})
        data["steps"][step] = status
        self.save(period, data)
        return data

    def clear(self, period: Annotated[str, "The period identifier to clear"]) -> None:
        """Remove checkpoint for ``period`` if present."""
        path = self.path_for_period(period)
        try:
            path.unlink()
            logger.debug("Checkpoint cleared: %s", path)
        except FileNotFoundError:
            return
        except OSError:
            logger.debug("Failed to delete checkpoint: %s", path, exc_info=True)
