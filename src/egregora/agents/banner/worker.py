"""Asynchronous worker for banner generation."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, cast

from egregora.agents.banner.batch_processor import BannerBatchProcessor, BannerTaskEntry
from egregora.agents.exceptions import (
    BannerError,
    BannerTaskDataError,
    BannerTaskPayloadError,
)
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
            try:
                entry = self._parse_task(task)
                parsed_tasks.append(entry)
            except BannerError as e:
                logger.warning("Invalid banner task %s: %s", task.get("task_id", "N/A"), e)
                invalid += 1
                continue

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
                # Cast to PipelineContext to access output_sink which is not in WorkerContext protocol
                ctx = cast("PipelineContext", self.ctx)
                web_path = persist_banner_document(ctx.output_sink, result.document)
                logger.info("Banner generated for %s -> %s", task_id, web_path)
                self.task_store.mark_completed(task_id)
            else:
                error_message = result.error or "Banner generation failed"
                logger.warning("Banner task %s failed: %s", task_id, error_message)
                self.task_store.mark_failed(task_id, error_message)

        return processed + invalid

    def _parse_task(self, task: dict[str, Any]) -> BannerTaskEntry:
        task_id = str(task.get("task_id", ""))
        raw_payload = task.get("payload")

        if not raw_payload:
            self.task_store.mark_failed(task_id, "Missing payload")
            raise BannerTaskPayloadError(task_id, "Missing payload")

        payload = raw_payload
        if isinstance(raw_payload, str):
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError as exc:
                self.task_store.mark_failed(task_id, "Invalid payload JSON")
                raise BannerTaskPayloadError(task_id, "Invalid payload JSON") from exc

        post_slug = payload.get("post_slug")
        title = payload.get("title")

        missing_fields = []
        if not post_slug:
            missing_fields.append("post_slug")
        if not title:
            missing_fields.append("title")

        if missing_fields:
            self.task_store.mark_failed(task_id, "Missing slug/title")
            raise BannerTaskDataError(task_id, missing_fields)

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
