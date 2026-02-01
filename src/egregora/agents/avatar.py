"""Avatar download and validation for user profiles.

Simplified: URL-only format, saved to media/images/ like regular media.
Avatars go through regular media enrichment pipeline (no special moderation).
"""

from __future__ import annotations

import hashlib
import io
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from PIL import Image
from ratelimit import limits, sleep_and_retry

from egregora.agents.enricher import ensure_datetime
from egregora.agents.enrichment import enrich_avatar
from egregora.constants import AVATAR_NAMESPACE_UUID
from egregora.exceptions import EgregoraError
from egregora.input_adapters.whatsapp.commands import extract_commands
from egregora.knowledge.profiles import remove_profile_avatar, update_profile_avatar
from egregora.ops.media import (
    extract_urls,
)
from egregora.orchestration.cache import EnrichmentCache
from egregora.security.dns import SSRFValidationError, safe_dns_validation

if TYPE_CHECKING:
    from datetime import datetime

    from ibis.expr.types import Table

logger = logging.getLogger(__name__)
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_AVATAR_SIZE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096
DEFAULT_DOWNLOAD_TIMEOUT = 30.0
MAX_REDIRECT_HOPS = 10
DOWNLOAD_CHUNK_SIZE = 8192
WEBP_HEADER_SIZE = 12
MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",
}


class AvatarProcessingError(EgregoraError):
    """Error during avatar processing."""


def _create_secure_client(timeout: float = DEFAULT_DOWNLOAD_TIMEOUT) -> httpx.Client:
    """Create a configured httpx.Client with security controls.

    Note: SSRF validation is handled by safe_dns_validation context manager
    in download_avatar_from_url, not via event hooks.
    """
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        max_redirects=MAX_REDIRECT_HOPS,
    )


def _get_avatar_directory(media_dir: Path) -> Path:
    """Get or create the images directory for avatars.

    Simplified: avatars are just regular images, saved to media/images/ like all other images.

    Args:
        media_dir: Root media directory (e.g., site_root/media)

    Returns:
        Path to avatar images directory

    """
    avatar_dir = media_dir / "images"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    return avatar_dir


# TODO: [Taskmaster] Refactor: Move hardcoded UUID namespace to configuration
def _generate_avatar_uuid(content: bytes | bytearray) -> uuid.UUID:
    """Generate deterministic UUID for avatar based on content only.

    Same content = same UUID, regardless of which group/chat uses it.
    This enables global deduplication across all groups.
    """
    namespace = uuid.UUID(AVATAR_NAMESPACE_UUID)
    content_hash = hashlib.sha256(content).hexdigest()
    return uuid.uuid5(namespace, content_hash)


def _validate_image_format(filename: str) -> str:
    """Validate image format.

    Returns the file extension if valid.
    Raises AvatarProcessingError if invalid.
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        msg = f"Unsupported image format: {ext}. Supported formats: {', '.join(SUPPORTED_IMAGE_EXTENSIONS)}"
        raise AvatarProcessingError(msg)
    return ext


def _validate_image_content(content: bytes | bytearray, expected_mime: str) -> None:
    """Validate that image content matches expected MIME type using magic bytes.

    This prevents attacks where executable code is disguised with an image MIME type header.
    Can operate on partial content (first chunk) as long as it covers the header size.

    Args:
        content: The image file content (or start of it)
        expected_mime: The expected MIME type from Content-Type header

    Raises:
        AvatarProcessingError: If content doesn't match expected type

    """
    # Ensure we have enough bytes for the largest check
    if len(content) < WEBP_HEADER_SIZE:
        # If content is smaller than header size but it's the full file, we will fail anyway.
        # But if it's a chunk, we might need more.
        # However, DOWNLOAD_CHUNK_SIZE is 8192, which is > 12. So we assume chunks are large enough.
        pass

    for magic, mime_type in MAGIC_BYTES.items():
        if content.startswith(magic):
            if magic == b"RIFF":
                if len(content) < WEBP_HEADER_SIZE:
                    msg = "File too small to be valid WEBP"
                    raise AvatarProcessingError(msg)
                if content[8:12] == b"WEBP":
                    if expected_mime != "image/webp":
                        msg = f"Image content is WEBP but declared as {expected_mime}"
                        raise AvatarProcessingError(msg)
                    return
                msg = f"RIFF file is not WEBP format (expected {expected_mime})"
                raise AvatarProcessingError(msg)
            if mime_type != expected_mime:
                msg = f"Image content type mismatch: content appears to be {mime_type} but declared as {expected_mime}"
                raise AvatarProcessingError(msg)
            return
    msg = "Unable to verify image format. Content does not match any supported image type."
    raise AvatarProcessingError(msg)


def _check_dimensions(width: int, height: int) -> None:
    """Check if image dimensions are within allowed limits.

    Args:
        width: Image width in pixels
        height: Image height in pixels

    Raises:
        AvatarProcessingError: If dimensions exceed limits

    """
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        msg = f"Image dimensions too large: {width}x{height} pixels. Maximum allowed: {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION} pixels."
        raise AvatarProcessingError(msg)


def _validate_image_dimensions(content: bytes | bytearray) -> None:
    """Validate image dimensions to prevent memory exhaustion attacks.

    Extremely large dimensions could cause memory issues during image processing
    even if the file size is within limits (e.g., highly compressed images).

    Args:
        content: The image file content

    Raises:
        AvatarProcessingError: If dimensions exceed limits

    """
    try:
        img = Image.open(io.BytesIO(content))
        width, height = img.size
        _check_dimensions(width, height)
        logger.debug("Image dimensions validated: %sx%s pixels", width, height)
    except Exception as e:
        # Let AvatarProcessingError propagate unchanged (don't wrap it)
        if isinstance(e, AvatarProcessingError):
            raise
        msg = f"Failed to validate image dimensions: {e}"
        raise AvatarProcessingError(msg) from e


MIME_TYPE_TO_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def _get_extension_from_mime_type(content_type: str, url: str) -> str:
    """Get file extension from MIME type.

    Args:
        content_type: MIME type string
        url: Original URL (fallback for extension detection)

    Returns:
        File extension with leading dot

    """
    base_type = content_type.split(";")[0].strip()
    if base_type in MIME_TYPE_TO_EXTENSION:
        return MIME_TYPE_TO_EXTENSION[base_type]

    # Try efficient prefix matching if exact match fails
    for mime, ext in MIME_TYPE_TO_EXTENSION.items():
        if content_type.startswith(mime):
            return ext

    return _validate_image_format(url or ".jpg")


def _download_image_content(response: httpx.Response) -> tuple[bytearray, str]:
    """Download and validate image content from HTTP response.

    Optimized to:
    1. Validate magic bytes on first chunk (early rejection).
    2. Return bytearray to avoid memory copy.

    Args:
        response: HTTP response object

    Returns:
        Tuple of (content bytearray, mime type)

    Raises:
        AvatarProcessingError: If content is invalid or too large

    """
    content_type = response.headers.get("content-type", "").lower().split(";")[0].strip()
    if content_type not in ALLOWED_MIME_TYPES:
        msg = f"Invalid image MIME type: {content_type}. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        raise AvatarProcessingError(msg)

    content_length_str = response.headers.get("content-length")
    if content_length_str:
        try:
            content_length = int(content_length_str)
            if content_length > MAX_AVATAR_SIZE_BYTES:
                msg = f"Avatar image too large: {content_length} bytes (max: {MAX_AVATAR_SIZE_BYTES} bytes)"
                raise AvatarProcessingError(msg)
        except ValueError:
            logger.warning("Invalid Content-Length header: %s", content_length_str)

    content = bytearray()
    iterator = response.iter_bytes(chunk_size=DOWNLOAD_CHUNK_SIZE)

    # Process first chunk for early validation
    try:
        first_chunk = next(iterator)
        content.extend(first_chunk)
    except StopIteration:
        # Empty response
        pass

    # Validate magic bytes immediately (on first chunk or empty content)
    _validate_image_content(content, content_type)

    for chunk in iterator:
        content.extend(chunk)
        if len(content) > MAX_AVATAR_SIZE_BYTES:
            msg = f"Avatar image too large: exceeded {MAX_AVATAR_SIZE_BYTES} bytes during download"
            raise AvatarProcessingError(msg)

    return content, content_type


def _save_avatar_file(content: bytes | bytearray, avatar_uuid: uuid.UUID, ext: str, media_dir: Path) -> Path:
    """Save avatar content to file.

    Args:
        content: Avatar image content
        avatar_uuid: UUID for the avatar
        ext: File extension
        media_dir: Root media directory (e.g., site_root/media)

    Returns:
        Path to saved avatar file

    """
    avatar_dir = _get_avatar_directory(media_dir)
    avatar_path = avatar_dir / f"{avatar_uuid}{ext}"

    if avatar_path.exists():
        logger.info("Avatar already exists (deduplication): %s", avatar_path)
        return avatar_path

    try:
        with avatar_path.open("xb") as f:
            f.write(content)
        logger.info("Saved avatar to: %s", avatar_path)
    except FileExistsError:
        logger.info("Avatar created concurrently: %s", avatar_path)

    return avatar_path


def _fetch_and_validate_image(client: httpx.Client, url: str) -> tuple[bytearray, str]:
    """Fetch image from URL and validate it."""
    logger.info("Downloading avatar from URL: %s", url)
    with client.stream("GET", url) as response:
        response.raise_for_status()
        content, content_type = _download_image_content(response)

    # _validate_image_content is already called inside _download_image_content for early rejection
    _validate_image_dimensions(content)

    ext = _get_extension_from_mime_type(content_type, url)
    return content, ext


def _handle_download_error(e: Exception, url: str) -> None:
    """Handle errors occurring during avatar download."""
    if isinstance(e, AvatarProcessingError):
        raise e

    if isinstance(e, httpx.TooManyRedirects):
        msg = f"Too many redirects (>{MAX_REDIRECT_HOPS}) for URL: {url}"
        raise AvatarProcessingError(msg) from e

    if isinstance(e, httpx.HTTPError):
        # If the HTTP error was caused by our own validation, re-raise it directly
        if isinstance(e.__cause__, AvatarProcessingError):
            raise e.__cause__ from e
        if isinstance(e.__context__, AvatarProcessingError):
            raise e.__context__ from e
        logger.debug("HTTP error details: %s", e)
        msg = "Failed to download avatar. Please check the URL and try again."
        raise AvatarProcessingError(msg) from e

    if isinstance(e, OSError):
        logger.debug("File system error details: %s", e)
        msg = "Failed to save avatar due to file system error."
        raise AvatarProcessingError(msg) from e

    raise e  # Re-raise unexpected exceptions


def _download_avatar_with_client(client: httpx.Client, url: str, media_dir: Path) -> tuple[uuid.UUID, Path]:
    """Internal function to download avatar using an existing client."""
    try:
        content, ext = _fetch_and_validate_image(client, url)
        avatar_uuid = _generate_avatar_uuid(content)
        avatar_path = _save_avatar_file(content, avatar_uuid, ext, media_dir)
        return avatar_uuid, avatar_path
    except (AvatarProcessingError, httpx.HTTPError, OSError) as e:
        _handle_download_error(e, url)
        # _handle_download_error always raises, but static analysis might not know
        raise e


@sleep_and_retry
@limits(calls=10, period=60)
def download_avatar_from_url(
    url: str,
    media_dir: Path,
    timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
    client: httpx.Client | None = None,
) -> tuple[uuid.UUID, Path]:
    """Download avatar from URL and save to avatars directory.

    Args:
        url: URL of the avatar image
        media_dir: Root media directory (e.g., site_root/media)
        timeout: HTTP timeout in seconds
        client: Optional httpx.Client to reuse

    Returns:
        Tuple of (avatar_uuid, avatar_path)

    Raises:
        AvatarProcessingError: If download fails or image is invalid

    """
    try:
        with safe_dns_validation(url):
            if client:
                return _download_avatar_with_client(client, url, media_dir)

            with _create_secure_client(timeout) as new_client:
                return _download_avatar_with_client(new_client, url, media_dir)
    except SSRFValidationError as exc:
        raise AvatarProcessingError(str(exc)) from exc


@dataclass
class AvatarContext:
    """Context for avatar processing operations."""

    docs_dir: Path
    media_dir: Path
    profiles_dir: Path
    vision_model: str
    cache: EnrichmentCache | None = None


def _download_avatar_from_command(
    value: str | None,
    author_uuid: str,
    timestamp: datetime,
    context: AvatarContext,
    client: httpx.Client | None = None,
) -> str:
    """Download avatar from URL in command value and enrich it."""
    if not value:
        msg = "Avatar command requires a URL value"
        raise AvatarProcessingError(msg)

    urls = extract_urls(value)
    if not urls:
        msg = "No valid URL found in command value"
        raise AvatarProcessingError(msg)

    url = urls[0]
    _avatar_uuid, avatar_path = download_avatar_from_url(url=url, media_dir=context.media_dir, client=client)
    enrich_avatar(avatar_path, author_uuid, timestamp, context)
    return url


def process_avatar_commands(
    messages_table: Table,
    context: AvatarContext,
) -> dict[str, str]:
    """Process all avatar commands from messages table."""
    logger.info("Processing avatar commands from messages")
    commands = extract_commands(messages_table)
    avatar_commands = [cmd for cmd in commands if cmd.get("command", {}).get("target") == "avatar"]
    if not avatar_commands:
        logger.info("No avatar commands found")
        return {}

    logger.info("Found %s avatar command(s)", len(avatar_commands))
    results: dict[str, str] = {}

    with _create_secure_client() as client:
        for cmd_entry in avatar_commands:
            author_uuid = cmd_entry["author"]
            timestamp_raw = cmd_entry["timestamp"]
            command = cmd_entry["command"]
            cmd_type = command["command"]
            target = command["target"]
            if cmd_type in ("set", "unset") and target == "avatar":
                if cmd_type == "set":
                    timestamp_dt = ensure_datetime(timestamp_raw)
                    result = _process_set_avatar_command(
                        author_uuid=author_uuid,
                        timestamp=timestamp_dt,
                        context=context,
                        value=command.get("value"),
                        client=client,
                    )
                    results[author_uuid] = result
                elif cmd_type == "unset":
                    result = _process_unset_avatar_command(
                        author_uuid=author_uuid,
                        timestamp=str(timestamp_raw),
                        profiles_dir=context.profiles_dir,
                    )
                    results[author_uuid] = result
    return results


def _process_set_avatar_command(
    author_uuid: str,
    timestamp: datetime,
    context: AvatarContext,
    value: str | None = None,
    client: httpx.Client | None = None,
) -> str:
    """Process a 'set avatar' command with enrichment."""
    logger.info("Processing 'set avatar' command for %s", author_uuid)
    try:
        avatar_url = _download_avatar_from_command(value, author_uuid, timestamp, context, client=client)
        update_profile_avatar(
            author_uuid=author_uuid,
            avatar_url=avatar_url,
            timestamp=str(timestamp),
            profiles_dir=context.profiles_dir,
        )
    except AvatarProcessingError as exc:
        logger.exception("Failed to process avatar for %s", author_uuid)
        return f"❌ Failed to process avatar for {author_uuid}: {exc}"
    except Exception as exc:  # pragma: no cover - unexpected issues are logged
        logger.exception("Unexpected error processing avatar for %s", author_uuid)
        return f"❌ Unexpected error processing avatar for {author_uuid}: {exc}"
    else:
        return f"✅ Avatar set for {author_uuid}"


def _process_unset_avatar_command(author_uuid: str, timestamp: str, profiles_dir: Path) -> str:
    """Process an 'unset avatar' command."""
    logger.info("Processing 'unset avatar' command for %s", author_uuid)
    try:
        remove_profile_avatar(author_uuid=author_uuid, timestamp=str(timestamp), profiles_dir=profiles_dir)
    except Exception as exc:  # pragma: no cover - unexpected issues are logged
        logger.exception("Failed to remove avatar for %s", author_uuid)
        return f"❌ Failed to remove avatar for {author_uuid}: {exc}"
    else:
        return f"✅ Avatar removed for {author_uuid}"


__all__ = [
    "AvatarContext",
    "AvatarProcessingError",
    "download_avatar_from_url",
    "process_avatar_commands",
]
