"""Avatar download and validation for user profiles.

Simplified: URL-only format, saved to media/images/ like regular media.
Avatars go through regular media enrichment pipeline (no special moderation).
"""

from __future__ import annotations

import hashlib
import io
import ipaddress
import logging
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image

from egregora.agents.shared.author_profiles import remove_profile_avatar, update_profile_avatar
from egregora.enrichment.agents import (
    MediaEnrichmentContext,
    create_media_enrichment_agent,
    load_file_as_binary_content,
)
from egregora.enrichment.media import detect_media_type, extract_urls
from egregora.sources.whatsapp.parser import extract_commands
from egregora.utils import EnrichmentCache, make_enrichment_cache_key

if TYPE_CHECKING:
    from ibis.expr.types import Table

logger = logging.getLogger(__name__)
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_AVATAR_SIZE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096
DEFAULT_DOWNLOAD_TIMEOUT = 30.0
MAX_REDIRECT_HOPS = 10
DOWNLOAD_CHUNK_SIZE = 8192
IP_VERSION_IPV6 = 6
IP_VERSION_IPV4 = 4
WEBP_HEADER_SIZE = 12
MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",
}
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
]


class AvatarProcessingError(Exception):
    """Error during avatar processing."""


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


def _validate_ip_address(ip_str: str, url: str) -> None:
    """Validate a single IP address against blocked ranges.

    Args:
        ip_str: IP address string to validate
        url: Original URL (for error messages)

    Raises:
        AvatarProcessingError: If IP is in a blocked range

    """
    try:
        ip_addr = ipaddress.ip_address(ip_str)
    except ValueError as e:
        msg = f"Invalid IP address '{ip_str}': {e}"
        raise AvatarProcessingError(msg) from e

    # Check for IPv4-mapped IPv6 addresses
    if ip_addr.version == IP_VERSION_IPV6 and ip_addr.ipv4_mapped:
        ipv4_addr = ip_addr.ipv4_mapped
        logger.debug("Detected IPv4-mapped address: %s -> %s", ip_addr, ipv4_addr)
        for blocked_range in BLOCKED_IP_RANGES:
            if blocked_range.version == IP_VERSION_IPV4 and ipv4_addr in blocked_range:
                logger.warning(
                    "⚠️  SSRF attempt blocked (IPv4-mapped): %s resolves to %s (maps to %s in blocked range %s)",
                    url,
                    ip_str,
                    ipv4_addr,
                    blocked_range,
                )
                msg = f"URL resolves to blocked IPv4-mapped address: {ip_str} (maps to {ipv4_addr} in range {blocked_range}). Access to private/internal networks is not allowed."
                raise AvatarProcessingError(msg)

    # Check against blocked ranges
    for blocked_range in BLOCKED_IP_RANGES:
        if ip_addr in blocked_range:
            logger.warning(
                "⚠️  SSRF attempt blocked: %s resolves to %s in blocked range %s",
                url,
                ip_str,
                blocked_range,
            )
            msg = f"URL resolves to blocked IP address: {ip_str} (in range {blocked_range}). Access to private/internal networks is not allowed."
            raise AvatarProcessingError(msg)


def _validate_url_for_ssrf(url: str) -> None:
    """Validate URL to prevent SSRF attacks.

    Checks:
    - Only HTTP/HTTPS schemes allowed
    - Resolves hostname to IP and blocks private/internal networks
    - Blocks localhost, link-local, and private IP ranges

    Args:
        url: URL to validate

    Raises:
        AvatarProcessingError: If URL is not safe to fetch

    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        msg = f"Invalid URL: {e}"
        raise AvatarProcessingError(msg) from e
    if parsed.scheme not in ("http", "https"):
        msg = f"Invalid URL scheme: {parsed.scheme}. Only HTTP and HTTPS are allowed."
        raise AvatarProcessingError(msg)
    hostname = parsed.hostname
    if not hostname:
        msg = "URL must have a hostname"
        raise AvatarProcessingError(msg)
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        ip_addresses = {info[4][0] for info in addr_info}
    except socket.gaierror as e:
        msg = f"Could not resolve hostname '{hostname}': {e}"
        raise AvatarProcessingError(msg) from e

    for ip_str in ip_addresses:
        _validate_ip_address(ip_str, url)

    logger.info("URL validation passed for: %s (resolves to: %s)", url, ", ".join(ip_addresses))


def _generate_avatar_uuid(content: bytes) -> uuid.UUID:
    """Generate deterministic UUID for avatar based on content only.

    Same content = same UUID, regardless of which group/chat uses it.
    This enables global deduplication across all groups.
    """
    # Use a fixed namespace for all egregora media
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # NAMESPACE_DNS
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


def _validate_image_content(content: bytes, expected_mime: str) -> None:
    """Validate that image content matches expected MIME type using magic bytes.

    This prevents attacks where executable code is disguised with an image MIME type header.

    Args:
        content: The image file content
        expected_mime: The expected MIME type from Content-Type header

    Raises:
        AvatarProcessingError: If content doesn't match expected type

    """
    for magic, mime_type in MAGIC_BYTES.items():
        if content.startswith(magic):
            if magic == b"RIFF" and len(content) >= WEBP_HEADER_SIZE:
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


def _validate_image_dimensions(content: bytes) -> None:
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
    except AvatarProcessingError:
        raise
    except Exception as e:
        msg = f"Failed to validate image dimensions: {e}"
        raise AvatarProcessingError(msg) from e


def _get_extension_from_mime_type(content_type: str, url: str) -> str:
    """Get file extension from MIME type.

    Args:
        content_type: MIME type string
        url: Original URL (fallback for extension detection)

    Returns:
        File extension with leading dot

    """
    if content_type.startswith("image/jpeg"):
        return ".jpg"
    if content_type.startswith("image/png"):
        return ".png"
    if content_type.startswith("image/gif"):
        return ".gif"
    if content_type.startswith("image/webp"):
        return ".webp"
    return _validate_image_format(url or ".jpg")


def _download_image_content(response: httpx.Response) -> tuple[bytes, str]:
    """Download and validate image content from HTTP response.

    Args:
        response: HTTP response object

    Returns:
        Tuple of (content bytes, mime type)

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
    for chunk in response.iter_bytes(chunk_size=DOWNLOAD_CHUNK_SIZE):
        content.extend(chunk)
        if len(content) > MAX_AVATAR_SIZE_BYTES:
            msg = f"Avatar image too large: exceeded {MAX_AVATAR_SIZE_BYTES} bytes during download"
            raise AvatarProcessingError(msg)

    return bytes(content), content_type


def _follow_redirects(client: httpx.Client, url: str) -> tuple[bytes, str]:
    """Follow HTTP redirects and download content.

    Args:
        client: HTTP client
        url: Starting URL

    Returns:
        Tuple of (content bytes, mime type)

    Raises:
        AvatarProcessingError: If too many redirects or download fails

    """
    current_url = url
    redirect_count = 0

    while redirect_count < MAX_REDIRECT_HOPS:
        with client.stream("GET", current_url) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_count += 1
                location = response.headers.get("location")
                if not location:
                    msg = "Redirect response missing Location header"
                    raise AvatarProcessingError(msg)
                next_url = urljoin(current_url, location)
                logger.info("Following redirect %s/%s: %s", redirect_count, MAX_REDIRECT_HOPS, next_url)
                _validate_url_for_ssrf(next_url)
                current_url = next_url
                continue

            response.raise_for_status()
            return _download_image_content(response)

    msg = f"Too many redirects (>{MAX_REDIRECT_HOPS})"
    raise AvatarProcessingError(msg)


def _save_avatar_file(content: bytes, avatar_uuid: uuid.UUID, ext: str, media_dir: Path) -> Path:
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


def download_avatar_from_url(
    url: str, media_dir: Path, timeout: float = DEFAULT_DOWNLOAD_TIMEOUT
) -> tuple[uuid.UUID, Path]:
    """Download avatar from URL and save to avatars directory.

    Args:
        url: URL of the avatar image
        media_dir: Root media directory (e.g., site_root/media)
        timeout: HTTP timeout in seconds

    Returns:
        Tuple of (avatar_uuid, avatar_path)

    Raises:
        AvatarProcessingError: If download fails or image is invalid

    """
    logger.info("Downloading avatar from URL: %s", url)
    _validate_url_for_ssrf(url)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            content, content_type = _follow_redirects(client, url)

        _validate_image_content(content, content_type)
        _validate_image_dimensions(content)

        ext = _get_extension_from_mime_type(content_type, url)
        avatar_uuid = _generate_avatar_uuid(content)
        avatar_path = _save_avatar_file(content, avatar_uuid, ext, media_dir)
    except httpx.HTTPError as e:
        logger.debug("HTTP error details: %s", e)
        msg = "Failed to download avatar. Please check the URL and try again."
        raise AvatarProcessingError(msg) from e
    except OSError as e:
        logger.debug("File system error details: %s", e)
        msg = "Failed to save avatar due to file system error."
        raise AvatarProcessingError(msg) from e
    else:
        return (avatar_uuid, avatar_path)


def _ensure_datetime(timestamp: datetime | str) -> datetime:
    """Ensure timestamp is a datetime object."""
    if isinstance(timestamp, datetime):
        return timestamp
    if isinstance(timestamp, str):
        return datetime.fromisoformat(timestamp)
    msg = f"Unsupported timestamp type: {type(timestamp)}"
    raise TypeError(msg)


@dataclass
class AvatarContext:
    """Context for avatar processing operations."""

    docs_dir: Path
    media_dir: Path
    profiles_dir: Path
    vision_model: str
    cache: EnrichmentCache | None = None


def _enrich_avatar(
    avatar_path: Path,
    author_uuid: str,
    timestamp: datetime,
    context: AvatarContext,
) -> None:
    """Enrich avatar with LLM description using the media enrichment agent."""
    cache_key = make_enrichment_cache_key(kind="media", identifier=str(avatar_path))
    if context.cache:
        cached = context.cache.load(cache_key)
        if cached and cached.get("markdown"):
            logger.info("Using cached enrichment for avatar: %s", avatar_path.name)
            enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
            enrichment_path.write_text(cached["markdown"], encoding="utf-8")
            return

    media_enrichment_agent = create_media_enrichment_agent(context.vision_model)

    try:
        binary_content = load_file_as_binary_content(avatar_path)
    except (OSError, ValueError) as exc:
        logger.warning("Failed to load avatar for enrichment: %s", exc)
        return

    media_type = detect_media_type(avatar_path)
    if not media_type:
        logger.warning("Could not detect media type for avatar: %s", avatar_path.name)
        return

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

        enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
        enrichment_path.write_text(markdown_content, encoding="utf-8")
        logger.info("Saved avatar enrichment to: %s", enrichment_path)

        if context.cache:
            context.cache.store(cache_key, {"markdown": markdown_content, "type": "media"})

    except Exception as exc:  # pragma: no cover - enrichment failures are logged
        logger.warning("Failed to enrich avatar %s: %s", avatar_path.name, exc)


def _download_avatar_from_command(
    value: str | None,
    author_uuid: str,
    timestamp: datetime,
    context: AvatarContext,
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
    _avatar_uuid, avatar_path = download_avatar_from_url(url=url, media_dir=context.media_dir)
    _enrich_avatar(avatar_path, author_uuid, timestamp, context)
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
    for cmd_entry in avatar_commands:
        author_uuid = cmd_entry["author"]
        timestamp_raw = cmd_entry["timestamp"]
        command = cmd_entry["command"]
        cmd_type = command["command"]
        target = command["target"]
        if cmd_type in ("set", "unset") and target == "avatar":
            if cmd_type == "set":
                timestamp_dt = _ensure_datetime(timestamp_raw)
                result = _process_set_avatar_command(
                    author_uuid=author_uuid,
                    timestamp=timestamp_dt,
                    context=context,
                    value=command.get("value"),
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
) -> str:
    """Process a 'set avatar' command with enrichment."""
    logger.info("Processing 'set avatar' command for %s", author_uuid)
    try:
        avatar_url = _download_avatar_from_command(value, author_uuid, timestamp, context)
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
