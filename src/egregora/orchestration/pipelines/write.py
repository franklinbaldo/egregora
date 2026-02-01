"""Write pipeline orchestration - executes the complete write workflow.

This module orchestrates the high-level flow for the 'write' command, coordinating:
- Input adapter selection and parsing
- Privacy and enrichment stages
- Content generation with WriterWorker
- Command processing and announcement generation
- Profile generation (Egregora writing ABOUT authors)
- Background task processing
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, cast

from rich.console import Console

from egregora.agents.commands import command_to_announcement, filter_commands
from egregora.agents.commands import extract_commands as extract_commands_list
from egregora.agents.formatting import build_conversation_xml
from egregora.agents.profile.generator import generate_profile_posts
from egregora.agents.types import Message, WriterResources
from egregora.agents.writer import WindowProcessingParams, write_posts_for_window
from egregora.data_primitives.document import Document
from egregora.database.utils import convert_ibis_table_to_list
from egregora.input_adapters import ADAPTER_REGISTRY
from egregora.input_adapters.exceptions import UnknownAdapterError
from egregora.orchestration.context import PipelineContext, PipelineRunParams
from egregora.orchestration.error_boundary import DefaultErrorBoundary
from egregora.orchestration.exceptions import (
    CommandAnnouncementError,
    OutputSinkError,
    ProfileGenerationError,
)
from egregora.orchestration.journal import create_journal_document, window_already_processed
from egregora.orchestration.pipelines.coordination.background_tasks import (
    generate_taxonomy_task,
    process_background_tasks,
)
from egregora.orchestration.pipelines.etl.preparation import (
    Conversation,
    get_pending_conversations,
    prepare_pipeline_data,
)
from egregora.orchestration.pipelines.etl.setup import pipeline_environment
from egregora.resources.prompts import PromptManager
from egregora.transformations.windowing import generate_window_signature

logger = logging.getLogger(__name__)
console = Console()

__all__ = ["run"]


def _process_commands(messages_list: list[dict[str, Any]], output_sink: Any) -> int:
    """Extract commands and generate announcements."""
    command_messages = extract_commands_list(messages_list)
    announcements_generated = 0
    if command_messages:
        for cmd_msg in command_messages:
            try:
                announcement = command_to_announcement(cmd_msg)
                output_sink.persist(announcement)
                announcements_generated += 1
            except Exception as exc:
                msg = f"Failed to generate announcement: {exc}"
                raise CommandAnnouncementError(msg) from exc
    return announcements_generated


def _check_window_processed(
    ctx: PipelineContext,
    messages_list: list[dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> tuple[bool, str]:
    """Check if window has already been processed using journal signature."""
    xml_content = build_conversation_xml(messages_list, None)
    template_content = PromptManager.get_template_content("writer.jinja", site_dir=ctx.site_root)
    signature = generate_window_signature(
        None,
        ctx.config,
        template_content,
        xml_content=xml_content,
    )

    if window_already_processed(ctx.output_sink, signature):
        window_label = f"{window_start:%Y-%m-%d %H:%M} to {window_end:%H:%M}"
        logger.info("⏭️  Skipping window %s (Already Processed)", window_label)
        return True, signature

    return False, signature


def _prepare_messages(
    messages_list: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[Message]]:
    """Filter commands and convert to Message DTOs."""
    clean_messages_list = filter_commands(messages_list)
    messages_dtos: list[Message] = []

    valid_keys = Message.model_fields.keys()

    for msg_dict in clean_messages_list:
        try:
            # Basic conversion - assuming keys match
            if "event_id" in msg_dict and "ts" in msg_dict and "author_uuid" in msg_dict:
                filtered_dict = {k: v for k, v in msg_dict.items() if k in valid_keys}
                messages_dtos.append(Message(**filtered_dict))
        except (ValueError, TypeError):
            continue

    return clean_messages_list, messages_dtos


def _run_writer_agent(
    ctx: PipelineContext,
    conversation: Conversation,
    messages_dtos: list[Message],
    clean_messages_list: list[dict[str, Any]],
) -> tuple[list[Any], list[str]]:
    """Execute writer agent and persist posts."""
    resources = WriterResources.from_pipeline_context(ctx)

    params = WindowProcessingParams(
        table=conversation.messages_table,
        messages=messages_dtos,
        window_start=conversation.window.start_time,
        window_end=conversation.window.end_time,
        resources=resources,
        config=ctx.config,
        cache=ctx.cache,
        adapter_content_summary=conversation.adapter_info[0],
        adapter_generation_instructions=conversation.adapter_info[1],
        run_id=str(ctx.run_id) if ctx.run_id else None,
        smoke_test=ctx.state.smoke_test,
    )

    writer_result = write_posts_for_window(params)
    posts = writer_result.get("posts", [])
    # Writer might return profile IDs, though currently it seems generate_profile_posts is separate
    # but `writer_result` dict has "profiles" key.
    initial_profiles = writer_result.get("profiles", [])

    if not posts and clean_messages_list:
        logger.warning(
            "⚠️ Writer agent processed %d messages but generated no posts for window %s. "
            "Check if write_post_tool was called by the agent.",
            len(clean_messages_list),
            f"{conversation.window.start_time:%Y-%m-%d %H:%M}",
        )

    for post in posts:
        if hasattr(post, "document_id"):
            try:
                ctx.output_sink.persist(post)
            except Exception as exc:
                msg = f"Failed to persist post {post.document_id}: {exc}"
                raise OutputSinkError(msg) from exc

    return posts, initial_profiles


def _run_profile_agent(
    ctx: PipelineContext,
    clean_messages_list: list[dict[str, Any]],
    window_date: str,
) -> list[str]:
    """Execute profile generator and persist profiles."""
    profiles: list[str] = []
    try:
        profile_docs = cast(
            "list[Document]",
            generate_profile_posts(ctx=ctx, messages=clean_messages_list, window_date=window_date),
        )
        for profile_doc in profile_docs:
            try:
                ctx.output_sink.persist(profile_doc)
                profiles.append(profile_doc.document_id)
            except Exception as exc:
                msg = f"Failed to persist profile {profile_doc.document_id}: {exc}"
                raise OutputSinkError(msg) from exc
    except Exception as exc:
        if isinstance(exc, OutputSinkError):
            raise
        msg = f"Failed to generate profile posts: {exc}"
        raise ProfileGenerationError(msg) from exc
    return profiles


def _persist_journal_entry(
    ctx: PipelineContext,
    signature: str,
    conversation: Conversation,
    posts_count: int,
    profiles_count: int,
) -> None:
    """Create and persist journal entry."""
    window_label = f"{conversation.window.start_time:%Y-%m-%d %H:%M} to {conversation.window.end_time:%H:%M}"
    try:
        journal = create_journal_document(
            signature=signature,
            run_id=ctx.run_id,
            window_start=conversation.window.start_time,
            window_end=conversation.window.end_time,
            model=ctx.config.models.writer,
            posts_generated=posts_count,
            profiles_updated=profiles_count,
        )
        ctx.output_sink.persist(journal)
    except Exception as e:
        logger.warning("Failed to persist JOURNAL for window %s: %s", window_label, e)


def process_item(conversation: Conversation) -> dict[str, dict[str, list[str]]]:
    """Execute the agent on an isolated conversation item."""
    ctx = conversation.context
    error_boundary = ctx.error_boundary or DefaultErrorBoundary()
    window_label = f"{conversation.window.start_time:%Y-%m-%d %H:%M} to {conversation.window.end_time:%H:%M}"

    # Convert table to list
    messages_list = convert_ibis_table_to_list(conversation.messages_table)

    # Check Journal / Deduplication
    is_processed, signature = _check_window_processed(
        ctx, messages_list, conversation.window.start_time, conversation.window.end_time
    )
    if is_processed:
        return {}

    # Handle commands
    announcements_generated = 0
    try:
        announcements_generated = _process_commands(messages_list, ctx.output_sink)
    except Exception as e:
        error_boundary.handle_command_error(e, window_label)

    # Prepare messages
    clean_messages_list, messages_dtos = _prepare_messages(messages_list)

    # Execute Writer
    posts: list[Any] = []
    profiles: list[str] = []
    try:
        posts, profiles = _run_writer_agent(ctx, conversation, messages_dtos, clean_messages_list)
    except Exception as e:
        error_boundary.handle_writer_error(e, window_label)

    # Execute Profile Generator
    try:
        window_date = conversation.window.start_time.strftime("%Y-%m-%d")
        new_profiles = _run_profile_agent(ctx, clean_messages_list, window_date)
        profiles.extend(new_profiles)
    except Exception as e:
        error_boundary.handle_profile_error(e, window_label)

    # Process background tasks
    try:
        process_background_tasks(ctx)
    except Exception as e:
        error_boundary.handle_enrichment_error(e, window_label)

    # Logging
    logger.info(
        "  [green]✔ Generated[/] %d posts, %d profiles, %d announcements for %s",
        len(posts),
        len(profiles),
        announcements_generated,
        window_label,
    )

    # Persist Journal
    try:
        _persist_journal_entry(ctx, signature, conversation, len(posts), len(profiles))
    except Exception as e:
        error_boundary.handle_journal_error(e, window_label)

    return {window_label: {"posts": posts, "profiles": profiles}}


def run(run_params: PipelineRunParams) -> dict[str, dict[str, list[str]]]:
    """Run the complete write pipeline workflow.

    Args:
        run_params: Aggregated pipeline run parameters

    Returns:
        Dict mapping window labels to {'posts': [...], 'profiles': [...]}

    """
    logger.info("[bold cyan]🚀 Starting pipeline for source:[/] %s", run_params.source_type)

    # Create adapter with config for privacy settings
    # Instead of using singleton from registry, instantiate with config
    adapter_cls = ADAPTER_REGISTRY.get(run_params.source_type)
    if adapter_cls is None:
        raise UnknownAdapterError(run_params.source_type)

    # Instantiate adapter with config if it supports it (WhatsApp does)
    try:
        adapter = adapter_cls(config=run_params.config)
    except TypeError:
        # Fallback for adapters that don't accept config parameter
        adapter = adapter_cls()

    with pipeline_environment(run_params) as ctx:
        try:
            dataset = prepare_pipeline_data(adapter, run_params, ctx)

            results = {}
            max_processed_timestamp: datetime | None = None

            # New simplified loop: Iterator (ETL) -> Process (Execution)
            for conversation in get_pending_conversations(dataset):
                item_results = process_item(conversation)
                results.update(item_results)

                # Track max timestamp for checkpoint
                if max_processed_timestamp is None or conversation.window.end_time > max_processed_timestamp:
                    max_processed_timestamp = conversation.window.end_time

            generate_taxonomy_task(dataset)

            # Final pass for any lingering background tasks
            process_background_tasks(dataset.context)

            # Regenerate tags page with word cloud visualization
            if hasattr(dataset.context.output_sink, "regenerate_tags_page"):
                try:
                    logger.info("[bold cyan]🏷️  Regenerating tags page with word cloud...[/]")
                    dataset.context.output_sink.regenerate_tags_page()
                except (OSError, AttributeError, TypeError) as e:
                    logger.warning("Failed to regenerate tags page: %s", e)

            logger.info("[bold green]🎉 Pipeline completed successfully![/]")

        except KeyboardInterrupt:
            logger.warning("[yellow]⚠️  Pipeline cancelled by user (Ctrl+C)[/]")
            raise  # Re-raise to allow proper cleanup

        return results
