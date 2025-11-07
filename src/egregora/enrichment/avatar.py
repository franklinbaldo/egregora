"""Avatar processing with moderation for user profiles."""

from __future__ import annotations

import hashlib
import io
import ipaddress
import logging
import socket
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image

from egregora.config import MEDIA_DIR_NAME
from egregora.enrichment.agents import (
    AvatarEnrichmentContext,
    create_avatar_enrichment_agent,
    load_file_as_binary_content,
)

logger = logging.getLogger(__name__)
ModerationStatus = Literal["approved", "questionable", "blocked"]
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


@dataclass
class AvatarModerationResult:
    """Result of avatar moderation."""

    status: ModerationStatus
    reason: str
    has_pii: bool
    avatar_uuid: str
    avatar_path: Path
    enrichment_path: Path


class AvatarProcessingError(Exception):
    """Error during avatar processing."""


def _get_avatar_directory(docs_dir: Path) -> Path:
    """Get or create the avatars directory."""
    avatar_dir = docs_dir / MEDIA_DIR_NAME / "avatars"
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


def _generate_avatar_uuid(content: bytes, group_slug: str) -> uuid.UUID:
    """Generate deterministic UUID for avatar based on content."""
    namespace = uuid.uuid5(uuid.NAMESPACE_DNS, group_slug)
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


def _save_avatar_file(content: bytes, avatar_uuid: uuid.UUID, ext: str, docs_dir: Path) -> Path:
    """Save avatar content to file.

    Args:
        content: Avatar image content
        avatar_uuid: UUID for the avatar
        ext: File extension
        docs_dir: MkDocs docs directory

    Returns:
        Path to saved avatar file

    """
    avatar_dir = _get_avatar_directory(docs_dir)
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
    url: str, docs_dir: Path, group_slug: str, timeout: float = DEFAULT_DOWNLOAD_TIMEOUT
) -> tuple[uuid.UUID, Path]:
    """Download avatar from URL and save to avatars directory.

    Args:
        url: URL of the avatar image
        docs_dir: MkDocs docs directory
        group_slug: Group slug for UUID namespace
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
        avatar_uuid = _generate_avatar_uuid(content, group_slug)
        avatar_path = _save_avatar_file(content, avatar_uuid, ext, docs_dir)
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


def _get_mime_type_from_extension(ext: str) -> str:
    """Get MIME type from file extension.

    Args:
        ext: File extension (e.g., '.jpg')

    Returns:
        MIME type string

    Raises:
        AvatarProcessingError: If extension is not supported

    """
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".gif":
        return "image/gif"
    if ext == ".webp":
        return "image/webp"
    msg = f"Unsupported extension: {ext}"
    raise AvatarProcessingError(msg)


def _find_file_in_zip(zf: zipfile.ZipFile, media_filename: str) -> bytes:
    """Find and extract file from ZIP archive.

    Args:
        zf: Open ZIP file object
        media_filename: Name of file to find

    Returns:
        File content as bytes

    Raises:
        AvatarProcessingError: If file not found or too large

    """
    for info in zf.infolist():
        if info.is_dir():
            continue

        # Security check for path traversal
        if ".." in info.filename or info.filename.startswith("/"):
            logger.warning("Skipping suspicious ZIP entry with path traversal: %s", info.filename)
            continue

        filename = Path(info.filename).name
        if filename == media_filename:
            if info.file_size > MAX_AVATAR_SIZE_BYTES:
                msg = f"Avatar image too large: {info.file_size} bytes (max: {MAX_AVATAR_SIZE_BYTES} bytes)"
                raise AvatarProcessingError(msg)
            return zf.read(info)

    msg = f"Media file not found in ZIP: {media_filename}"
    raise AvatarProcessingError(msg)


def extract_avatar_from_zip(
    zip_path: Path, media_filename: str, docs_dir: Path, group_slug: str
) -> tuple[uuid.UUID, Path]:
    """Extract avatar image from WhatsApp ZIP export.

    Args:
        zip_path: Path to WhatsApp export ZIP
        media_filename: Filename of the media in the ZIP
        docs_dir: MkDocs docs directory
        group_slug: Group slug for UUID namespace

    Returns:
        Tuple of (avatar_uuid, avatar_path)

    Raises:
        AvatarProcessingError: If extraction fails or image is invalid

    """
    logger.info("Extracting avatar from ZIP: %s", media_filename)
    try:
        ext = _validate_image_format(media_filename)
        with zipfile.ZipFile(zip_path, "r") as zf:
            content = _find_file_in_zip(zf, media_filename)

        mime_type = _get_mime_type_from_extension(ext)
        _validate_image_content(content, mime_type)
        _validate_image_dimensions(content)

        avatar_uuid = _generate_avatar_uuid(content, group_slug)
        avatar_path = _save_avatar_file(content, avatar_uuid, ext, docs_dir)
    except zipfile.BadZipFile as e:
        msg = f"Invalid ZIP file: {e}"
        raise AvatarProcessingError(msg) from e
    except OSError as e:
        msg = f"Failed to extract avatar: {e}"
        raise AvatarProcessingError(msg) from e
    else:
        return (avatar_uuid, avatar_path)


def enrich_and_moderate_avatar(
    avatar_uuid: uuid.UUID, avatar_path: Path, docs_dir: Path, model: str = "models/gemini-flash-latest"
) -> AvatarModerationResult:
    """Enrich avatar image with AI description and moderation.

    Creates pydantic-ai agent with configured model.
    Reads auth from GOOGLE_API_KEY environment variable.

    Args:
        avatar_uuid: UUID of the avatar
        avatar_path: Path to avatar image
        docs_dir: MkDocs docs directory
        model: Model name in Google API format (default: models/gemini-flash-latest)

    Returns:
        AvatarModerationResult with moderation verdict

    Raises:
        AvatarProcessingError: If enrichment fails

    """
    logger.info("Enriching and moderating avatar: %s", avatar_uuid)
    avatar_enrichment_agent = create_avatar_enrichment_agent(model)
    try:
        binary_content = load_file_as_binary_content(avatar_path)
        relative_path = avatar_path.relative_to(docs_dir).as_posix()
        context = AvatarEnrichmentContext(media_filename=avatar_path.name, media_path=relative_path)
        message_content = ["Analyze and moderate this avatar image", binary_content]
        result = avatar_enrichment_agent.run_sync(message_content, deps=context)
        is_appropriate = result.data.is_appropriate
        reason = result.data.reason
        description = result.data.description
        status = "approved" if is_appropriate else "blocked"
        has_pii = "pii" in reason.lower() or "personal" in reason.lower()
        enrichment_text = f"# Avatar Analysis\n\n{description}\n\n**Status**: {status}\n**Reason**: {reason}"
        enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
        enrichment_path.write_text(enrichment_text, encoding="utf-8")
        logger.info("Saved enrichment to: %s", enrichment_path)
        if has_pii or status == "blocked":
            logger.warning("Avatar %s blocked (PII: %s, Status: %s)", avatar_uuid, has_pii, status)
            if has_pii and status == "approved":
                status = "blocked"
            try:
                avatar_path.unlink(missing_ok=True)
                logger.info("Deleted blocked avatar: %s", avatar_path)
            except OSError:
                logger.exception("Failed to delete avatar %s", avatar_path)
            try:
                enrichment_path.unlink(missing_ok=True)
                logger.info("Deleted enrichment file: %s", enrichment_path)
            except OSError:
                logger.exception("Failed to delete enrichment %s", enrichment_path)
        return AvatarModerationResult(
            status=status,
            reason=reason,
            has_pii=has_pii,
            avatar_uuid=str(avatar_uuid),
            avatar_path=avatar_path,
            enrichment_path=enrichment_path,
        )
    except Exception as e:
        logger.error("Avatar enrichment failed for %s: %s", avatar_uuid, e, exc_info=True)
        try:
            if avatar_path and avatar_path.exists():
                avatar_path.unlink(missing_ok=True)
                logger.info("Cleaned up avatar file after failure: %s", avatar_path)
        except OSError:
            logger.exception("Failed to clean up avatar %s", avatar_path)
        try:
            enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
            if enrichment_path.exists():
                enrichment_path.unlink(missing_ok=True)
                logger.info("Cleaned up enrichment file after failure: %s", enrichment_path)
        except (OSError, AttributeError):
            logger.exception("Failed to clean up enrichment file")
        msg = f"Failed to enrich avatar {avatar_uuid}: {e}"
        raise AvatarProcessingError(msg) from e


__all__ = [
    "AvatarModerationResult",
    "AvatarProcessingError",
    "ModerationStatus",
    "download_avatar_from_url",
    "enrich_and_moderate_avatar",
    "extract_avatar_from_zip",
]
