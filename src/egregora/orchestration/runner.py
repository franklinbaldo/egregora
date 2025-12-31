"""PipelineRunner orchestration logic.

This module encapsulates the execution of the pipeline logic, separating it from CLI concerns.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from typing import TYPE_CHECKING, Any

from egregora.agents.banner.worker import BannerWorker
from egregora.agents.commands import command_to_announcement, filter_commands
from egregora.agents.commands import extract_commands as extract_commands_list
from egregora.agents.enricher import EnrichmentRuntimeContext, EnrichmentWorker, schedule_enrichment
from egregora.agents.profile.generator import generate_profile_posts
from egregora.agents.profile.worker import ProfileWorker
from egregora.agents.types import PromptTooLargeError
from egregora.agents.writer import WindowProcessingParams, write_posts_for_window
from egregora.data_primitives.document import UrlContext
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.exceptions import (
    OutputSinkError,
    WindowSizeError,
    WindowSplitError,
)
from egregora.orchestration.factory import PipelineFactory
from egregora.orchestration.pipelines.modules.media import process_media_for_window
from egregora.transformations import split_window_into_n_parts
from egregora.utils.async_utils import run_async_safely

if TYPE_CHECKING:
    from datetime import datetime

    import ibis.expr.types as ir

    from egregora.input_adapters.base import MediaMapping

logger = logging.getLogger(__name__)

MIN_WINDOWS_WARNING_THRESHOLD = 5


class PipelineRunner:
    """Orchestrates the execution of the pipeline window processing loop."""

    def __init__(self, context: PipelineContext) -> None:
        self.context = context

    def process_windows(
        self,
        windows_iterator: Any,
    ) -> tuple[dict[str, dict[str, list[str]]], datetime | None]:
        """Process all windows with tracking and error handling.

        Args:
            windows_iterator: Iterator of Window objects

        Returns:
            Tuple of (results dict, max_processed_timestamp)

        """
        results = {}
        max_processed_timestamp: datetime | None = None

        # Calculate max window size from LLM context (once)
        max_window_size = self._calculate_max_window_size()
        effective_token_limit = self._resolve_context_token_limit()
        logger.debug(
            "Max window size: %d messages (based on %d token context)",
            max_window_size,
            effective_token_limit,
        )

        # Get max_windows limit from config (default 1 for single-window behavior)
        max_windows = getattr(self.context.config.pipeline, "max_windows", 1)
        if max_windows == 0:
            max_windows = None  # 0 means process all windows

        windows_processed = 0
        total_windows = max_windows if max_windows else "unlimited"
        logger.info("Processing windows (limit: %s)", total_windows)

        for window in windows_iterator:
            if max_windows is not None and windows_processed >= max_windows:
                logger.info("Reached max_windows limit (%d). Stopping processing.", max_windows)
                if max_windows < MIN_WINDOWS_WARNING_THRESHOLD:
                    logger.warning(
                        "⚠️  Processing stopped early due to low 'max_windows' setting (%d). "
                        "Use --max-windows 0 or remove the limit to process all data.",
                        max_windows,
                    )
                break

            if window.size == 0:
                logger.debug("Skipping empty window %d", window.window_index)
                continue

            window_label = (
                f"{window.start_time.strftime('%Y-%m-%d %H:%M')} - {window.end_time.strftime('%H:%M')}"
            )
            logger.info("Processing window %d: %s", windows_processed + 1, window_label)

            self._validate_window_size(window, max_window_size)

            window_results = self._process_window_with_auto_split(window, depth=0, max_depth=5)
            results.update(window_results)

            if max_processed_timestamp is None or window.end_time > max_processed_timestamp:
                max_processed_timestamp = window.end_time

            self.process_background_tasks()

            posts_count = sum(len(r.get("posts", [])) for r in window_results.values())
            profiles_count = sum(len(r.get("profiles", [])) for r in window_results.values())
            logger.debug(
                "📊 Window %d: %s posts, %s profiles",
                window.window_index,
                posts_count,
                profiles_count,
            )

            windows_processed += 1

        return results, max_processed_timestamp

    def _calculate_max_window_size(self) -> int:
        """Calculate maximum window size based on LLM context window."""
        max_tokens = self._resolve_context_token_limit()
        # TODO: [Taskmaster] Externalize hardcoded configuration values.
        avg_tokens_per_message = 5
        buffer_ratio = 0.8
        return int((max_tokens * buffer_ratio) / avg_tokens_per_message)

    def _resolve_context_token_limit(self) -> int:
        """Resolve the effective context window token limit."""
        config = self.context.config
        use_full_window = getattr(config.pipeline, "use_full_context_window", False)

        if use_full_window:
            return 1_048_576

        return config.pipeline.max_prompt_tokens

    def _validate_window_size(self, window: Any, max_size: int) -> None:
        """Validate window doesn't exceed LLM context limits."""
        if window.size > max_size:
            msg = (
                f"Window {window.window_index} has {window.size} messages but max is {max_size}. "
                f"Reduce --step-size to create smaller windows."
            )
            raise WindowSizeError(msg)

    def process_background_tasks(self) -> None:
        """Process pending background tasks."""
        if not hasattr(self.context, "task_store") or not self.context.task_store:
            return

        logger.info("⚙️  [bold cyan]Processing background tasks...[/]")

        banner_worker = BannerWorker(self.context)
        banners_processed = banner_worker.run()
        if banners_processed > 0:
            logger.info("Generated %d banners", banners_processed)

        profile_worker = ProfileWorker(self.context)
        profiles_processed = profile_worker.run()
        if profiles_processed > 0:
            logger.info("Updated %d profiles", profiles_processed)

        enrichment_worker = EnrichmentWorker(self.context)
        enrichment_processed = enrichment_worker.run()
        if enrichment_processed > 0:
            logger.info("Enriched %d items", enrichment_processed)

    def _process_window_with_auto_split(
        self, window: Any, *, depth: int = 0, max_depth: int = 5
    ) -> dict[str, dict[str, list[str]]]:
        """Process a window with automatic splitting if prompt exceeds model limit."""
        min_window_size = 5
        results: dict[str, dict[str, list[str]]] = {}
        queue: deque[tuple[Any, int]] = deque([(window, depth)])

        while queue:
            current_window, current_depth = queue.popleft()
            indent = "  " * current_depth
            window_label = f"{current_window.start_time:%Y-%m-%d %H:%M} to {current_window.end_time:%H:%M}"

            if current_window.size < min_window_size:
                logger.warning(
                    "%s⚠️  Window %s too small to split (%d messages) - attempting anyway",
                    indent,
                    window_label,
                    current_window.size,
                )

            if current_depth >= max_depth:
                error_msg = f"Max split depth {max_depth} reached for window {window_label}."
                logger.error("%s❌ %s", indent, error_msg)
                raise WindowSplitError(error_msg)

            try:
                window_results = self._process_single_window(current_window, depth=current_depth)
            except PromptTooLargeError as error:
                split_work = self._split_window_for_retry(
                    current_window,
                    error,
                    current_depth,
                    indent,
                )
                queue.extendleft(reversed(split_work))
                continue

            results.update(window_results)

        return results

    def _process_single_window(self, window: Any, *, depth: int = 0) -> dict[str, dict[str, list[str]]]:
        # TODO: [Taskmaster] Refactor this method to reduce its complexity.
        """Process a single window with media extraction, enrichment, and post writing."""
        indent = "  " * depth
        window_label = f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"

        logger.info("%s➡️  [bold]%s[/] — %s messages (depth=%d)", indent, window_label, window.size, depth)

        output_sink = self.context.output_format
        if output_sink is None:
            raise OutputSinkError("Output adapter must be initialized before processing windows.")

        url_context = self.context.url_context or UrlContext()
        window_table_processed, media_mapping = process_media_for_window(
            window_table=window.table,
            adapter=self.context.adapter,
            url_convention=output_sink.url_convention,
            url_context=url_context,
            zip_path=self.context.input_path,
        )

        if media_mapping and not self.context.enable_enrichment:
            for media_doc in media_mapping.values():
                try:
                    output_sink.persist(media_doc)
                except Exception as e:
                    logger.exception("Failed to write media file: %s", e)

        if self.context.enable_enrichment:
            enriched_table = self._perform_enrichment(window_table_processed, media_mapping)
        else:
            enriched_table = window_table_processed

        resources = PipelineFactory.create_writer_resources(self.context)
        adapter_summary, adapter_instructions = self._extract_adapter_info()

        # TODO: [Taskmaster] Improve brittle data conversion logic.
        # Convert table to list for command processing
        try:
            messages_list = enriched_table.execute().to_pylist()
        except (AttributeError, TypeError):
            try:
                messages_list = enriched_table.to_pylist()
            except (AttributeError, TypeError):
                messages_list = enriched_table if isinstance(enriched_table, list) else []

        command_messages = extract_commands_list(messages_list)
        announcements_generated = 0
        if command_messages:
            for cmd_msg in command_messages:
                try:
                    announcement = command_to_announcement(cmd_msg)
                    output_sink.persist(announcement)
                    announcements_generated += 1
                except Exception as exc:
                    logger.exception("Failed to generate announcement: %s", exc)

        clean_messages_list = filter_commands(messages_list)

        params = WindowProcessingParams(
            table=enriched_table,
            window_start=window.start_time,
            window_end=window.end_time,
            resources=resources,
            config=self.context.config,
            cache=self.context.cache,
            adapter_content_summary=adapter_summary,
            adapter_generation_instructions=adapter_instructions,
            run_id=str(self.context.run_id) if self.context.run_id else None,
            smoke_test=self.context.state.smoke_test,
        )

        posts, profiles = run_async_safely(write_posts_for_window(params))

        window_date = window.start_time.strftime("%Y-%m-%d")
        try:
            profile_docs = run_async_safely(
                generate_profile_posts(
                    ctx=self.context, messages=clean_messages_list, window_date=window_date
                )
            )
            for profile_doc in profile_docs:
                try:
                    output_sink.persist(profile_doc)
                    profiles.append(profile_doc.document_id)
                except Exception as exc:
                    logger.exception("Failed to persist profile: %s", exc)
        except Exception as exc:
            logger.exception("Failed to generate profile posts: %s", exc)

        # Scheduled tasks are returned as "pending:<task_id>"
        scheduled_posts = sum(1 for p in posts if isinstance(p, str) and p.startswith("pending:"))
        generated_posts = len(posts) - scheduled_posts

        scheduled_profiles = sum(1 for p in profiles if isinstance(p, str) and p.startswith("pending:"))
        generated_profiles = len(profiles) - scheduled_profiles

        # Construct status message
        status_parts = []
        if generated_posts > 0:
            status_parts.append(f"{generated_posts} posts")
        if scheduled_posts > 0:
            status_parts.append(f"{scheduled_posts} scheduled posts")
        if generated_profiles > 0:
            status_parts.append(f"{generated_profiles} profiles")
        if scheduled_profiles > 0:
            status_parts.append(f"{scheduled_profiles} scheduled profiles")
        if announcements_generated > 0:
            status_parts.append(f"{announcements_generated} announcements")

        status_msg = ", ".join(status_parts) if status_parts else "0 items"

        logger.info(
            "%s[green]✔ Generated[/] %s for %s",
            indent,
            status_msg,
            window_label,
        )

        return {window_label: {"posts": posts, "profiles": profiles}}

    def _perform_enrichment(
        self,
        window_table: ir.Table,
        media_mapping: MediaMapping,
        override_config: Any | None = None,
    ) -> ir.Table:
        """Execute enrichment for a window's table."""
        enrichment_context = EnrichmentRuntimeContext(
            cache=self.context.enrichment_cache,
            output_format=self.context.output_format,
            site_root=self.context.site_root,
            usage_tracker=self.context.usage_tracker,
            pii_prevention=None,
            task_store=self.context.task_store,
        )

        schedule_enrichment(
            window_table,
            media_mapping,
            override_config or self.context.config.enrichment,
            enrichment_context,
            run_id=self.context.run_id,
        )

        with EnrichmentWorker(self.context, enrichment_config=override_config) as worker:
            while True:
                processed = worker.run()
                if processed == 0:
                    break

        return window_table

    def _extract_adapter_info(self) -> tuple[str, str]:
        """Extract content summary and generation instructions from adapter."""
        adapter = getattr(self.context, "adapter", None)
        if adapter is None:
            return "", ""

        summary = getattr(adapter, "content_summary", "")
        if callable(summary):
            summary = summary()

        instructions = getattr(adapter, "generation_instructions", "")
        if callable(instructions):
            instructions = instructions()

        return str(summary or "").strip(), str(instructions or "").strip()

    def _split_window_for_retry(
        self,
        window: Any,
        error: PromptTooLargeError,
        depth: int,
        indent: str,
    ) -> list[tuple[Any, int]]:
        estimated_tokens = getattr(error, "estimated_tokens", 0)
        effective_limit = getattr(error, "effective_limit", 1) or 1

        num_splits = max(1, math.ceil(estimated_tokens / effective_limit))
        split_windows = split_window_into_n_parts(window, num_splits)

        if not split_windows:
            raise RuntimeError("Cannot split window - all splits would be empty") from error

        return [(split_window, depth + 1) for split_window in split_windows]
