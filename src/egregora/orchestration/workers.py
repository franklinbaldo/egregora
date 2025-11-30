"""Background workers for asynchronous task processing.

This module implements the consumer side of the async event-driven architecture.
Workers fetch tasks from the TaskStore, process them, and update their status.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from egregora.agents.banner.agent import generate_banner
from egregora.data_primitives.document import Document, DocumentType

if TYPE_CHECKING:
    from egregora.orchestration.context import PipelineContext

logger = logging.getLogger(__name__)


class BaseWorker(ABC):
    """Abstract base class for background workers."""

    def __init__(self, ctx: PipelineContext) -> None:
        self.ctx = ctx
        # Assume task_store is available on context or we get it from storage
        # Ideally it should be on context. If not, we instantiate it.
        # But we need storage manager.
        if hasattr(ctx, "task_store") and ctx.task_store:
             self.task_store = ctx.task_store
        else:
             # Fallback if not injected (though it should be)
             from egregora.database.task_store import TaskStore
             self.task_store = TaskStore(ctx.storage)

    @abstractmethod
    def run(self) -> int:
        """Process pending tasks. Returns number of tasks processed."""


class BannerWorker(BaseWorker):
    """Worker that generates banner images."""

    def run(self) -> int:
        tasks = self.task_store.fetch_pending(task_type="generate_banner")
        if not tasks:
            return 0

        logger.info("Processing %d banner generation tasks", len(tasks))
        count = 0

        for task in tasks:
            try:
                payload = task["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)

                # Extract args
                post_slug = payload["post_slug"]
                title = payload["title"]
                summary = payload["summary"]
                task.get("run_id")

                logger.info("Generating banner for %s", post_slug)

                # Execute generation (synchronous for now, but in worker thread/process conceptually)
                result = generate_banner(post_title=title, post_summary=summary, slug=post_slug)

                if result.success and result.document:
                    # Persist
                    self.ctx.output_format.persist(result.document)

                    # Chain: Enqueue enrichment if needed (e.g. image description)
                    # For now, just mark complete
                    self.task_store.mark_completed(task["task_id"])

                    # Determine web path for logging/further use
                    url_convention = self.ctx.output_format.url_convention
                    url_context = self.ctx.output_format.url_context
                    web_path = url_convention.canonical_url(result.document, url_context)
                    logger.info("Banner generated: %s", web_path)

                    # TODO: Enqueue 'enrich_media' task here if we implement chaining

                else:
                    self.task_store.mark_failed(task["task_id"], result.error or "Unknown error")

                count += 1

            except Exception as e:
                logger.exception("Error processing banner task %s", task["task_id"])
                self.task_store.mark_failed(task["task_id"], str(e))

        return count


class ProfileWorker(BaseWorker):
    """Worker that updates author profiles, with coalescing optimization."""

    def run(self) -> int:
        tasks = self.task_store.fetch_pending(task_type="update_profile", limit=1000)
        if not tasks:
            return 0

        # Group by author_uuid
        # Map: author_uuid -> list of tasks (ordered by creation time, ascending)
        author_tasks: dict[str, list[dict]] = {}
        for task in tasks:
            payload = task["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            # Attach parsed payload for convenience
            task["_parsed_payload"] = payload

            author_uuid = payload["author_uuid"]
            if author_uuid not in author_tasks:
                author_tasks[author_uuid] = []
            author_tasks[author_uuid].append(task)

        processed_count = 0

        for author_uuid, task_list in author_tasks.items():
            # If multiple tasks for same author, only execute the LAST one.
            # Mark others as superseded.

            latest_task = task_list[-1]
            superseded_tasks = task_list[:-1]

            # 1. Mark superseded
            for t in superseded_tasks:
                self.task_store.mark_superseded(
                    t["task_id"],
                    reason=f"Superseded by task {latest_task['task_id']}"
                )
                logger.info("Coalesced profile update for %s (Task %s skipped)", author_uuid, t["task_id"])

            # 2. Execute latest
            try:
                content = latest_task["_parsed_payload"]["content"]

                # Write profile
                doc = Document(
                    content=content,
                    type=DocumentType.PROFILE,
                    metadata={"uuid": author_uuid},
                    source_window="async_worker", # Or derive from task metadata if stored
                )
                self.ctx.output_format.persist(doc)

                self.task_store.mark_completed(latest_task["task_id"])
                logger.info("Updated profile for %s (Task %s)", author_uuid, latest_task["task_id"])
                processed_count += 1

            except Exception as e:
                logger.exception("Error processing profile task %s", latest_task["task_id"])
                self.task_store.mark_failed(latest_task["task_id"], str(e))

        return processed_count


class EnrichmentWorker(BaseWorker):
    """Worker for media enrichment (e.g. image description)."""

    def run(self) -> int:
        # Placeholder for enrichment logic
        # Typically fetches 'enrich_media' tasks
        return 0
