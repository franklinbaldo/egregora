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
from egregora.orchestration.context import PipelineContext
from egregora.orchestration.factory import PipelineFactory
from egregora.orchestration.pipelines.coordination.background_tasks import process_background_tasks
from egregora.orchestration.pipelines.etl.preparation import Conversation

logger = logging.getLogger(__name__)


def _convert_table_to_list(messages_table: Any) -> list[dict[str, Any]]:
    """Convert Ibis/Arrow table to list of dictionaries safely."""
    try:
        executed = messages_table.execute()
        if hasattr(executed, "to_pylist"):
            return executed.to_pylist()
        elif hasattr(executed, "to_dict"):
            return executed.to_dict(orient="records")
        return []
    except (AttributeError, TypeError):
        try:
            return messages_table.to_pylist()
        except (AttributeError, TypeError):
            return messages_table if isinstance(messages_table, list) else []


def _handle_announcements(command_messages: list[dict[str, Any]], output_sink: Any) -> int:
    """Process command messages and return count of generated announcements."""
    count = 0
    if not command_messages:
        return 0

    for cmd_msg in command_messages:
        try:
            announcement = command_to_announcement(cmd_msg)
            if output_sink:
                output_sink.persist(announcement)
                count += 1
        except Exception as exc:
            logger.exception("Failed to generate announcement: %s", exc)
    return count


def _persist_posts(posts: list[Any], output_sink: Any) -> None:
    """Persist posts if they are Document objects."""
    for post in posts:
        if hasattr(post, "document_id") and output_sink:  # Is a Document
            try:
                output_sink.persist(post)
            except Exception as exc:
                logger.exception("Failed to persist post: %s", exc)


def _generate_and_persist_profiles(
    ctx: Any, clean_messages_list: list[dict[str, Any]], window_date: str, output_sink: Any
) -> list[str]:
    """Generate profiles and persist them."""
    profiles_ids = []
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
                    profiles_ids.append(profile_doc.document_id)
            except Exception as exc:
                logger.exception("Failed to persist profile: %s", exc)
    except Exception as exc:
        logger.exception("Failed to generate profile posts: %s", exc)
    return profiles_ids


def process_item(conversation: Conversation) -> dict[str, dict[str, list[str]]]:
    """Execute the agent on an isolated conversation item.

    Args:
        conversation: Prepared conversation object containing window and context.

    Returns:
        Dict mapping window label to result dict containing 'posts' and 'profiles'.

    """
    ctx = conversation.context

<<<<<<< HEAD
    # 1. Convert messages
    messages_list = _convert_messages_to_list(conversation)

    # 2. Handle commands
    announcements_generated = _process_announcements(ctx, messages_list)

    # 3. Filter and Prepare Messages
    clean_messages_list = filter_commands(messages_list)
    messages_objects = [Message(**msg) for msg in clean_messages_list]

    # 4. Execute Writer
    posts, profiles = _execute_writer(ctx, conversation, messages_objects, clean_messages_list)

    # 5. Execute Profile Generator
    _execute_profile_generator(ctx, clean_messages_list, conversation, profiles)

    # 6. Background Tasks
    process_background_tasks(ctx)

    # 7. Log and Return
    window_label = f"{conversation.window.start_time:%Y-%m-%d %H:%M} to {conversation.window.end_time:%H:%M}"
    logger.info(
        "  [green]✔ Generated[/] %d posts, %d profiles, %d announcements for %s",
        len(posts),
        len(profiles),
        announcements_generated,
        window_label,
    )

    return {window_label: {"posts": posts, "profiles": profiles}}


def _convert_messages_to_list(conversation: Conversation) -> list[dict[str, Any]]:
    """Convert Ibis table to list of dicts safely."""
    try:
        executed = conversation.messages_table.execute()
        if hasattr(executed, "to_pylist"):
            return executed.to_pylist()
        if hasattr(executed, "to_dict"):
            return executed.to_dict(orient="records")
    except (AttributeError, TypeError):
        try:
            return conversation.messages_table.to_pylist()
        except (AttributeError, TypeError):
            if isinstance(conversation.messages_table, list):
                return conversation.messages_table
    return []
=======
    messages_list = _convert_table_to_list(conversation.messages_table)
>>>>>>> origin/pr/2856


def _process_announcements(ctx: PipelineContext, messages_list: list[dict[str, Any]]) -> int:
    """Extract and persist announcements from commands."""
    command_messages = extract_commands_list(messages_list)
<<<<<<< HEAD
    count = 0
    if command_messages:
        output_sink = ctx.output_sink
        for cmd_msg in command_messages:
            try:
                announcement = command_to_announcement(cmd_msg)
                if output_sink:
                    output_sink.persist(announcement)
                    count += 1
            except Exception as exc:
                logger.exception("Failed to generate announcement: %s", exc)
    return count
=======
    announcements_generated = _handle_announcements(command_messages, output_sink)
>>>>>>> origin/pr/2856


def _execute_writer(
    ctx: PipelineContext,
    conversation: Conversation,
    messages_objects: list[Message],
    clean_messages_list: list[dict[str, Any]],
) -> tuple[list[Any], list[Any]]:
    """Execute the writer agent for the window."""
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

<<<<<<< HEAD
=======
    # EXECUTE WRITER
>>>>>>> origin/pr/2856
    writer_result = write_posts_for_window(params)
    posts = cast("list[Any]", writer_result.get("posts", []))
    profiles = cast("list[Any]", writer_result.get("profiles", []))

    if not posts and clean_messages_list:
        logger.warning(
            "⚠️ Writer agent processed %d messages but generated no posts for window %s. "
            "Check if write_post_tool was called by the agent.",
            len(clean_messages_list),
            f"{conversation.window.start_time:%Y-%m-%d %H:%M}",
        )

<<<<<<< HEAD
    # Persist generated posts
    output_sink = ctx.output_sink
    for post in posts:
        if hasattr(post, "document_id") and output_sink:
            try:
                output_sink.persist(post)
            except Exception as exc:
                logger.exception("Failed to persist post: %s", exc)
    return posts, profiles
=======
    _persist_posts(posts, output_sink)
>>>>>>> origin/pr/2856


def _execute_profile_generator(
    ctx: PipelineContext,
    messages: list[dict[str, Any]],
    conversation: Conversation,
    profiles_list: list[Any],
) -> None:
    """Generate and persist profiles."""
    window_date = conversation.window.start_time.strftime("%Y-%m-%d")
<<<<<<< HEAD
    try:
        profile_docs = cast(
            "list[Document]",
            generate_profile_posts(ctx=ctx, messages=messages, window_date=window_date),
        )
        output_sink = ctx.output_sink
        for profile_doc in profile_docs:
            try:
                if output_sink:
                    output_sink.persist(profile_doc)
                    profiles_list.append(profile_doc.document_id)
            except Exception as exc:
                logger.exception("Failed to persist profile: %s", exc)
    except Exception as exc:
        logger.exception("Failed to generate profile posts: %s", exc)
=======
    new_profiles = _generate_and_persist_profiles(ctx, clean_messages_list, window_date, output_sink)
    profiles.extend(new_profiles)

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
>>>>>>> origin/pr/2856
