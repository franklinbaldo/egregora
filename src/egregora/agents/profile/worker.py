"""Background worker for profile updates."""

from __future__ import annotations

import json
import logging
from typing import Any

from egregora.orchestration.persistence import persist_profile_document
from egregora.orchestration.worker_base import BaseWorker

logger = logging.getLogger(__name__)


class ProfileWorker(BaseWorker):
    """Worker that updates author profiles, with coalescing optimization."""

    def run(self) -> int:
        tasks = self.task_store.fetch_pending(task_type="update_profile", limit=1000)
        if not tasks:
            return 0

        author_tasks: dict[str, list[dict[str, Any]]] = {}
        for task in tasks:
            payload = task["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            task["_parsed_payload"] = payload

            author_uuid = payload["author_uuid"]
            author_tasks.setdefault(author_uuid, []).append(task)

        processed_count = 0

        for author_uuid, task_list in author_tasks.items():
            latest_task = task_list[-1]
            superseded_tasks = task_list[:-1]

            for t in superseded_tasks:
                self.task_store.mark_superseded(
                    t["task_id"],
                    reason=f"Superseded by task {latest_task['task_id']}",
                )
                logger.info("Coalesced profile update for %s (Task %s skipped)", author_uuid, t["task_id"])

            try:
                content = latest_task["_parsed_payload"]["content"]

                persist_profile_document(
                    self.ctx.output_format,
                    author_uuid,
                    content,
                    source_window="async_worker",
                )

                self.task_store.mark_completed(latest_task["task_id"])
                logger.info("Updated profile for %s (Task %s)", author_uuid, latest_task["task_id"])
                processed_count += 1

            except Exception as exc:
                logger.exception("Error processing profile task %s", latest_task["task_id"])
                self.task_store.mark_failed(latest_task["task_id"], str(exc))

        return processed_count
