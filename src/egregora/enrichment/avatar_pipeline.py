"""Avatar pipeline integration - processes avatar commands from messages.

Simplified approach: Only accept URL format, download to media/images/, store URL in profile.
Avatars go through regular media enrichment pipeline for LLM descriptions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from egregora.agents.shared.profiler import remove_profile_avatar, update_profile_avatar
from egregora.enrichment.agents import (
    MediaEnrichmentContext,
    create_media_enrichment_agent,
    load_file_as_binary_content,
)
from egregora.enrichment.avatar import AvatarProcessingError, download_avatar_from_url
from egregora.enrichment.media import detect_media_type, extract_urls
from egregora.sources.whatsapp.parser import extract_commands
from egregora.utils import EnrichmentCache, make_enrichment_cache_key

if TYPE_CHECKING:
    from pathlib import Path

    from ibis.expr.types import Table

logger = logging.getLogger(__name__)


def _ensure_datetime(timestamp: datetime | str) -> datetime:
    """Ensure timestamp is a datetime object.

    Args:
        timestamp: Either datetime or ISO string

    Returns:
        datetime object

    """
    if isinstance(timestamp, datetime):
        return timestamp
    if isinstance(timestamp, str):
        return datetime.fromisoformat(timestamp)
    msg = f"Unsupported timestamp type: {type(timestamp)}"
    raise TypeError(msg)


@dataclass
class AvatarContext:
    """Context for avatar processing operations - simplified."""

    docs_dir: Path
    media_dir: Path
    profiles_dir: Path
    vision_model: str  # For enrichment
    cache: EnrichmentCache | None = None  # Optional cache for enrichment


def _enrich_avatar(
    avatar_path: Path,
    author_uuid: str,
    timestamp: datetime,
    context: AvatarContext,
) -> None:
    """Enrich avatar with LLM description (regular media enrichment).

    Args:
        avatar_path: Path to downloaded avatar image
        author_uuid: Author who set the avatar
        timestamp: When the avatar was set
        context: Avatar processing context

    """
    # Check cache first
    cache_key = make_enrichment_cache_key(kind="media", identifier=str(avatar_path))
    if context.cache:
        cached = context.cache.load(cache_key)
        if cached and cached.get("markdown"):
            logger.info("Using cached enrichment for avatar: %s", avatar_path.name)
            enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
            enrichment_path.write_text(cached["markdown"], encoding="utf-8")
            return

    # Create enrichment agent
    media_enrichment_agent = create_media_enrichment_agent(context.vision_model)

    # Load avatar as binary content
    try:
        binary_content = load_file_as_binary_content(avatar_path)
    except (OSError, ValueError) as e:
        logger.warning("Failed to load avatar for enrichment: %s", e)
        return

    # Detect media type
    media_type = detect_media_type(avatar_path)
    if not media_type:
        logger.warning("Could not detect media type for avatar: %s", avatar_path.name)
        return

    # Create enrichment context
    try:
        media_path = avatar_path.relative_to(context.docs_dir)
    except ValueError:
        media_path = avatar_path

    enrichment_context = MediaEnrichmentContext(
        media_type=media_type,
        media_filename=avatar_path.name,
        media_path=str(media_path),
        original_message=f"Avatar set by {author_uuid}",
        sender_uuid=author_uuid,
        date=timestamp.strftime("%Y-%m-%d"),
        time=timestamp.strftime("%H:%M"),
    )

    # Run enrichment
    message_content = [
        "Analyze and enrich this avatar image. Provide a detailed description in markdown format.",
        binary_content,
    ]

    try:
        result = media_enrichment_agent.run_sync(message_content, deps=enrichment_context)
        output = getattr(result, "output", getattr(result, "data", result))
        markdown_content = output.markdown.strip()

        if not markdown_content:
            markdown_content = f"[No enrichment generated for avatar: {avatar_path.name}]"

        # Save enrichment markdown
        enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
        enrichment_path.write_text(markdown_content, encoding="utf-8")
        logger.info("Saved avatar enrichment to: %s", enrichment_path)

        # Cache the result
        if context.cache:
            context.cache.store(cache_key, {"markdown": markdown_content, "type": "media"})

    except Exception as e:
        logger.warning("Failed to enrich avatar %s: %s", avatar_path.name, e)


def _download_avatar_from_command(
    value: str | None,
    author_uuid: str,
    timestamp: datetime,
    context: AvatarContext,
) -> str:
    """Download avatar from URL in command value and enrich it.

    Args:
        value: Command value containing URL
        author_uuid: Author UUID for enrichment context
        timestamp: Timestamp for enrichment context
        context: Avatar processing context

    Returns:
        The avatar URL

    Raises:
        AvatarProcessingError: If no valid URL found

    """
    if not value:
        msg = "Avatar command requires a URL value"
        raise AvatarProcessingError(msg)

    urls = extract_urls(value)
    if not urls:
        msg = "No valid URL found in command value"
        raise AvatarProcessingError(msg)

    url = urls[0]
    # Download and save to media/images/ (same as regular media)
    # UUID is based on content only - global deduplication across all groups
    _avatar_uuid, avatar_path = download_avatar_from_url(url=url, media_dir=context.media_dir)

    # Enrich with regular media enrichment pipeline
    _enrich_avatar(avatar_path, author_uuid, timestamp, context)

    # Return the URL (this is what we store in the profile)
    return url


def process_avatar_commands(
    messages_table: Table,
    context: AvatarContext,
) -> dict[str, str]:
    """Process all avatar commands from messages table.

    Flow:
    1. Extract avatar commands
    2. For 'set avatar' commands:
       - Download image from URL to media/images/
       - Enrich with regular media enrichment (LLM description)
       - Store URL in profile
    3. For 'unset avatar' commands:
       - Remove avatar URL from profile

    Args:
        messages_table: Ibis table with message data
        context: Avatar processing context (paths, vision model, cache)

    Returns:
        Dict mapping author_uuid to result message

    """
    logger.info("Processing avatar commands from messages")
    commands = extract_commands(messages_table)
    avatar_commands = [cmd for cmd in commands if cmd.get("command", {}).get("target") == "avatar"]
    if not avatar_commands:
        logger.info("No avatar commands found")
        return {}
    logger.info("Found %s avatar command(s)", len(avatar_commands))
    results = {}
    for cmd_entry in avatar_commands:
        author_uuid = cmd_entry["author"]
        timestamp_raw = cmd_entry["timestamp"]
        command = cmd_entry["command"]
        cmd_type = command["command"]
        target = command["target"]
        if cmd_type in ("set", "unset") and target == "avatar":
            if cmd_type == "set":
                # Convert timestamp to datetime for enrichment
                timestamp = _ensure_datetime(timestamp_raw)
                result = _process_set_avatar_command(
                    author_uuid=author_uuid,
                    timestamp=timestamp,
                    context=context,
                    value=command.get("value"),
                )
                results[author_uuid] = result
            elif cmd_type == "unset":
                result = _process_unset_avatar_command(
                    author_uuid=author_uuid, timestamp=str(timestamp_raw), profiles_dir=context.profiles_dir
                )
                results[author_uuid] = result
    return results


def _process_set_avatar_command(
    author_uuid: str,
    timestamp: datetime,
    context: AvatarContext,
    value: str | None = None,
) -> str:
    """Process a 'set avatar' command with enrichment.

    Args:
        author_uuid: UUID of the author
        timestamp: Command timestamp
        context: Avatar processing context
        value: Command value containing URL

    Returns:
        Result message describing what happened

    """
    logger.info("Processing 'set avatar' command for %s", author_uuid)
    try:
        # Download avatar from URL to media/images/ and enrich it
        avatar_url = _download_avatar_from_command(value, author_uuid, timestamp, context)

        # Store just the URL in profile
        update_profile_avatar(
            author_uuid=author_uuid,
            avatar_url=avatar_url,
            timestamp=str(timestamp),
            profiles_dir=context.profiles_dir,
        )
    except AvatarProcessingError as e:
        logger.exception("Failed to process avatar for %s", author_uuid)
        return f"❌ Failed to process avatar for {author_uuid}: {e}"
    except Exception as e:
        logger.exception("Unexpected error processing avatar for %s", author_uuid)
        return f"❌ Unexpected error processing avatar for {author_uuid}: {e}"
    else:
        return f"✅ Avatar set for {author_uuid}"


def _process_unset_avatar_command(author_uuid: str, timestamp: str, profiles_dir: Path) -> str:
    """Process an 'unset avatar' command.

    Args:
        author_uuid: UUID of the author
        timestamp: Command timestamp
        profiles_dir: Directory where profiles are stored

    Returns:
        Result message describing what happened

    """
    logger.info("Processing 'unset avatar' command for %s", author_uuid)
    try:
        remove_profile_avatar(author_uuid=author_uuid, timestamp=str(timestamp), profiles_dir=profiles_dir)
    except Exception as e:
        logger.exception("Failed to remove avatar for %s", author_uuid)
        return f"❌ Failed to remove avatar for {author_uuid}: {e}"
    else:
        return f"✅ Avatar removed for {author_uuid}"


__all__ = ["AvatarContext", "process_avatar_commands"]
