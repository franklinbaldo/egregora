"""Pipeline execution logic.

This module encapsulates the core logic for running the processing pipeline,
separated from the CLI orchestration.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Any

from egregora.agents.banner.worker import BannerWorker
from egregora.agents.commands import command_to_announcement, extract_commands, filter_commands
from egregora.agents.enricher import EnrichmentRuntimeContext, EnrichmentWorker, schedule_enrichment
from egregora.agents.profile.generator import generate_profile_posts
from egregora.agents.profile.worker import ProfileWorker
from egregora.agents.types import PromptTooLargeError, WindowProcessingParams
from egregora.agents.writer import write_posts_for_window
from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.protocols import UrlContext
from egregora.input_adapters.base import MediaMapping
from egregora.ops.media import process_media_for_window
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.factory import PipelineFactory
from egregora.transformations import (
    split_window_into_n_parts,
)

if TYPE_CHECKING:
    import ibis.expr.types as ir

logger = logging.getLogger(__name__)

MIN_WINDOWS_WARNING_THRESHOLD = 5


def run_async_safely(coro: Any) -> Any:
    """Run an async coroutine safely, handling nested event loops.

    If an event loop is already running (e.g., in Jupyter or nested calls),
    this will use run_until_complete instead of asyncio.run().
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - use asyncio.run()
        return asyncio.run(coro)
    else:
        # Loop is already running - use run_until_complete in a new thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()


class PipelineRunner:
    """Encapsulates the execution logic for the Egregora pipeline."""

    def __init__(self, context: PipelineContext):
        self.ctx = context
        self.output_sink = context.output_format
        if self.output_sink is None:
            msg = "Output sink must be initialized in PipelineContext."
            raise ValueError(msg)

    def process_windows(
        self, windows_iterator: Any, max_windows: int | None = None
    ) -> tuple[dict[str, dict[str, list[str]]], datetime | None]:
        """Process all windows.

        Args:
            windows_iterator: Iterator of Window objects
            max_windows: Optional limit on number of windows to process

        Returns:
            Tuple of (results dict, max_processed_timestamp)
            - results: Dict mapping window labels to {'posts': [...], 'profiles': [...]}
            - max_processed_timestamp: Latest end_time from successfully processed windows
        """
        results = {}
        max_processed_timestamp: datetime | None = None

        # Calculate max window size from LLM context (once)
        max_window_size = self._calculate_max_window_size(self.ctx.config)
        effective_token_limit = self._resolve_context_token_limit(self.ctx.config)
        logger.debug(
            "Max window size: %d messages (based on %d token context)",
            max_window_size,
            effective_token_limit,
        )

        windows_processed = 0
        total_windows_label = max_windows if max_windows is not None else "unlimited"
        logger.info("Processing windows (limit: %s)", total_windows_label)

        for window in windows_iterator:
            if max_windows is not None and windows_processed >= max_windows:
                logger.info("Reached max_windows limit (%d). Stopping processing.", max_windows)
                if max_windows < MIN_WINDOWS_WARNING_THRESHOLD:
                    logger.warning(
                        "⚠️  Processing stopped early due to low 'max_windows' setting (%d). "
                        "This may result in incomplete data coverage. "
                        "Use --max-windows 0 or remove the limit to process all data.",
                        max_windows,
                    )
                break
            # Skip empty windows
            if window.size == 0:
                logger.debug(
                    "Skipping empty window %d (%s to %s)",
                    window.window_index,
                    window.start_time.strftime("%Y-%m-%d %H:%M"),
                    window.end_time.strftime("%Y-%m-%d %H:%M"),
                )
                continue

            # Log current window
            window_label = f"{window.start_time.strftime('%Y-%m-%d %H:%M')} - {window.end_time.strftime('%H:%M')}"
            logger.info("Processing window %d: %s", windows_processed + 1, window_label)

            # Validate window size doesn't exceed LLM context limits
            self._validate_window_size(window, max_window_size)

            # Process window
            window_results = self._process_window_with_auto_split(window, depth=0, max_depth=5)
            results.update(window_results)

            # Track max processed timestamp for checkpoint
            if max_processed_timestamp is None or window.end_time > max_processed_timestamp:
                max_processed_timestamp = window.end_time

            # Process background tasks periodically
            self.process_background_tasks()

            # Log summary
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

    def process_background_tasks(self) -> None:
        """Process pending background tasks (banners, profiles, enrichment)."""
        if not hasattr(self.ctx, "task_store") or not self.ctx.task_store:
            return

        logger.info("⚙️  [bold cyan]Processing background tasks...[/]")

        # Run workers sequentially for now
        # 1. Banner Generation (Highest priority - visual assets)
        banner_worker = BannerWorker(self.ctx)
        banners_processed = banner_worker.run()
        if banners_processed > 0:
            logger.info("Generated %d banners", banners_processed)

        # 2. Profile Updates
        profile_worker = ProfileWorker(self.ctx)
        profiles_processed = profile_worker.run()
        if profiles_processed > 0:
            logger.info("Updated %d profiles", profiles_processed)

        # 3. Enrichment
        enrichment_worker = EnrichmentWorker(self.ctx)
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

            self._warn_if_window_too_small(current_window.size, indent, window_label, min_window_size)
            self._ensure_split_depth(current_depth, max_depth, indent, window_label)

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

    def _process_single_window(
        self, window: Any, *, depth: int = 0
    ) -> dict[str, dict[str, list[str]]]:
        """Process a single window with media extraction, enrichment, and post writing."""
        indent = "  " * depth
        window_label = f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"
        window_table = window.table
        window_count = window.size

        logger.info("%s➡️  [bold]%s[/] — %s messages (depth=%d)", indent, window_label, window_count, depth)

        url_context = self.ctx.url_context or UrlContext()
        window_table_processed, media_mapping = process_media_for_window(
            window_table=window_table,
            adapter=self.ctx.adapter,
            url_convention=self.output_sink.url_convention,
            url_context=url_context,
            zip_path=self.ctx.input_path,
        )

        # Media persistence deferred until after enrichment unless disabled
        if media_mapping and not self.ctx.enable_enrichment:
            for media_doc in media_mapping.values():
                try:
                    self.output_sink.persist(media_doc)
                except (OSError, PermissionError):
                    logger.exception("Failed to write media file %s", media_doc.metadata.get("filename"))
                except ValueError:
                    logger.exception("Invalid media document %s", media_doc.metadata.get("filename"))

        # Enrichment
        if self.ctx.enable_enrichment:
            logger.info("%s✨ [cyan]Scheduling enrichment[/] for window %s", indent, window_label)
            enriched_table = self._perform_enrichment(window_table_processed, media_mapping)
        else:
            enriched_table = window_table_processed

        # Write posts
        resources = PipelineFactory.create_writer_resources(self.ctx)
        adapter_summary, adapter_instructions = self._extract_adapter_info()

        # Command processing
        try:
            messages_list = enriched_table.execute().to_pylist()
        except (AttributeError, TypeError):
            try:
                messages_list = enriched_table.to_pylist()
            except (AttributeError, TypeError):
                messages_list = enriched_table if isinstance(enriched_table, list) else []
                logger.warning("Could not convert table to list, using fallback")

        command_messages = extract_commands(messages_list)
        announcements_generated = 0
        if command_messages:
            logger.info(
                "%s📢 [cyan]Processing %d commands[/] for window %s", indent, len(command_messages), window_label
            )
            for cmd_msg in command_messages:
                try:
                    announcement = command_to_announcement(cmd_msg)
                    self.output_sink.persist(announcement)
                    announcements_generated += 1
                except Exception as exc:
                    logger.exception("Failed to generate announcement from command: %s", exc)

        clean_messages_list = filter_commands(messages_list)

        params = WindowProcessingParams(
            table=enriched_table,
            window_start=window.start_time,
            window_end=window.end_time,
            resources=resources,
            config=self.ctx.config,
            cache=self.ctx.cache,
            adapter_content_summary=adapter_summary,
            adapter_generation_instructions=adapter_instructions,
            run_id=str(self.ctx.run_id) if self.ctx.run_id else None,
        )
        result = run_async_safely(write_posts_for_window(params))

        posts = result.get("posts", [])
        profiles = result.get("profiles", [])

        # Generate PROFILE posts
        window_date = window.start_time.strftime("%Y-%m-%d")
        try:
            profile_docs = run_async_safely(
                generate_profile_posts(ctx=self.ctx, messages=clean_messages_list, window_date=window_date)
            )

            for profile_doc in profile_docs:
                try:
                    self.output_sink.persist(profile_doc)
                    profiles.append(profile_doc.document_id)
                except Exception as exc:
                    logger.exception("Failed to persist profile: %s", exc)

            if profile_docs:
                logger.info(
                    "%s👥 [cyan]Generated %d profile posts[/] for window %s",
                    indent,
                    len(profile_docs),
                    window_label,
                )
        except Exception as exc:
            logger.exception("Failed to generate profile posts: %s", exc)

        # Log status
        scheduled_posts = sum(1 for p in posts if isinstance(p, str) and p.startswith("pending:"))
        generated_posts = len(posts) - scheduled_posts
        scheduled_profiles = sum(1 for p in profiles if isinstance(p, str) and p.startswith("pending:"))
        generated_profiles = len(profiles) - scheduled_profiles

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
        logger.info("%s[green]✔ Generated[/] %s for %s", indent, status_msg, window_label)

        return {window_label: result}

    def _perform_enrichment(
        self,
        window_table: ir.Table,
        media_mapping: MediaMapping,
        override_config: Any | None = None,
    ) -> ir.Table:
        """Execute enrichment for a window's table."""
        pii_prevention = None

        enrichment_context = EnrichmentRuntimeContext(
            cache=self.ctx.enrichment_cache,
            output_format=self.ctx.output_format,
            site_root=self.ctx.site_root,
            usage_tracker=self.ctx.usage_tracker,
            pii_prevention=pii_prevention,
            task_store=self.ctx.task_store,
        )

        schedule_enrichment(
            window_table,
            media_mapping,
            override_config or self.ctx.config.enrichment,
            enrichment_context,
            run_id=self.ctx.run_id,
        )

        with EnrichmentWorker(self.ctx, enrichment_config=override_config) as worker:
            total_processed = 0
            while True:
                processed = worker.run()
                if processed == 0:
                    break
                total_processed += processed
                logger.info("Synchronously processed %d enrichment tasks", processed)

            if total_processed > 0:
                logger.info("Enrichment complete. Processed %d items.", total_processed)

        return window_table

    def _extract_adapter_info(self) -> tuple[str, str]:
        """Extract content summary and generation instructions from adapter."""
        adapter = getattr(self.ctx, "adapter", None)
        if adapter is None:
            return "", ""

        summary: str | None = ""
        try:
            summary = getattr(adapter, "content_summary", "")
            if callable(summary):
                summary = summary()
        except (AttributeError, TypeError) as exc:
            logger.debug("Adapter %s failed to provide content_summary: %s", adapter, exc)
            summary = ""

        instructions: str | None = ""
        try:
            instructions = getattr(adapter, "generation_instructions", "")
            if callable(instructions):
                instructions = instructions()
        except (AttributeError, TypeError) as exc:
            logger.warning("Failed to evaluate adapter generation instructions: %s", exc)
            instructions = ""

        return (summary or "").strip(), (instructions or "").strip()

    def _split_window_for_retry(
        self,
        window: Any,
        error: Exception,
        depth: int,
        indent: str,
    ) -> list[tuple[Any, int]]:
        estimated_tokens = getattr(error, "estimated_tokens", 0)
        effective_limit = getattr(error, "effective_limit", 1) or 1

        logger.warning(
            "%s⚡ [yellow]Splitting window[/] %s (prompt: %dk tokens > %dk limit)",
            indent,
            f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}",
            estimated_tokens // 1000,
            effective_limit // 1000,
        )

        num_splits = max(1, math.ceil(estimated_tokens / effective_limit))
        logger.info("%s↳ [dim]Splitting into %d parts[/]", indent, num_splits)

        split_windows = split_window_into_n_parts(window, num_splits)
        if not split_windows:
            error_msg = (
                f"Cannot split window {window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"
                " - all splits would be empty"
            )
            logger.exception("%s❌ %s", indent, error_msg)
            raise RuntimeError(error_msg) from error

        scheduled: list[tuple[Any, int]] = []
        for index, split_window in enumerate(split_windows, 1):
            split_label = f"{split_window.start_time:%Y-%m-%d %H:%M} to {split_window.end_time:%H:%M}"
            logger.info(
                "%s↳ [dim]Processing part %d/%d: %s[/]",
                indent,
                index,
                len(split_windows),
                split_label,
            )
            scheduled.append((split_window, depth + 1))

        return scheduled

    def _warn_if_window_too_small(self, size: int, indent: str, label: str, minimum: int) -> None:
        if size < minimum:
            logger.warning(
                "%s⚠️  Window %s too small to split (%d messages) - attempting anyway",
                indent,
                label,
                size,
            )

    def _ensure_split_depth(self, depth: int, max_depth: int, indent: str, label: str) -> None:
        if depth >= max_depth:
            error_msg = (
                f"Max split depth {max_depth} reached for window {label}. "
                "Window cannot be split enough to fit in model context (possible miscalculation). "
                "Try increasing --max-prompt-tokens or using --use-full-context-window."
            )
            logger.error("%s❌ %s", indent, error_msg)
            raise RuntimeError(error_msg)

    def _resolve_context_token_limit(self, config: EgregoraConfig) -> int:
        """Resolve the effective context window token limit for the writer model."""
        use_full_window = getattr(config.pipeline, "use_full_context_window", False)

        if use_full_window:
            writer_model = config.models.writer
            # Use KNOWN_MODEL_LIMITS from constants if available
            from egregora.constants import KNOWN_MODEL_LIMITS

            clean_name = (
                writer_model.replace("models/", "").replace("google-gla:", "").replace("google-vertex:", "")
            )
            limit = 128_000
            for known_model, known_limit in KNOWN_MODEL_LIMITS.items():
                if clean_name.startswith(known_model):
                    limit = known_limit
                    break

            logger.debug(
                "Using full context window for writer model %s (limit=%d tokens)",
                writer_model,
                limit,
            )
            return limit

        limit = config.pipeline.max_prompt_tokens
        logger.debug("Using configured max_prompt_tokens cap: %d tokens", limit)
        return limit

    def _calculate_max_window_size(self, config: EgregoraConfig) -> int:
        """Calculate maximum window size based on LLM context window."""
        max_tokens = self._resolve_context_token_limit(config)
        avg_tokens_per_message = 5  # Conservative estimate
        buffer_ratio = 0.8  # Leave 20% for system prompt, tools, etc.

        return int((max_tokens * buffer_ratio) / avg_tokens_per_message)

    def _validate_window_size(self, window: Any, max_size: int) -> None:
        """Validate window doesn't exceed LLM context limits."""
        if window.size > max_size:
            msg = (
                f"Window {window.window_index} has {window.size} messages but max is {max_size}. "
                f"This limit is based on your model's context window. "
                f"Reduce --step-size to create smaller windows."
            )
            raise ValueError(msg)
