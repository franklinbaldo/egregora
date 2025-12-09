"""Asynchronous worker for banner generation."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from egregora.agents.banner.batch_processor import BannerBatchProcessor, BannerTaskEntry
from egregora.orchestration.persistence import persist_banner_document
from egregora.orchestration.worker_base import BaseWorker

if TYPE_CHECKING:
    from egregora.orchestration.context import PipelineContext

logger = logging.getLogger(__name__)


class BannerWorker(BaseWorker):
    """Worker that generates banner images using the banner batch processor."""

    def __init__(self, ctx: PipelineContext) -> None:
        super().__init__(ctx)
        self.generator = BannerBatchProcessor()

    def run(self) -> int:
        tasks = self.task_store.fetch_pending(task_type="generate_banner")
        if not tasks:
            return 0

        parsed_tasks: list[BannerTaskEntry] = []
        invalid = 0

        for task in tasks:
            entry = self._parse_task(task)
            if entry is None:
                invalid += 1
                continue
            parsed_tasks.append(entry)

        if not parsed_tasks:
            return invalid

        logger.info(
            "Processing %d banner tasks (invalid: %d)",
            len(parsed_tasks),
            invalid,
        )

        results = self.generator.process_tasks(parsed_tasks)

        processed = 0
        for result in results:
            processed += 1
            task_id = result.task.task_id

            if result.success and result.document:
                web_path = persist_banner_document(self.ctx.output_format, result.document)
                logger.info("Banner generated for %s -> %s", task_id, web_path)
                self.task_store.mark_completed(task_id)
            else:
                error_message = result.error or "Banner generation failed"
                logger.warning("Banner task %s failed: %s", task_id, error_message)
                self.task_store.mark_failed(task_id, error_message)

        return processed + invalid

    def _parse_task(self, task: dict[str, Any]) -> BannerTaskEntry | None:
        task_id = str(task.get("task_id", ""))
        raw_payload = task.get("payload")

        if not raw_payload:
            logger.warning("Task %s missing payload", task_id)
            self.task_store.mark_failed(task.get("task_id"), "Missing payload")
            return None

        payload = raw_payload
        if isinstance(raw_payload, str):
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError as exc:
                logger.warning("Invalid banner payload for %s: %s", task_id, exc)
                self.task_store.mark_failed(task.get("task_id"), "Invalid payload JSON")
                return None

        post_slug = payload.get("post_slug")
        title = payload.get("title")

        if not post_slug or not title:
            logger.warning("Banner task %s missing slug/title", task_id)
            self.task_store.mark_failed(task.get("task_id"), "Missing slug/title")
            return None

        summary = payload.get("summary") or ""
        language = payload.get("language") or "pt-BR"
        metadata = {}
        if payload.get("run_id"):
            metadata["run_id"] = payload["run_id"]

        return BannerTaskEntry(
            task_id=task_id,
            title=title,
            summary=summary,
            slug=post_slug,
            language=language,
            metadata=metadata,
        )
