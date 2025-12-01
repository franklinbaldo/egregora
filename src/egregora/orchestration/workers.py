"""Background workers for asynchronous task processing.

This module implements the consumer side of the async event-driven architecture.
Workers fetch tasks from the TaskStore, process them, and update their status.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from egregora.agents.banner.agent import generate_banner
from egregora.orchestration.persistence import persist_banner_document, persist_profile_document

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

                # Execute generation
                result = generate_banner(post_title=title, post_summary=summary, slug=post_slug)

                if result.success and result.document:
                    # Persist using shared helper
                    web_path = persist_banner_document(self.ctx.output_format, result.document)

                    self.task_store.mark_completed(task["task_id"])
                    logger.info("Banner generated: %s", web_path)

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
                    t["task_id"], reason=f"Superseded by task {latest_task['task_id']}"
                )
                logger.info("Coalesced profile update for %s (Task %s skipped)", author_uuid, t["task_id"])

            # 2. Execute latest
            try:
                content = latest_task["_parsed_payload"]["content"]

                # Write profile using shared helper
                persist_profile_document(
                    self.ctx.output_format,
                    author_uuid,
                    content,
                    source_window="async_worker",
                )

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
        """Process pending enrichment tasks in batches."""
        # Configurable batch size
        batch_size = 50
        tasks = self.task_store.fetch_pending(task_type="enrich_url", limit=batch_size)
        media_tasks = self.task_store.fetch_pending(task_type="enrich_media", limit=batch_size)

        processed_count = 0

        if tasks:
            processed_count += self._process_url_batch(tasks)

        if media_tasks:
            processed_count += self._process_media_batch(media_tasks)

        return processed_count

    def _process_url_batch(self, tasks: list[dict[str, Any]]) -> int:
        from concurrent.futures import ThreadPoolExecutor

        from egregora.agents.enricher import (
            create_enrichment_row,
            create_url_enrichment_agent,
            normalize_slug,
            run_url_enrichment,
        )
        from egregora.data_primitives.document import Document, DocumentType

        # Prepare task data
        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None

        # Create a single agent instance to reuse (it's stateless except config)
        url_model = self.ctx.config.models.enricher
        agent = create_url_enrichment_agent(url_model)

        def process_single_task(task: dict[str, Any]) -> tuple[dict, Any | None, str | None]:
            try:
                payload = task["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                # Attach parsed for later use
                task["_parsed_payload"] = payload

                url = payload["url"]

                # Execute logic
                output, usage = run_url_enrichment(
                    agent,
                    url,
                    prompts_dir,
                    pii_prevention=None,  # Could pass from context if available
                )

                # Record usage (thread-safe?)
                # UsageTracker might need lock if shared
                # For simplicity, we aggregate or ignore in worker for now, or assume it's thread-safe
                if self.ctx.usage_tracker:
                    self.ctx.usage_tracker.record(usage)

                return task, output, None
            except Exception as e:
                logger.error("Error processing URL task %s: %s", task["task_id"], e)
                return task, None, str(e)

        max_concurrent = getattr(self.ctx.config.enrichment, "max_concurrent_enrichments", 5)
        logger.info(
            "Processing %d enrichment tasks with max concurrency of %d (ThreadPool)",
            len(tasks),
            max_concurrent,
        )

        results = []
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            results = list(executor.map(process_single_task, tasks))

        # Process results and create documents (Main thread)
        success_count = 0
        new_rows = []

        for task, output, error in results:
            if error:
                self.task_store.mark_failed(task["task_id"], error)
                continue

            if not output:
                # Should have error if None, but defensive check
                continue

            try:
                payload = task["_parsed_payload"]
                url = payload["url"]
                slug_value = normalize_slug(output.slug, url)

                doc = Document(
                    content=output.markdown,
                    type=DocumentType.ENRICHMENT_URL,
                    metadata={
                        "url": url,
                        "slug": slug_value,
                        "nav_exclude": True,
                        "hide": ["navigation"],
                    },
                )
                self.ctx.output_format.persist(doc)

                # Create DB row
                metadata = payload["message_metadata"]
                row = create_enrichment_row(metadata, "URL", url, doc.document_id)
                if row:
                    new_rows.append(row)

                self.task_store.mark_completed(task["task_id"])
                success_count += 1
            except Exception as e:
                logger.error("Failed to persist enrichment for %s: %s", task["task_id"], e)
                self.task_store.mark_failed(task["task_id"], f"Persistence error: {e!s}")

        # Insert rows into DB
        if new_rows:
            try:
                self.ctx.storage.ibis_conn.insert("messages", new_rows)
                logger.info("Inserted %d enrichment rows", len(new_rows))
            except Exception as e:
                logger.error("Failed to insert enrichment rows: %s", e)

        return success_count

    def _process_media_batch(self, tasks: list[dict[str, Any]]) -> int:
        from concurrent.futures import ThreadPoolExecutor

        from egregora.agents.enricher import (
            create_enrichment_row,
            create_media_enrichment_agent,
            normalize_slug,
            run_media_enrichment,
        )
        from egregora.data_primitives.document import Document, DocumentType

        prompts_dir = self.ctx.site_root / ".egregora" / "prompts" if self.ctx.site_root else None
        vision_model = self.ctx.config.models.enricher_vision
        agent = create_media_enrichment_agent(vision_model)

        def process_single_task(task: dict[str, Any]) -> tuple[dict, Any | None, str | None]:
            try:
                payload = task["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                task["_parsed_payload"] = payload

                filename = payload["filename"]
                media_type = payload["media_type"]
                suggested_path = payload.get("suggested_path")

                # Resolve file path
                file_path = None
                if suggested_path:
                    full_path = self.ctx.output_dir / suggested_path
                    if full_path.exists():
                        file_path = full_path

                if not file_path or not file_path.exists():
                    return task, None, "Media file not found"

                output, usage = run_media_enrichment(
                    agent,
                    filename=filename,
                    mime_hint=media_type,
                    prompts_dir=prompts_dir,
                    file_path=file_path,
                    pii_prevention=None,
                )

                if self.ctx.usage_tracker:
                    self.ctx.usage_tracker.record(usage)

                return task, output, None

            except Exception as e:
                logger.error("Error processing media task %s: %s", task["task_id"], e)
                return task, None, str(e)

        max_concurrent = getattr(self.ctx.config.enrichment, "max_concurrent_enrichments", 5)

        results = []
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            results = list(executor.map(process_single_task, tasks))

        success_count = 0
        new_rows = []

        for task, output, error in results:
            if error:
                self.task_store.mark_failed(task["task_id"], error)
                continue

            if not output:
                continue

            try:
                payload = task["_parsed_payload"]
                filename = payload["filename"]
                media_type = payload["media_type"]

                slug_value = normalize_slug(output.slug, filename)

                enrichment_metadata = {
                    "filename": filename,
                    "media_type": media_type,
                    "parent_path": payload.get("suggested_path"),
                    "slug": slug_value,
                    "nav_exclude": True,
                    "hide": ["navigation"],
                }

                doc = Document(
                    content=output.markdown,
                    type=DocumentType.ENRICHMENT_MEDIA,
                    metadata=enrichment_metadata,
                )
                self.ctx.output_format.persist(doc)

                # Create DB row
                metadata = payload["message_metadata"]
                row = create_enrichment_row(metadata, "Media", filename, doc.document_id)
                if row:
                    new_rows.append(row)

                self.task_store.mark_completed(task["task_id"])
                success_count += 1

            except Exception as e:
                logger.error("Failed to persist media enrichment for %s: %s", task["task_id"], e)
                self.task_store.mark_failed(task["task_id"], f"Persistence error: {e!s}")

        if new_rows:
            try:
                self.ctx.storage.ibis_conn.insert("messages", new_rows)
                logger.info("Inserted %d media enrichment rows", len(new_rows))
            except Exception as e:
                logger.error("Failed to insert media enrichment rows: %s", e)

        return success_count
