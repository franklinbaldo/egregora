"""Execution processor for individual conversation items.

This module handles the core execution logic for processing a single window/conversation,
orchestrating the writer agent, profile generator, and side effects.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from egregora.agents.commands import command_to_announcement, filter_commands
from egregora.agents.commands import extract_commands as extract_commands_list
from egregora.agents.profile.generator import generate_profile_posts
from egregora.agents.types import Message
from egregora.agents.writer import WindowProcessingParams, write_posts_for_window
from egregora.data_primitives.document import Document
from egregora.orchestration.factory import PipelineFactory
from egregora.orchestration.pipelines.coordination.background_tasks import process_background_tasks
from egregora.orchestration.pipelines.etl.preparation import Conversation

logger = logging.getLogger(__name__)


def _extract_messages(conversation: Conversation) -> list[Any]:
    """Extract messages list from conversation table."""
    try:
        executed = conversation.messages_table.execute()
        if hasattr(executed, "to_pylist"):
            return cast("list[Any]", executed.to_pylist())
        if hasattr(executed, "to_dict"):
            return cast("list[Any]", executed.to_dict(orient="records"))
        return []
    except (AttributeError, TypeError):
        try:
            return cast("list[Any]", conversation.messages_table.to_pylist())
        except (AttributeError, TypeError):
            return (
                cast("list[Any]", conversation.messages_table)
                if isinstance(conversation.messages_table, list)
                else []
            )


def process_item(conversation: Conversation) -> dict[str, dict[str, list[str]]]:
    """Execute the agent on an isolated conversation item.

    Args:
        conversation: Prepared conversation object containing window and context.

    Returns:
        Dict mapping window label to result dict containing 'posts' and 'profiles'.

    """
    ctx = conversation.context
    output_sink = ctx.output_sink

    # Extract commands (ETL/Processing boundary - commands are side effects)
    # We do this here or in generator? Generator does "data prep".
    # Commands might generate announcements which is "output".
    # But filtering commands from input to writer is "prep".

    # Convert table to list
    messages_list = _extract_messages(conversation)

    # Handle commands (Announcements)
    command_messages = extract_commands_list(messages_list)
    announcements_generated = 0
    if command_messages:
        for cmd_msg in command_messages:
            try:
                announcement = command_to_announcement(cmd_msg)
                if output_sink:
                    output_sink.persist(announcement)
                    announcements_generated += 1
            except Exception as exc:
                logger.exception("Failed to generate announcement: %s", exc)

    clean_messages_list = filter_commands(messages_list)
    # Convert to Message objects for strict typing
    messages_objects = [Message(**msg) for msg in clean_messages_list]

    # Prepare Resources
    resources = PipelineFactory.create_writer_resources(ctx)

    params = WindowProcessingParams(
        table=conversation.messages_table,
        messages=messages_objects,
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

    # EXECUTE WRITER
    # Note: We don't handle PromptTooLargeError here because we rely on heuristic splitting
    # in the generator. If it fails here, it fails.
    writer_result = write_posts_for_window(params)
    posts = cast("list[Any]", writer_result.get("posts", []))
    profiles = cast("list[Any]", writer_result.get("profiles", []))

    # Warn if writer processed messages but generated no posts
    if not posts and clean_messages_list:
        logger.warning(
            "⚠️ Writer agent processed %d messages but generated no posts for window %s. "
            "Check if write_post_tool was called by the agent.",
            len(clean_messages_list),
            f"{conversation.window.start_time:%Y-%m-%d %H:%M}",
        )

    # Persist generated posts
    # The writer agent returns documents (strings if pending).
    # Pending posts are handled by background worker?
    # The original runner logic didn't explicitly persist posts returned by `write_posts_for_window`.
    # Let's check `write_posts_for_window` in `src/egregora/agents/writer.py`.
    # It seems `write_posts_for_window` returns paths or IDs, and persistence happens inside tools.
    # However, `generate_profile_posts` returns Document objects that need persistence.
    # If `posts` contains Document objects, we should persist them.
    for post in posts:
        if hasattr(post, "document_id") and output_sink:  # Is a Document
            try:
                output_sink.persist(post)
            except Exception as exc:
                logger.exception("Failed to persist post: %s", exc)

    # EXECUTE PROFILE GENERATOR
    window_date = conversation.window.start_time.strftime("%Y-%m-%d")
    try:
        # Cast to list[Document] as we are running synchronously
        profile_docs = cast(
            "list[Document]",
            generate_profile_posts(ctx=ctx, messages=clean_messages_list, window_date=window_date),
        )
        for profile_doc in profile_docs:
            try:
                if output_sink:
                    output_sink.persist(profile_doc)
                    profiles.append(profile_doc.document_id)
            except Exception as exc:
                logger.exception("Failed to persist profile: %s", exc)
    except Exception as exc:
        logger.exception("Failed to generate profile posts: %s", exc)

    # Process background tasks (Banner, etc)
    process_background_tasks(ctx)

    # Logging
    window_label = f"{conversation.window.start_time:%Y-%m-%d %H:%M} to {conversation.window.end_time:%H:%M}"
    logger.info(
        "  [green]✔ Generated[/] %d posts, %d profiles, %d announcements for %s",
        len(posts),
        len(profiles),
        announcements_generated,
        window_label,
    )

    return {window_label: {"posts": posts, "profiles": profiles}}
