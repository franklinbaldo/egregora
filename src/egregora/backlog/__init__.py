"""Backlog processing helpers with lazy imports to avoid heavy dependencies."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import-time helpers for type checkers only
    from .processor import BacklogProcessor, ProcessingResult  # noqa: F401
    from .scanner import PendingDay  # noqa: F401
    from .estimator import CostEstimate, DayEstimate  # noqa: F401
    from .checkpoint import CheckpointManager, CheckpointState  # noqa: F401


__all__ = [
    "BacklogProcessor",
    "ProcessingResult",
    "PendingDay",
    "CostEstimate",
    "DayEstimate",
    "CheckpointManager",
    "CheckpointState",
]


def __getattr__(name: str):  # pragma: no cover - dynamic loader
    if name in {"BacklogProcessor", "ProcessingResult"}:
        module = import_module("egregora.backlog.processor")
        return getattr(module, name)
    if name in {"PendingDay"}:
        module = import_module("egregora.backlog.scanner")
        return getattr(module, name)
    if name in {"CostEstimate", "DayEstimate"}:
        module = import_module("egregora.backlog.estimator")
        return getattr(module, name)
    if name in {"CheckpointManager", "CheckpointState"}:
        module = import_module("egregora.backlog.checkpoint")
        return getattr(module, name)
    raise AttributeError(name)
