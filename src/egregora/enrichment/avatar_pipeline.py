"""Avatar pipeline integration - processes avatar commands from messages."""

from __future__ import annotations

import logging
from pathlib import Path

from google import genai
from ibis.expr.types import Table

from ..agents.tools.profiler import remove_profile_avatar, update_profile_avatar
from ..enrichment.media import extract_urls, find_media_references
from ..ingestion.parser import extract_commands
from .avatar import (
    AvatarProcessingError,
    download_avatar_from_url,
    enrich_and_moderate_avatar,
    extract_avatar_from_zip,
)

logger = logging.getLogger(__name__)


def process_avatar_commands(  # noqa: PLR0913
    messages_table: Table,
    zip_path: Path | None,
    docs_dir: Path,
    profiles_dir: Path,
    group_slug: str,
    vision_client: genai.Client,
    model: str = "gemini-2.0-flash-exp",
) -> dict[str, str]:
    """
    Process all avatar commands from messages table.

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
        zip_path: Path to WhatsApp export ZIP (optional, for extracting attachments)
        docs_dir: MkDocs docs directory
        profiles_dir: Directory where profiles are stored
        group_slug: Group slug for UUID namespace
        vision_client: Gemini client for enrichment
        model: Model name for vision processing

    Returns:
        Dict mapping author_uuid to result message
    """
    logger.info("Processing avatar commands from messages")

    # Extract all commands from messages
    commands = extract_commands(messages_table)

    avatar_commands = [cmd for cmd in commands if cmd.get("command", {}).get("target") == "avatar"]

    if not avatar_commands:
        logger.info("No avatar commands found")
        return {}

    logger.info(f"Found {len(avatar_commands)} avatar command(s)")

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
                    zip_path=zip_path,
                    docs_dir=docs_dir,
                    profiles_dir=profiles_dir,
                    group_slug=group_slug,
                    vision_client=vision_client,
                    model=model,
                    value=command.get("value"),
                )
                results[author_uuid] = result

            elif cmd_type == "unset":
                result = _process_unset_avatar_command(
                    author_uuid=author_uuid,
                    timestamp=timestamp,
                    profiles_dir=profiles_dir,
                )
                results[author_uuid] = result

    return results


def _process_set_avatar_command(  # noqa: PLR0913, PLR0912
    author_uuid: str,
    timestamp: str,
    message: str,
    zip_path: Path | None,
    docs_dir: Path,
    profiles_dir: Path,
    group_slug: str,
    vision_client: genai.Client,
    model: str,
    value: str | None = None,
) -> str:
    """
    Process a 'set avatar' command.

    Returns:
        Result message describing what happened
    """
    logger.info(f"Processing 'set avatar' command for {author_uuid}")

    try:
        # Determine avatar source: URL or media attachment
        avatar_uuid = None
        avatar_path = None

        # Check if value is a URL
        if value:
            urls = extract_urls(value)
            if urls:
                # Download from URL
                logger.info(f"Downloading avatar from URL for {author_uuid}")
                avatar_uuid, avatar_path = download_avatar_from_url(
                    url=urls[0],
                    docs_dir=docs_dir,
                    group_slug=group_slug,
                )
            else:
                # Value might be a media filename
                media_refs = find_media_references(message)
                if media_refs and zip_path:
                    logger.info(f"Extracting avatar from ZIP for {author_uuid}")
                    avatar_uuid, avatar_path = extract_avatar_from_zip(
                        zip_path=zip_path,
                        media_filename=media_refs[0],
                        docs_dir=docs_dir,
                        group_slug=group_slug,
                    )
                else:
                    raise AvatarProcessingError("No valid URL or media attachment found for avatar")
        else:
            # No value provided, check for media attachment in message
            media_refs = find_media_references(message)
            if media_refs and zip_path:
                logger.info(f"Extracting avatar from ZIP for {author_uuid}")
                avatar_uuid, avatar_path = extract_avatar_from_zip(
                    zip_path=zip_path,
                    media_filename=media_refs[0],
                    docs_dir=docs_dir,
                    group_slug=group_slug,
                )
            else:
                raise AvatarProcessingError("No media attachment found for avatar command")

        # Enrich and moderate the avatar
        logger.info(f"Enriching and moderating avatar for {author_uuid}")
        moderation_result = enrich_and_moderate_avatar(
            avatar_uuid=avatar_uuid,
            avatar_path=avatar_path,
            docs_dir=docs_dir,
            vision_client=vision_client,
            model=model,
        )

        # Update profile with moderation result
        update_profile_avatar(
            author_uuid=author_uuid,
            avatar_uuid=moderation_result.avatar_uuid,
            avatar_path=moderation_result.avatar_path,
            moderation_status=moderation_result.status,
            moderation_reason=moderation_result.reason,
            timestamp=str(timestamp),
            profiles_dir=profiles_dir,
        )

        if moderation_result.status == "approved":
            return f"✅ Avatar approved and set for {author_uuid}"
        elif moderation_result.status == "questionable":
            return f"⚠️ Avatar requires manual review for {author_uuid}: {moderation_result.reason}"
        else:  # blocked
            return f"❌ Avatar blocked for {author_uuid}: {moderation_result.reason}"

    except AvatarProcessingError as e:
        logger.error(f"Failed to process avatar for {author_uuid}: {e}")

        # Clean up avatar and enrichment files if processing failed
        # Note: If enrichment succeeded but later steps failed, files may still exist
        if avatar_path and avatar_path.exists():
            try:
                avatar_path.unlink(missing_ok=True)
                logger.info(f"Cleaned up avatar file after processing failure: {avatar_path}")
            except OSError as cleanup_error:
                logger.error(f"Failed to clean up avatar {avatar_path}: {cleanup_error}")

            # Also clean up enrichment file if it exists
            try:
                enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
                if enrichment_path.exists():
                    enrichment_path.unlink(missing_ok=True)
                    logger.info(f"Cleaned up enrichment file after processing failure: {enrichment_path}")
            except OSError as cleanup_error:
                logger.error(f"Failed to clean up enrichment file: {cleanup_error}")

        return f"❌ Failed to process avatar for {author_uuid}: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error processing avatar for {author_uuid}")

        # Clean up avatar and enrichment files if processing failed
        if avatar_path and avatar_path.exists():
            try:
                avatar_path.unlink(missing_ok=True)
                logger.info(f"Cleaned up avatar file after unexpected error: {avatar_path}")
            except OSError as cleanup_error:
                logger.error(f"Failed to clean up avatar {avatar_path}: {cleanup_error}")

            # Also clean up enrichment file if it exists
            try:
                enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
                if enrichment_path.exists():
                    enrichment_path.unlink(missing_ok=True)
                    logger.info(f"Cleaned up enrichment file after unexpected error: {enrichment_path}")
            except OSError as cleanup_error:
                logger.error(f"Failed to clean up enrichment file: {cleanup_error}")

        return f"❌ Unexpected error processing avatar for {author_uuid}: {e}"


def _process_unset_avatar_command(
    author_uuid: str,
    timestamp: str,
    profiles_dir: Path,
) -> str:
    """
    Process an 'unset avatar' command.

    Returns:
        Result message describing what happened
    """
    logger.info(f"Processing 'unset avatar' command for {author_uuid}")

    try:
        remove_profile_avatar(
            author_uuid=author_uuid,
            timestamp=str(timestamp),
            profiles_dir=profiles_dir,
        )
        return f"✅ Avatar removed for {author_uuid}"

    except Exception as e:
        logger.exception(f"Failed to remove avatar for {author_uuid}")
        return f"❌ Failed to remove avatar for {author_uuid}: {e}"


__all__ = ["process_avatar_commands"]
