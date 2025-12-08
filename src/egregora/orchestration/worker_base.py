"""Base class for background workers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from egregora.orchestration.context import PipelineContext

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """Abstract base class for background workers."""

    def __init__(self, ctx: PipelineContext) -> None:
        self.ctx = ctx
        if not hasattr(ctx, "task_store") or not ctx.task_store:
            msg = "TaskStore not found in PipelineContext; it must be initialized and injected."
            raise ValueError(msg)
        self.task_store = ctx.task_store

    @abstractmethod
    def run(self) -> int:
        """Process pending tasks. Returns number of tasks processed."""
