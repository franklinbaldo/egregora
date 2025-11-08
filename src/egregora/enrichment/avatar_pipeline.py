"""Avatar pipeline integration - processes avatar commands from messages.

Simplified approach: Only accept URL format, download to media/images/, store URL in profile.
No special pipeline, enrichment, or moderation - avatars are just regular media.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from egregora.agents.tools.profiler import remove_profile_avatar, update_profile_avatar
from egregora.enrichment.avatar import AvatarProcessingError, download_avatar_from_url
from egregora.enrichment.media import extract_urls
from egregora.ingestion import extract_commands  # Phase 6: Re-exported from sources/whatsapp

if TYPE_CHECKING:
    from pathlib import Path

    from ibis.expr.types import Table

logger = logging.getLogger(__name__)


@dataclass
class AvatarContext:
    """Context for avatar processing operations - simplified."""

    docs_dir: Path
    profiles_dir: Path
    group_slug: str


def _download_avatar_from_command(value: str | None, context: AvatarContext) -> str:
    """Download avatar from URL in command value.

    Args:
        value: Command value containing URL
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
    download_avatar_from_url(url=url, docs_dir=context.docs_dir, group_slug=context.group_slug)

    # Return the URL (this is what we store in the profile)
    return url


def process_avatar_commands(
    messages_table: Table,
    context: AvatarContext,
) -> dict[str, str]:
    """Process all avatar commands from messages table.

    Simplified flow:
    1. Extract avatar commands
    2. For 'set avatar' commands:
       - Download image from URL to media/images/
       - Store URL in profile
    3. For 'unset avatar' commands:
       - Remove avatar URL from profile

    Args:
        messages_table: Ibis table with message data
        context: Avatar processing context with paths

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
        timestamp = cmd_entry["timestamp"]
        command = cmd_entry["command"]
        cmd_type = command["command"]
        target = command["target"]
        if cmd_type in ("set", "unset") and target == "avatar":
            if cmd_type == "set":
                result = _process_set_avatar_command(
                    author_uuid=author_uuid,
                    timestamp=timestamp,
                    context=context,
                    value=command.get("value"),
                )
                results[author_uuid] = result
            elif cmd_type == "unset":
                result = _process_unset_avatar_command(
                    author_uuid=author_uuid, timestamp=timestamp, profiles_dir=context.profiles_dir
                )
                results[author_uuid] = result
    return results


def _process_set_avatar_command(
    author_uuid: str,
    timestamp: str,
    context: AvatarContext,
    value: str | None = None,
) -> str:
    """Process a 'set avatar' command - simplified.

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
        # Download avatar from URL to media/images/
        avatar_url = _download_avatar_from_command(value, context)

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
