"""PipelineRunner orchestration logic.

This module encapsulates the execution of the pipeline logic, separating it from CLI concerns.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Protocol, cast

from egregora.agents.banner.worker import BannerWorker
from egregora.agents.commands import command_to_announcement, filter_commands
from egregora.agents.commands import extract_commands as extract_commands_list
from egregora.agents.enricher import EnrichmentRuntimeContext, EnrichmentWorker, schedule_enrichment
from egregora.agents.profile.generator import generate_profile_posts
from egregora.agents.profile.worker import ProfileWorker
from egregora.agents.types import (
    Message,
    PromptTooLargeError,
    WindowProcessingParams,
    WriterResources,
)
from egregora.agents.writer import write_posts_for_window
from egregora.config.settings import EnrichmentSettings
from egregora.data_primitives import OutputSink
from egregora.data_primitives.document import Document, DocumentType, UrlContext
from egregora.ops.media import process_media_for_window
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.exceptions import (
    CommandAnnouncementError,
    MediaPersistenceError,
    OutputSinkError,
    ProfileGenerationError,
    WindowSizeError,
    WindowSplitError,
)
from egregora.orchestration.journal import create_journal_document, window_already_processed
from egregora.resources.prompts import PromptManager
from egregora.transformations.windowing import generate_window_signature, split_window_into_n_parts

if TYPE_CHECKING:
    from datetime import datetime
    from typing import Protocol

    import ibis.expr.types as ir

    from egregora.data_primitives.document import DocumentMetadata
    from egregora.input_adapters.base import MediaMapping
    from egregora.transformations.windowing import Window

    class JournalRepositoryProtocol(Protocol):
        def list(self, doc_type: DocumentType) -> Iterator[DocumentMetadata]: ...

    class LibraryProtocol(Protocol):
        journal: JournalRepositoryProtocol


logger = logging.getLogger(__name__)

MIN_WINDOWS_WARNING_THRESHOLD = 5


class PipelineRunner:
    """Orchestrates the execution of the pipeline window processing loop."""

    # Corresponds to a 1M token context window, expressed in characters
    FULL_CONTEXT_WINDOW_SIZE = 1_048_576

    def __init__(self, context: PipelineContext) -> None:
        self.context = context

    def process_windows(
        self,
        windows_iterator: Iterator[Window],
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

        processed_intervals = self._fetch_processed_intervals()

        for window in windows_iterator:
            # Check if window already processed (using Journal-based deduplication)
            start_iso = window.start_time.isoformat()
            end_iso = window.end_time.isoformat()

            if (start_iso, end_iso) in processed_intervals:
                logger.info(
                    "⏭️  Skipping window %d: %s (Already Processed)", window.window_index, window.start_time
                )
                continue

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

        # TODO: [Taskmaster] Refactor magic number for token limit
        if use_full_window:
            return self.FULL_CONTEXT_WINDOW_SIZE

        return config.pipeline.max_prompt_tokens

    def _validate_window_size(self, window: Window, max_size: int) -> None:
        """Validate window doesn't exceed LLM context limits."""
        if window.size > max_size:
            msg = (
                f"Window {window.window_index} has {window.size} messages but max is {max_size}. "
                f"Reduce --step-size to create smaller windows."
            )
            raise WindowSizeError(msg)

    def _fetch_processed_intervals(self) -> set[tuple[str, str]]:
        """Fetch all processed window intervals from JOURNAL entries.

        Returns:
            Set of (start_iso, end_iso) tuples.

        """
        processed: set[tuple[str, str]] = set()
        if not self.context.library:
            return processed

        try:
            library = cast("ContentLibrary", self.context.library)
            # Using list(DocumentType.JOURNAL) on library.journal (which is a DocumentRepository)
            # Use cast to Protocol to avoid "object has no attribute journal" error
            library = cast("LibraryProtocol", self.context.library)
            journals = library.journal.list(doc_type=DocumentType.JOURNAL)

            for journal in journals:
                # journal is a dict with keys matching table columns
                j_start = journal.get("window_start")
                j_end = journal.get("window_end")

                if j_start and j_end:
                    processed.add((str(j_start), str(j_end)))

        except Exception as e:
            logger.warning("Failed to fetch processed journals: %s", e)

        return processed

    def process_background_tasks(self) -> None:
        """Process pending background tasks."""
        if not hasattr(self.context, "task_store") or not self.context.task_store:
            return

        # TODO: [Taskmaster] Refactor worker logic to be more generic
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
        self, window: Window, *, depth: int = 0, max_depth: int = 5
    ) -> dict[str, dict[str, list[str]]]:
        """Process a window with automatic splitting if prompt exceeds model limit."""
        min_window_size = 5
        results: dict[str, dict[str, list[str]]] = {}
        queue: deque[tuple[Window, int]] = deque([(window, depth)])

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

    def _process_single_window(self, window: Window, *, depth: int = 0) -> dict[str, dict[str, list[str]]]:
        # TODO: [Taskmaster] Refactor this method to reduce its complexity.
        # TODO: [Taskmaster] Decompose _process_single_window method
        """Process a single window with media extraction, enrichment, and post writing."""
        indent = "  " * depth
        window_label = f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"

        # === Journal Check: Skip if already processed ===
        output_sink = self.context.output_sink
        if output_sink is None:
            msg = "Output sink must be initialized before processing windows."
            raise OutputSinkError(msg)

        template_content = PromptManager.get_template_content("writer.jinja", site_dir=self.context.site_root)
        signature = generate_window_signature(
            window.table,
            self.context.config,
            template_content,
        )

        if window_already_processed(output_sink, signature):
            logger.info(
                "%s⏭️  [yellow]Skipping window %s[/] (already processed, signature: %s)",
                indent,
                window_label,
                signature[:12],
            )
            return {}  # Empty results, window skipped

        logger.info("%s➡️  [bold]%s[/] — %s messages (depth=%d)", indent, window_label, window.size, depth)

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
                    msg = f"Failed to write media file {media_doc.filename}: {e}"
                    raise MediaPersistenceError(msg) from e

        if self.context.enable_enrichment:
            enriched_table = self._perform_enrichment(window_table_processed, media_mapping)
        else:
            enriched_table = window_table_processed

        resources = WriterResources.from_pipeline_context(self.context)
        adapter_summary, adapter_instructions = self._extract_adapter_info()

        # TODO: [Taskmaster] Refactor data type conversion for consistency
        # TODO: [Taskmaster] Improve brittle data conversion logic.
        # Convert table to list for command processing
        try:
            messages_list = enriched_table.execute().to_pylist()
        except (AttributeError, TypeError):
            try:
                messages_list = enriched_table.to_pylist()
            except (AttributeError, TypeError):
                messages_list = enriched_table if isinstance(enriched_table, list) else []

        # CONVERT TO DTOs for Writer
        # Ensure messages_list are dicts, convert to Message objects
        messages_dtos: list[Message] = []
        for msg_dict in messages_list:
            try:
                # We need to map keys if they don't match exactly or if extra keys exist.
                # Message DTO expects: event_id, ts, author_uuid...
                # The schema keys should match mostly.
                # Use model_validate to be robust or simple constructor
                # Since we don't know if extra fields are present and we want to ignore them
                # unless we use strict mode.
                # Let's use **msg_dict but filter only known fields or rely on ignore_extra if config set.
                # We didn't set ignore_extra in Message config, let's assume keys match or update Message DTO.
                # Actually, simply passing **msg_dict to constructor works if no unknown fields
                # OR if we used class Config: extra = 'ignore'.
                # Let's check keys manually to be safe or add extra='ignore' to DTO.
                # I'll add extra='ignore' to DTO in a subsequent edit if needed,
                # but for now let's assume the schema matches as we defined DTO based on it.
                # BUT, wait, enriched_table might have extra columns.
                # Let's filter keys.
                valid_keys = Message.model_fields.keys()
                filtered_dict = {k: v for k, v in msg_dict.items() if k in valid_keys}

                # Check required fields. event_id, ts, author_uuid are required.
                if "event_id" in filtered_dict and "ts" in filtered_dict and "author_uuid" in filtered_dict:
                    messages_dtos.append(Message(**filtered_dict))
            except (ValueError, TypeError) as e:
                logger.warning("Failed to convert message to DTO: %s", e)

        command_messages = extract_commands_list(messages_list)
        announcements_generated = 0
        if command_messages:
            for cmd_msg in command_messages:
                try:
                    announcement = command_to_announcement(cmd_msg)
                    output_sink.persist(announcement)
                    announcements_generated += 1
                except Exception as exc:
                    msg = f"Failed to generate announcement for command: {exc}"
                    raise CommandAnnouncementError(msg) from exc

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
            messages=messages_dtos,  # Inject DTOs
        )

        writer_result = write_posts_for_window(params)
        posts: list[str] = cast("list[str]", writer_result.get("posts", []))
        profiles: list[str] = cast("list[str]", writer_result.get("profiles", []))

        window_date = window.start_time.strftime("%Y-%m-%d")
        try:
            profile_docs_result = generate_profile_posts(
                ctx=self.context, messages=clean_messages_list, window_date=window_date
            profile_docs = cast(
                "list[Document]",
                generate_profile_posts(
                    ctx=self.context, messages=clean_messages_list, window_date=window_date
                ),
            )
            # Handle potential awaitable return from generate_profile_posts
            # In sync context, we expect list[Document]
            profile_docs: list[Document] = cast("list[Document]", profile_docs_result)

            for profile_doc in profile_docs:
                try:
                    output_sink.persist(profile_doc)
                    if profile_doc.document_id:
                        profiles.append(profile_doc.document_id)
                except Exception as exc:
                    msg = f"Failed to persist profile {profile_doc.document_id}: {exc}"
                    raise ProfileGenerationError(msg) from exc
        except Exception as exc:
            if isinstance(exc, ProfileGenerationError):
                raise
            msg = f"Failed to generate profile posts: {exc}"
            raise ProfileGenerationError(msg) from exc

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

        # === Journal Persist: Mark window as processed ===
        try:
            journal = create_journal_document(
                signature=signature,
                run_id=self.context.run_id,
                window_start=window.start_time,
                window_end=window.end_time,
                model=self.context.config.models.writer,
                posts_generated=len(posts),
                profiles_updated=len(profiles),
            )
            output_sink.persist(journal)
            logger.debug("Persisted JOURNAL for window: %s", window_label)
        except Exception as e:
            # Non-fatal: Log warning but don't fail the pipeline
            logger.warning("Failed to persist JOURNAL for window %s: %s", window_label, e)

        return {window_label: {"posts": posts, "profiles": profiles}}

    def _perform_enrichment(
        self,
        window_table: ir.Table,
        media_mapping: MediaMapping,
        override_config: EnrichmentSettings | None = None,
    ) -> ir.Table:
        """Execute enrichment for a window's table."""
        enrichment_context = EnrichmentRuntimeContext(
            cache=self.context.cache.enrichment,
            output_sink=self.context.output_sink,
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

    # TODO: [Taskmaster] Extract command processing logic from _process_single_window
    def _process_commands(self, messages_list: list[dict], output_sink: OutputSink) -> int:
        """Processes commands from a list of messages."""
        announcements_generated = 0
        command_messages = extract_commands_list(messages_list)
        if command_messages:
            for cmd_msg in command_messages:
                try:
                    announcement = command_to_announcement(cmd_msg)
                    output_sink.persist(announcement)
                    announcements_generated += 1
                except Exception as exc:
                    msg = f"Failed to generate announcement for command: {exc}"
                    raise CommandAnnouncementError(msg) from exc
        return announcements_generated

    # TODO: [Taskmaster] Extract status message generation from _process_single_window
    def _construct_status_message(self, posts: list, profiles: list, announcements_generated: int) -> str:
        """Constructs a status message for logging."""
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

        return ", ".join(status_parts) if status_parts else "0 items"

    def _split_window_for_retry(
        self,
        window: Window,
        error: PromptTooLargeError,
        depth: int,
        indent: str,
    ) -> list[tuple[Window, int]]:
        estimated_tokens = getattr(error, "estimated_tokens", 0)
        effective_limit = getattr(error, "effective_limit", 1) or 1

        num_splits = max(1, math.ceil(estimated_tokens / effective_limit))
        split_windows = split_window_into_n_parts(window, num_splits)

        if not split_windows:
            msg = "Cannot split window - all splits would be empty"
            raise RuntimeError(msg) from error

        return [(split_window, depth + 1) for split_window in split_windows]
