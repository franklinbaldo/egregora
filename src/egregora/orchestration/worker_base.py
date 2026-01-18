"""Shared base class for orchestrator workers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

ContextT = TypeVar("ContextT")


class BaseWorker[ContextT](ABC):
    """Abstract base for background workers that consume TaskStore jobs."""

    def __init__(self, ctx: ContextT) -> None:
        self.ctx = ctx
        task_store = getattr(ctx, "task_store", None)
        if not task_store:
            msg = "TaskStore not found in context; it must be initialized and injected."
            raise ValueError(msg)
        self.task_store = task_store

    @abstractmethod
    def run(self) -> int:
        """Process pending tasks. Returns number of tasks processed."""
