"""Preparation logic for the Egregora write pipeline.

This module handles:
- Input parsing and validation
- Filter application (dates, users, commands)
- Window creation
- Initial content directory setup
- Media processing and enrichment scheduling
- Conversation iteration
"""

from __future__ import annotations

import logging
import math
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console

from egregora.agents.avatar import AvatarContext, process_avatar_commands
from egregora.agents.enricher import EnrichmentRuntimeContext, EnrichmentWorker, schedule_enrichment
from egregora.config.exceptions import InvalidDateFormatError, InvalidTimezoneError
from egregora.config.settings import parse_date_arg, validate_timezone
from egregora.data_primitives.document import OutputSink, UrlContext
from egregora.input_adapters.whatsapp.commands import extract_commands, filter_egregora_messages
from egregora.knowledge.profiles import filter_opted_out_authors, process_commands
from egregora.ops.media import process_media_for_window
from egregora.orchestration.context import PipelineContext, PipelineRunParams
from egregora.output_sinks import create_and_initialize_adapter
from egregora.rag import index_documents, reset_backend
from egregora.transformations import (
    Window,
    WindowConfig,
    create_windows,
    split_window_into_n_parts,
)

if TYPE_CHECKING:
    import ibis.expr.types as ir

    from egregora.config.settings import EgregoraConfig, EnrichmentSettings
    from egregora.input_adapters.base import InputAdapter, MediaMapping


logger = logging.getLogger(__name__)
console = Console()


@dataclass
class PreparedPipelineData:
    """Artifacts produced during dataset preparation."""

    messages_table: ir.Table
    windows_iterator: Iterator[Window]
    checkpoint_path: Path
    context: PipelineContext
    enable_enrichment: bool
    embedding_model: str


@dataclass
class Conversation:
    """A conversation window prepared for processing (ETL completed)."""

    window: Window
    messages_table: ir.Table
    media_mapping: MediaMapping
    context: PipelineContext
    adapter_info: tuple[str, str]
    depth: int = 0


@dataclass
class FilterOptions:
    """Options for filtering messages."""

    from_date: date_type | None = None
    to_date: date_type | None = None


def validate_dates(from_date: str | None, to_date: str | None) -> tuple[date_type | None, date_type | None]:
    """Validate and parse date arguments."""
    from_date_obj, to_date_obj = None, None
    try:
        if from_date:
            from_date_obj = parse_date_arg(from_date, "from_date")
        if to_date:
            to_date_obj = parse_date_arg(to_date, "to_date")
    except (ValueError, InvalidDateFormatError) as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1) from e
    return from_date_obj, to_date_obj


def validate_timezone_arg(timezone: str | None) -> None:
    """Validate timezone argument."""
    if timezone:
        try:
            validate_timezone(timezone)
            console.print(f"[green]Using timezone: {timezone}[/green]")
        except (ValueError, InvalidTimezoneError) as e:
            console.print(f"[red]{e}[/red]")
            raise SystemExit(1) from e


def _apply_date_filters(
    messages_table: ir.Table, from_date: date_type | None, to_date: date_type | None
) -> ir.Table:
    """Apply date range filtering."""
    if not (from_date or to_date):
        return messages_table

    original_count = messages_table.count().execute()
    if from_date and to_date:
        messages_table = messages_table.filter(
            (messages_table.ts.date() >= from_date) & (messages_table.ts.date() <= to_date)
        )
        logger.info("📅 [cyan]Filtering[/] from %s to %s", from_date, to_date)
    elif from_date:
        messages_table = messages_table.filter(messages_table.ts.date() >= from_date)
        logger.info("📅 [cyan]Filtering[/] from %s onwards", from_date)
    elif to_date:
        messages_table = messages_table.filter(messages_table.ts.date() <= to_date)
        logger.info("📅 [cyan]Filtering[/] up to %s", to_date)

    filtered_count = messages_table.count().execute()
    removed_by_date = original_count - filtered_count
    if removed_by_date > 0:
        logger.info("🗓️  [yellow]Filtered out[/] %s messages (kept %s)", removed_by_date, filtered_count)
    return messages_table


def _apply_filters(
    messages_table: ir.Table,
    ctx: PipelineContext,
    options: FilterOptions,
) -> ir.Table:
    """Apply all filters: egregora messages, opted-out users, date range.

    Args:
        messages_table: Input messages table
        ctx: Pipeline context
        options: Filter configuration

    Returns:
        Filtered messages table

    """
    # Filter egregora messages
    messages_table, egregora_removed = filter_egregora_messages(messages_table)
    if egregora_removed:
        logger.info("[yellow]🧹 Removed[/] %s /egregora messages", egregora_removed)

    # Filter opted-out authors
    messages_table, removed_count = filter_opted_out_authors(messages_table, ctx.profiles_dir)
    if removed_count > 0:
        logger.warning("⚠️  %s messages removed from opted-out users", removed_count)

    # Date range filtering
    return _apply_date_filters(messages_table, options.from_date, options.to_date)


def _setup_content_directories(ctx: PipelineContext) -> None:
    """Create and validate content directories.

    Args:
        ctx: Pipeline context

    Raises:
        ValueError: If directories are not inside docs_dir

    """
    content_dirs = {
        "posts": ctx.posts_dir,
        "profiles": ctx.profiles_dir,
        "media": ctx.media_dir,
    }

    for label, directory in content_dirs.items():
        if label == "media":
            try:
                directory.relative_to(ctx.docs_dir)
            except ValueError:
                try:
                    directory.relative_to(ctx.site_root)
                except ValueError as exc:
                    msg = (
                        "Media directory must reside inside the MkDocs docs_dir or the site root. "
                        f"Expected parent {ctx.docs_dir} or {ctx.site_root}, got {directory}."
                    )
                    raise ValueError(msg) from exc
            directory.mkdir(parents=True, exist_ok=True)
            continue

        try:
            directory.relative_to(ctx.docs_dir)
        except ValueError as exc:
            msg = (
                f"{label.capitalize()} directory must reside inside the MkDocs docs_dir. "
                f"Expected parent {ctx.docs_dir}, got {directory}."
            )
            raise ValueError(msg) from exc
        directory.mkdir(parents=True, exist_ok=True)


def _process_commands_and_avatars(
    messages_table: ir.Table, ctx: PipelineContext, vision_model: str
) -> ir.Table:
    """Process egregora commands and avatar commands.

    Args:
        messages_table: Input messages table
        ctx: Pipeline context
        vision_model: Vision model identifier

    Returns:
        Messages table (unchanged, commands are side effects)

    """
    commands = extract_commands(messages_table)
    if commands:
        process_commands(commands, ctx.profiles_dir)
        logger.info("[magenta]🧾 Processed[/] %s /egregora commands", len(commands))
    else:
        logger.info("[magenta]🧾 No /egregora commands detected[/]")

    logger.info("[cyan]🖼️  Processing avatar commands...[/]")
    avatar_context = AvatarContext(
        docs_dir=ctx.docs_dir,
        media_dir=ctx.media_dir,
        profiles_dir=ctx.profiles_dir,
        vision_model=vision_model,
        cache=ctx.cache.enrichment,
    )
    avatar_results = process_avatar_commands(
        messages_table=messages_table,
        context=avatar_context,
    )
    if avatar_results:
        logger.info("[green]✓ Processed[/] %s avatar command(s)", len(avatar_results))

    return messages_table


def _parse_and_validate_source(
    adapter: InputAdapter,
    input_path: Path,
    timezone: str,
    *,
    output_adapter: OutputSink | None = None,
) -> ir.Table:
    """Parse source and return messages table.

    Args:
        adapter: Source adapter instance
        input_path: Path to input file
        timezone: Timezone string
        output_adapter: Optional output adapter (used by adapters that reprocess existing sites)

    Returns:
        messages_table: Parsed messages table

    """
    logger.info("[bold cyan]📦 Parsing with adapter:[/] %s", adapter.source_name)
    messages_table = adapter.parse(input_path, timezone=timezone, output_adapter=output_adapter)
    total_messages = messages_table.count().execute()
    logger.info("[green]✅ Parsed[/] %s messages", total_messages)

    metadata = adapter.get_metadata(input_path)
    logger.info("[yellow]👥 Group:[/] %s", metadata.get("group_name", "Unknown"))

    return messages_table


def prepare_pipeline_data(
    adapter: InputAdapter,
    run_params: PipelineRunParams,
    ctx: PipelineContext,
) -> PreparedPipelineData:
    """Prepare messages, filters, and windowing context for processing.

    Args:
        adapter: Input adapter instance
        run_params: Aggregated pipeline run parameters
        ctx: Pipeline context

    Returns:
        PreparedPipelineData with messages table, windows iterator, and updated context

    """
    config = run_params.config
    timezone = config.pipeline.timezone
    step_size = config.pipeline.step_size
    step_unit = config.pipeline.step_unit
    overlap_ratio = config.pipeline.overlap_ratio
    max_window_time_hours = config.pipeline.max_window_time
    max_window_time = timedelta(hours=max_window_time_hours) if max_window_time_hours else None
    enable_enrichment = config.enrichment.enabled

    from_date: date_type | None = None
    to_date: date_type | None = None
    if config.pipeline.from_date:
        from_date = date_type.fromisoformat(config.pipeline.from_date)
    if config.pipeline.to_date:
        to_date = date_type.fromisoformat(config.pipeline.to_date)

    vision_model = config.models.enricher_vision
    embedding_model = config.models.embedding

    output_sink = create_and_initialize_adapter(
        config,
        run_params.output_dir,
        site_root=ctx.site_root,
        registry=ctx.output_registry,
        url_context=ctx.url_context,
    )
    ctx = ctx.with_output_sink(output_sink)

    messages_table = _parse_and_validate_source(
        adapter, run_params.input_path, timezone, output_adapter=output_sink
    )
    _setup_content_directories(ctx)
    messages_table = _process_commands_and_avatars(messages_table, ctx, vision_model)

    filter_options = FilterOptions(
        from_date=from_date,
        to_date=to_date,
    )
    messages_table = _apply_filters(
        messages_table,
        ctx,
        filter_options,
    )

    logger.info("🎯 [bold cyan]Creating windows:[/] step_size=%s, unit=%s", step_size, step_unit)
    window_config = WindowConfig(
        step_size=step_size,
        step_unit=step_unit,
        overlap_ratio=overlap_ratio,
        max_window_time=max_window_time,
    )
    windows_iterator = create_windows(
        messages_table,
        config=window_config,
    )

    # Update context with adapter
    ctx = ctx.with_adapter(adapter)

    # Index existing documents into RAG
    if ctx.config.rag.enabled:
        logger.info("[bold cyan]📚 Indexing existing documents into RAG...[/]")
        try:
            # Get existing documents from output format
            existing_docs = list(output_sink.documents())
            if existing_docs:
                index_documents(existing_docs)
                logger.info("[green]✓ Indexed %d existing documents into RAG[/]", len(existing_docs))
                reset_backend()
            else:
                logger.info("[dim]No existing documents to index[/]")
        except (ConnectionError, TimeoutError) as exc:
            logger.warning("[yellow]⚠️ RAG backend unavailable for indexing (non-critical): %s[/]", exc)
        except (ValueError, TypeError) as exc:
            logger.warning("[yellow]⚠️ Invalid document data for RAG indexing (non-critical): %s[/]", exc)
        except (OSError, PermissionError) as exc:
            logger.warning("[yellow]⚠️ Cannot access RAG storage for indexing (non-critical): %s[/]", exc)

    checkpoint_root = ctx.storage.checkpoint_dir or (ctx.output_dir / ".egregora" / "data")
    checkpoint_path = checkpoint_root / f"{ctx.run_id}-pipeline.json"

    return PreparedPipelineData(
        messages_table=messages_table,
        windows_iterator=windows_iterator,
        checkpoint_path=checkpoint_path,
        context=ctx,
        enable_enrichment=enable_enrichment,
        embedding_model=embedding_model,
    )


def perform_enrichment(
    context: PipelineContext,
    window_table: ir.Table,
    media_mapping: MediaMapping,
    override_config: EnrichmentSettings | None = None,
) -> ir.Table:
    """Execute enrichment for a window's table."""
    enrichment_context = EnrichmentRuntimeContext(
        cache=context.cache.enrichment,
        output_sink=context.output_sink,
        site_root=context.site_root,
        usage_tracker=context.usage_tracker,
        pii_prevention=None,
        task_store=context.task_store,
    )

    schedule_enrichment(
        window_table,
        media_mapping,
        override_config or context.config.enrichment,
        enrichment_context,
        run_id=context.run_id,
    )

    # Execute enrichment worker immediately (synchronous for now in pipeline)
    # The worker consumes tasks from the store until empty
    with EnrichmentWorker(context, enrichment_config=override_config) as worker:
        while True:
            processed = worker.run()
            if processed == 0:
                break

    return window_table


def _extract_adapter_info(ctx: PipelineContext) -> tuple[str, str]:
    """Extract content summary and generation instructions from adapter."""
    adapter = getattr(ctx, "adapter", None)
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


def _calculate_max_window_size(config: EgregoraConfig) -> int:
    """Calculate maximum window size based on LLM context window."""
    use_full_window = getattr(config.pipeline, "use_full_context_window", False)
    # Corresponds to a 1M token context window, expressed in characters
    full_context_window_size = 1_048_576

    max_tokens = full_context_window_size if use_full_window else config.pipeline.max_prompt_tokens

    # TODO: [Taskmaster] Externalize hardcoded configuration values.
    avg_tokens_per_message = 5
    buffer_ratio = 0.8
    return int((max_tokens * buffer_ratio) / avg_tokens_per_message)


def get_pending_conversations(dataset: PreparedPipelineData) -> Iterator[Conversation]:
    """Yield prepared conversations ready for processing.

    This generator handles:
    1. Window iteration
    2. Size validation and splitting (heuristic)
    3. Media processing
    4. Enrichment
    5. Command extraction (partial)
    """
    ctx = dataset.context
    max_window_size = _calculate_max_window_size(ctx.config)

    # Use a queue to handle splitting
    # Each item is (window, depth)
    queue: deque[tuple[Window, int]] = deque([(w, 0) for w in dataset.windows_iterator])

    max_depth = 5
    min_window_size = 5

    processed_count = 0
    max_windows = getattr(ctx.config.pipeline, "max_windows", None)
    if max_windows == 0:
        max_windows = None

    while queue:
        if max_windows is not None and processed_count >= max_windows:
            logger.info("Reached max_windows limit (%d). Stopping.", max_windows)
            break

        window, depth = queue.popleft()

        # Heuristic splitting check
        if window.size > max_window_size and depth < max_depth:
            # Too big, split immediately based on heuristic
            logger.info(
                "Window %d too large (%d > %d), splitting...",
                window.window_index,
                window.size,
                max_window_size,
            )
            num_splits = max(2, math.ceil(window.size / max_window_size))
            split_windows = split_window_into_n_parts(window, num_splits)
            # Add back to front of queue
            queue.extendleft(reversed([(w, depth + 1) for w in split_windows]))
            continue

        if window.size < min_window_size and depth > 0:
            logger.warning("Window too small after split (%d messages), attempting anyway", window.size)

        # ETL Step 1: Media Processing
        output_sink = ctx.output_sink
        if output_sink is None:
            # Should not happen if dataset is prepared correctly
            msg = "Output sink not initialized"
            raise ValueError(msg)

        url_context = ctx.url_context or UrlContext()
        window_table_processed, media_mapping = process_media_for_window(
            window_table=window.table,
            adapter=ctx.adapter,
            url_convention=output_sink.url_convention,
            url_context=url_context,
            zip_path=ctx.input_path,
        )

        # Persist media if enrichment disabled (otherwise enrichment handles it/updates it)
        if media_mapping and not dataset.enable_enrichment:
            for media_doc in media_mapping.values():
                try:
                    output_sink.persist(media_doc)
                except Exception as e:
                    logger.exception("Failed to write media file: %s", e)

        # ETL Step 2: Enrichment
        if dataset.enable_enrichment:
            enriched_table = perform_enrichment(ctx, window_table_processed, media_mapping)
        else:
            enriched_table = window_table_processed

        # Prepare metadata
        adapter_info = _extract_adapter_info(ctx)

        yield Conversation(
            window=window,
            messages_table=enriched_table,
            media_mapping=media_mapping,
            context=ctx,
            adapter_info=adapter_info,
            depth=depth,
        )
        processed_count += 1
