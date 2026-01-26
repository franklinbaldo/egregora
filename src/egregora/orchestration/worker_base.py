"""Shared base class for orchestrator workers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from egregora.database.task_store import TaskStore


class WorkerContext(Protocol):
    """Protocol for context required by workers."""

    @property
    def task_store(self) -> TaskStore | None: ...


class BaseWorker(ABC):
    """Abstract base for background workers that consume TaskStore jobs."""

    def __init__(self, ctx: WorkerContext) -> None:
        self.ctx = ctx
        task_store = getattr(ctx, "task_store", None)
        if not task_store:
            msg = "TaskStore not found in PipelineContext; it must be initialized and injected."
            raise ValueError(msg)
        self.task_store = task_store

    @abstractmethod
    def run(self) -> int:
        """Process pending tasks. Returns number of tasks processed."""
