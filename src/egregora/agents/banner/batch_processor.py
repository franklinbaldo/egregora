"""Batch banner processor for asynchronous workers.

This module keeps the V2 pipeline independent from the V3 feed-based plan by
operating on simple task payloads that mirror what the TaskStore enqueues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from egregora.agents.banner.agent import BannerInput, generate_banner
from egregora.data_primitives.document import Document

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(slots=True)
class BannerTaskEntry:
    """Task payload parsed from the TaskStore queue."""

    task_id: str
    title: str
    summary: str
    slug: str | None = None
    language: str = "pt-BR"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_banner_input(self) -> BannerInput:
        """Convert the stored payload into the synchronous BannerInput."""
        return BannerInput(
            post_title=self.title,
            post_summary=self.summary,
            slug=self.slug,
            language=self.language,
        )


class BannerGenerationResult:
    """Result of processing a single banner task."""

    def __init__(
        self,
        task: BannerTaskEntry,
        document: Document | None = None,
        error: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.task = task
        self.document = document
        self.error = error
        self.error_code = error_code

    @property
    def success(self) -> bool:
        """Return True when a banner document was produced."""
        return self.document is not None and self.error is None


class BannerBatchProcessor:
    """Process queued banner tasks by calling the sync generate_banner function."""

    def process_tasks(self, tasks: Iterable[BannerTaskEntry]) -> list[BannerGenerationResult]:
        """Process scheduled banner tasks sequentially."""
        results: list[BannerGenerationResult] = []

        for task in tasks:
            banner_input = task.to_banner_input()
            result = generate_banner(**banner_input.model_dump())

            if result.document:
                document = self._attach_task_metadata(task, result.document)
                results.append(BannerGenerationResult(task, document=document))
            else:
                results.append(
                    BannerGenerationResult(
                        task,
                        error=result.error or "Unknown error",
                        error_code=result.error_code or "GENERATION_FAILED",
                    )
                )
        return results

    def _attach_task_metadata(self, task: BannerTaskEntry, document: Document) -> Document:
        if document.metadata is None:
            document.metadata = {}

        document.metadata.setdefault("slug", task.slug)
        document.metadata.setdefault("language", task.language)
        document.metadata.setdefault("task_id", task.task_id)
        document.metadata.setdefault("generated_at", datetime.now(UTC).isoformat())
        return document
