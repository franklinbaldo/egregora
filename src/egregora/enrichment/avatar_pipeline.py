"""Avatar pipeline integration - processes avatar commands from messages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from egregora.agents.tools.profiler import remove_profile_avatar, update_profile_avatar
from egregora.enrichment.avatar import (
    AvatarProcessingError,
    download_avatar_from_url,
    enrich_and_moderate_avatar,
)
from egregora.enrichment.media import extract_urls, find_media_references
from egregora.ingestion import extract_commands  # Phase 6: Re-exported from sources/whatsapp

if TYPE_CHECKING:
    from pathlib import Path

    from google import genai
    from ibis.expr.types import Table

logger = logging.getLogger(__name__)


@dataclass
class AvatarContext:
    """Context for avatar processing operations."""

    docs_dir: Path
    profiles_dir: Path
    group_slug: str
    vision_client: genai.Client
    model: str
    adapter: any  # SourceAdapter - avoiding circular import
    input_path: Path


def _acquire_avatar_from_url(value: str, context: AvatarContext) -> tuple[str, Path]:
    """Acquire avatar from URL in command value.

    Args:
        value: Command value containing URL
        context: Avatar processing context

    Returns:
        Tuple of (avatar_uuid, avatar_path)

    Raises:
        AvatarProcessingError: If no valid URL found

    """
    urls = extract_urls(value)
    if urls:
        return download_avatar_from_url(url=urls[0], docs_dir=context.docs_dir, group_slug=context.group_slug)
    msg = "No valid URL found in command value"
    raise AvatarProcessingError(msg)


def _process_avatar_file(temp_file: Path, context: AvatarContext) -> tuple[str, Path]:
    """Process a delivered avatar file and save it.

    Args:
        temp_file: Path to temporary avatar file
        context: Avatar processing context

    Returns:
        Tuple of (avatar_uuid, avatar_path)

    Raises:
        AvatarProcessingError: If validation fails

    """
    from egregora.enrichment.avatar import (
        _generate_avatar_uuid,
        _get_mime_type_from_extension,
        _save_avatar_file,
        _validate_image_content,
        _validate_image_dimensions,
        _validate_image_format,
    )

    # Validate and process the file
    ext = _validate_image_format(temp_file.name)
    content = temp_file.read_bytes()

    mime_type = _get_mime_type_from_extension(ext)
    _validate_image_content(content, mime_type)
    _validate_image_dimensions(content)

    avatar_uuid = _generate_avatar_uuid(content, context.group_slug)
    avatar_path = _save_avatar_file(content, avatar_uuid, ext, context.docs_dir)

    return (str(avatar_uuid), avatar_path)


def _acquire_avatar_from_adapter(message: str, context: AvatarContext) -> tuple[str, Path]:
    """Acquire avatar from media via source adapter.

    Args:
        message: Message text containing media reference
        context: Avatar processing context

    Returns:
        Tuple of (avatar_uuid, avatar_path)

    Raises:
        AvatarProcessingError: If no media reference or delivery fails

    """
    import tempfile

    media_refs = find_media_references(message)
    if not media_refs:
        msg = "No media attachment found for avatar command"
        raise AvatarProcessingError(msg)

    # Use adapter.deliver_media() to get the file (source-agnostic)
    with tempfile.TemporaryDirectory(prefix="egregora-avatar-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        adapter_kwargs = {
            "zip_path": context.input_path,
            "input_path": context.input_path,
        }
        delivered_file = context.adapter.deliver_media(
            media_reference=media_refs[0],
            temp_dir=temp_dir,
            **adapter_kwargs,
        )

        if delivered_file is None or not delivered_file.exists():
            msg = f"Failed to deliver media file: {media_refs[0]}"
            raise AvatarProcessingError(msg)

        # Now process the delivered file as an avatar
        return _process_avatar_file(delivered_file, context)


def _cleanup_avatar_files(avatar_path: Path) -> None:
    """Clean up avatar and enrichment files after processing failure.

    Args:
        avatar_path: Path to avatar file to clean up

    """
    if not (avatar_path and avatar_path.exists()):
        return

    try:
        avatar_path.unlink(missing_ok=True)
        logger.info("Cleaned up avatar file: %s", avatar_path)
    except OSError:
        logger.exception("Failed to clean up avatar %s", avatar_path)

    try:
        enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
        if enrichment_path.exists():
            enrichment_path.unlink(missing_ok=True)
            logger.info("Cleaned up enrichment file: %s", enrichment_path)
    except OSError:
        logger.exception("Failed to clean up enrichment file")


def _acquire_avatar_source(
    value: str | None,
    message: str,
    context: AvatarContext,
    author_uuid: str,
) -> tuple[str, Path]:
    """Acquire avatar from URL or adapter media delivery.

    Args:
        value: Optional command value (may contain URL)
        message: Message text (may contain media reference)
        context: Avatar processing context
        author_uuid: Author UUID for logging

    Returns:
        Tuple of (avatar_uuid, avatar_path)

    Raises:
        AvatarProcessingError: If no valid avatar source found

    """
    if value:
        urls = extract_urls(value)
        if urls:
            logger.info("Downloading avatar from URL for %s", author_uuid)
            return _acquire_avatar_from_url(value, context)
        # Fall through to adapter extraction if no URL in value
    logger.info("Extracting avatar via adapter for %s", author_uuid)
    return _acquire_avatar_from_adapter(message, context)


def process_avatar_commands(
    messages_table: Table,
    context: AvatarContext,
) -> dict[str, str]:
    """Process all avatar commands from messages table.

    This function:
    1. Extracts avatar commands from messages
    2. For 'set avatar' commands:
       - Downloads/extracts the avatar image
       - Enriches with AI moderation
       - Updates profile if approved
    3. For 'unset avatar' commands:
       - Removes avatar from profile

    Args:
        messages_table: Ibis table with message data
        context: Avatar processing context with paths and clients

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
        message = cmd_entry.get("message", "")
        cmd_type = command["command"]
        target = command["target"]
        if cmd_type in ("set", "unset") and target == "avatar":
            if cmd_type == "set":
                result = _process_set_avatar_command(
                    author_uuid=author_uuid,
                    timestamp=timestamp,
                    message=message,
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
    message: str,
    context: AvatarContext,
    value: str | None = None,
) -> str:
    """Process a 'set avatar' command.

    Args:
        author_uuid: UUID of the author
        timestamp: Command timestamp
        message: Message text
        context: Avatar processing context
        value: Optional command value

    Returns:
        Result message describing what happened

    """
    logger.info("Processing 'set avatar' command for %s", author_uuid)
    avatar_path = None
    try:
        avatar_uuid, avatar_path = _acquire_avatar_source(value, message, context, author_uuid)
        logger.info("Enriching and moderating avatar for %s", author_uuid)
        moderation_result = enrich_and_moderate_avatar(
            avatar_uuid=avatar_uuid,
            avatar_path=avatar_path,
            docs_dir=context.docs_dir,
            model=context.model,
        )
        update_profile_avatar(
            author_uuid=author_uuid,
            avatar_uuid=moderation_result.avatar_uuid,
            avatar_path=moderation_result.avatar_path,
            moderation_status=moderation_result.status,
            moderation_reason=moderation_result.reason,
            timestamp=str(timestamp),
            profiles_dir=context.profiles_dir,
        )
    except AvatarProcessingError as e:
        logger.exception("Failed to process avatar for %s", author_uuid)
        _cleanup_avatar_files(avatar_path)
        return f"❌ Failed to process avatar for {author_uuid}: {e}"
    except Exception as e:
        logger.exception("Unexpected error processing avatar for %s", author_uuid)
        _cleanup_avatar_files(avatar_path)
        return f"❌ Unexpected error processing avatar for {author_uuid}: {e}"
    else:
        if moderation_result.status == "approved":
            return f"✅ Avatar approved and set for {author_uuid}"
        if moderation_result.status == "questionable":
            return f"⚠️ Avatar requires manual review for {author_uuid}: {moderation_result.reason}"
        return f"❌ Avatar blocked for {author_uuid}: {moderation_result.reason}"


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
