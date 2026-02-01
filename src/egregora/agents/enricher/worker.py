"""Enrichment Worker orchestrator."""

from __future__ import annotations

import logging
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from egregora.agents.enricher.media import MediaEnrichmentHandler
from egregora.agents.enricher.types import MediaEnrichmentConfig
from egregora.agents.enricher.url import UrlEnrichmentHandler
from egregora.config.settings import EnrichmentSettings
from egregora.llm.api_keys import get_google_api_keys
from egregora.orchestration.worker_base import BaseWorker
from egregora.security.zip import validate_zip_contents

if TYPE_CHECKING:
    from types import TracebackType

    from ibis.expr.types import Table

    from egregora.agents.enricher.types import EnrichmentRuntimeContext
    from egregora.input_adapters.base import MediaMapping
    from egregora.llm.providers.model_key_rotator import ModelKeyRotator
    from egregora.orchestration.context import PipelineContext

logger = logging.getLogger(__name__)


def schedule_enrichment(
    messages_table: Table,
    media_mapping: MediaMapping,
    enrichment_settings: EnrichmentSettings,
    context: EnrichmentRuntimeContext,
    run_id: Any = None,
) -> None:
    """Schedule enrichment tasks for background processing."""
    if not hasattr(context, "task_store") or not context.task_store:
        logger.warning("TaskStore not available in context; skipping enrichment scheduling.")
        return

    if messages_table.count().execute() == 0:
        return

    import uuid

    current_run_id = run_id or uuid.uuid4()
    max_enrichments = enrichment_settings.max_enrichments

    # Use handlers for enqueueing (instantiated without worker)
    url_handler = UrlEnrichmentHandler(worker=None)
    url_count = url_handler.enqueue(
        messages_table,
        max_enrichments,
        context,
        current_run_id,
        enable_url=enrichment_settings.enable_url,
    )

    media_config = MediaEnrichmentConfig(
        media_mapping=media_mapping,
        max_enrichments=max_enrichments,
        enable_media=enrichment_settings.enable_media,
    )
    media_handler = MediaEnrichmentHandler(worker=None)
    media_count = media_handler.enqueue(
        messages_table,
        context,
        current_run_id,
        media_config,
    )
    logger.info("Scheduled %d URL tasks and %d Media tasks", url_count, media_count)


class EnrichmentWorker(BaseWorker):
    """Worker for media enrichment (e.g. image description)."""

    def __init__(
        self,
        ctx: PipelineContext,
        enrichment_config: EnrichmentSettings | None = None,
    ) -> None:
        super().__init__(ctx)
        self.ctx: PipelineContext = ctx
        self._enrichment_config_override = enrichment_config
        self.zip_handle: zipfile.ZipFile | None = None
        self.media_index: dict[str, str] = {}
        # Main Architecture: Ephemeral media staging
        self.staging_dir = tempfile.TemporaryDirectory(prefix="egregora_staging_")
        self.staged_files: set[str] = set()

        # Initialize handlers
        self.url_handler = UrlEnrichmentHandler(self)
        self.media_handler = MediaEnrichmentHandler(self)

        # Initialize ModelKeyRotator if enabled (reusing state across batches)
        rotation_enabled = getattr(self.enrichment_config, "model_rotation_enabled", True)
        self.rotator: ModelKeyRotator | None = None
        if rotation_enabled:
            from egregora.llm.providers.model_key_rotator import ModelKeyRotator

            rotation_models = getattr(self.enrichment_config, "rotation_models", None)
            self.rotator = ModelKeyRotator(models=rotation_models)

        if self.ctx.input_path and self.ctx.input_path.exists() and self.ctx.input_path.is_file():
            try:
                self.zip_handle = zipfile.ZipFile(self.ctx.input_path, "r")
                validate_zip_contents(self.zip_handle)
                # Build index for O(1) lookup
                for info in self.zip_handle.infolist():
                    if not info.is_dir():
                        self.media_index[Path(info.filename).name.lower()] = info.filename
            except (OSError, zipfile.BadZipFile) as exc:
                logger.warning("Failed to open source ZIP %s: %s", self.ctx.input_path, exc)
                if self.zip_handle:
                    self.zip_handle.close()
                    self.zip_handle = None

    @property
    def enrichment_config(self) -> EnrichmentSettings:
        """Get effective enrichment configuration."""
        if self._enrichment_config_override:
            return self._enrichment_config_override
        # Fallback to context config if available
        if hasattr(self.ctx, "config"):
            return self.ctx.config.enrichment
        # Last resort fallback (should not happen in normal pipeline)
        return EnrichmentSettings()

    def close(self) -> None:
        """Explicitly close the ZIP handle to release resources."""
        if self.zip_handle:
            try:
                self.zip_handle.close()
            except OSError:
                logger.debug("Error closing ZIP handle", exc_info=True)
            finally:
                self.zip_handle = None
                self.media_index = {}

        # Clean up staging directory
        if self.staging_dir:
            try:
                self.staging_dir.cleanup()
            except OSError:
                logger.debug("Error cleaning up staging directory", exc_info=True)
            finally:
                self.staging_dir = None
                self.staged_files = set()

    def __enter__(self) -> Self:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit - ensures ZIP handle is closed."""
        self.close()

    def run(self) -> int:
        """Process pending enrichment tasks in batches."""
        if not self.enrichment_config.enabled:
            logger.info("Enrichment is disabled. Skipping enrichment worker.")
            return 0

        base_batch_size = 50
        concurrency = self.determine_concurrency(base_batch_size)
        fetch_limit = base_batch_size * concurrency

        tasks = self.task_store.fetch_pending(task_type="enrich_url", limit=fetch_limit)
        media_tasks = self.task_store.fetch_pending(task_type="enrich_media", limit=fetch_limit)

        total_tasks = len(tasks) + len(media_tasks)
        if not total_tasks:
            return 0

        logger.info(
            "[Enrichment] Processing %d tasks (URL: %d, Media: %d) with concurrency %d",
            total_tasks,
            len(tasks),
            len(media_tasks),
            concurrency,
        )

        processed_count = 0

        if tasks:
            count = self.url_handler.process_batch(tasks)
            processed_count += count
            logger.info("[Enrichment] URL batch complete: %d/%d", count, len(tasks))

        if media_tasks:
            count = self.media_handler.process_batch(media_tasks)
            processed_count += count
            logger.info("[Enrichment] Media batch complete: %d/%d", count, len(media_tasks))

        logger.info("Enrichment complete: %d/%d tasks processed", processed_count, total_tasks)
        return processed_count

    def determine_concurrency(self, task_count: int) -> int:
        """Determine optimal concurrency based on available API keys."""
        api_keys = get_google_api_keys()
        num_keys = len(api_keys) if api_keys else 1

        enrichment_concurrency = getattr(
            self.enrichment_config,
            "max_concurrent_enrichments",
            None,
        )

        if enrichment_concurrency is None:
            logger.info("Auto-scaling concurrency to match available API keys: %d", num_keys)
            enrichment_concurrency = num_keys

        global_concurrency = getattr(self.ctx.config.quota, "concurrency", num_keys)

        max_concurrent = min(enrichment_concurrency, global_concurrency, task_count)

        logger.info(
            "Processing %d enrichment tasks with max concurrency of %d "
            "(API keys: %d, enrichment limit: %d, global limit: %d)",
            task_count,
            max_concurrent,
            num_keys,
            enrichment_concurrency,
            global_concurrency,
        )

        return max_concurrent
