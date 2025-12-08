"""Banner generation worker."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING
from egregora.agents.banner.agent import generate_banner
from egregora.orchestration.persistence import persist_banner_document
from egregora.orchestration.worker_base import BaseWorker

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


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

                # Execute generation (synchronous)
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
