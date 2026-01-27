"""Shared base class for orchestrator workers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol


class WorkerContext(Protocol):
    """Protocol for context required by workers."""

    @property
    def task_store(self) -> Any: ...


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
