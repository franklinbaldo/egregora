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

# Avatar moderation status
ModerationStatus = Literal["approved", "questionable", "blocked"]

# Supported image formats
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Allowed MIME types for avatars (strict whitelist)
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# Max avatar file size (10MB)
MAX_AVATAR_SIZE_BYTES = 10 * 1024 * 1024

# Max image dimensions (width or height)
MAX_IMAGE_DIMENSION = 4096

# Default timeout for avatar downloads (seconds)
DEFAULT_DOWNLOAD_TIMEOUT = 30.0

# Maximum number of HTTP redirects to follow
MAX_REDIRECT_HOPS = 10

# Chunk size for streaming downloads (bytes)
DOWNLOAD_CHUNK_SIZE = 8192

# Magic bytes for image validation
MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",  # WEBP starts with RIFF (followed by WEBP)
}

# Private IP ranges to block (SSRF prevention)
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),  # Private network
    ipaddress.ip_network("172.16.0.0/12"),  # Private network
    ipaddress.ip_network("192.168.0.0/16"),  # Private network
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
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
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        msg = f"Invalid URL: {e}"
        raise AvatarProcessingError(msg) from e

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        msg = f"Invalid URL scheme: {parsed.scheme}. Only HTTP and HTTPS are allowed."
        raise AvatarProcessingError(msg)

    # Get hostname
    hostname = parsed.hostname
    if not hostname:
        msg = "URL must have a hostname"
        raise AvatarProcessingError(msg)

    # Resolve hostname to IP addresses
    try:
        # Get all IP addresses for the hostname
        addr_info = socket.getaddrinfo(hostname, None)
        ip_addresses = {info[4][0] for info in addr_info}
    except socket.gaierror as e:
        msg = f"Could not resolve hostname '{hostname}': {e}"
        raise AvatarProcessingError(msg) from e

    # Check each resolved IP against blocked ranges
    for ip_str in ip_addresses:
        try:
            ip_addr = ipaddress.ip_address(ip_str)

            # Check for IPv4-mapped IPv6 addresses (e.g., ::ffff:127.0.0.1)
            # These can bypass IPv4 range checks, so we need to extract the IPv4 address
            if ip_addr.version == 6 and ip_addr.ipv4_mapped:
                # Extract the IPv4 address from the mapped IPv6 address
                ipv4_addr = ip_addr.ipv4_mapped
                logger.debug(f"Detected IPv4-mapped address: {ip_addr} -> {ipv4_addr}")

                # Check the extracted IPv4 address against blocked ranges
                for blocked_range in BLOCKED_IP_RANGES:
                    if blocked_range.version == 4 and ipv4_addr in blocked_range:
                        # Log security event at WARNING level for monitoring
                        logger.warning(
                            f"⚠️  SSRF attempt blocked (IPv4-mapped): {url} resolves to {ip_str} "
                            f"(maps to {ipv4_addr} in blocked range {blocked_range})"
                        )
                        msg = (
                            f"URL resolves to blocked IPv4-mapped address: {ip_str} "
                            f"(maps to {ipv4_addr} in range {blocked_range}). "
                            "Access to private/internal networks is not allowed."
                        )
                        raise AvatarProcessingError(msg)

            # Check against blocked ranges
            for blocked_range in BLOCKED_IP_RANGES:
                if ip_addr in blocked_range:
                    # Log security event at WARNING level for monitoring
                    logger.warning(
                        f"⚠️  SSRF attempt blocked: {url} resolves to {ip_str} in blocked range {blocked_range}"
                    )
                    msg = (
                        f"URL resolves to blocked IP address: {ip_str} "
                        f"(in range {blocked_range}). "
                        "Access to private/internal networks is not allowed."
                    )
                    raise AvatarProcessingError(msg)

        except ValueError as e:
            msg = f"Invalid IP address '{ip_str}': {e}"
            raise AvatarProcessingError(msg) from e

    logger.info(f"URL validation passed for: {url} (resolves to: {', '.join(ip_addresses)})")


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
    # Check magic bytes
    for magic, mime_type in MAGIC_BYTES.items():
        if content.startswith(magic):
            # Special handling for WEBP (RIFF can be other formats too)
            if magic == b"RIFF" and len(content) >= 12:
                if content[8:12] == b"WEBP":
                    if expected_mime != "image/webp":
                        msg = f"Image content is WEBP but declared as {expected_mime}"
                        raise AvatarProcessingError(msg)
                    return
                msg = f"RIFF file is not WEBP format (expected {expected_mime})"
                raise AvatarProcessingError(msg)

            # Normal validation for other formats
            if mime_type != expected_mime:
                msg = (
                    f"Image content type mismatch: content appears to be {mime_type} "
                    f"but declared as {expected_mime}"
                )
                raise AvatarProcessingError(msg)
            return

    # No magic bytes matched
    msg = "Unable to verify image format. Content does not match any supported image type."
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

        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            msg = (
                f"Image dimensions too large: {width}x{height} pixels. "
                f"Maximum allowed: {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION} pixels."
            )
            raise AvatarProcessingError(msg)

        logger.debug(f"Image dimensions validated: {width}x{height} pixels")

    except AvatarProcessingError:
        raise
    except Exception as e:
        msg = f"Failed to validate image dimensions: {e}"
        raise AvatarProcessingError(msg) from e


def download_avatar_from_url(
    url: str,
    docs_dir: Path,
    group_slug: str,
    timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
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
    logger.info(f"Downloading avatar from URL: {url}")

    # Validate URL to prevent SSRF attacks
    _validate_url_for_ssrf(url)

    try:
        # Disable automatic redirects and validate each redirect hop manually
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            current_url = url
            redirect_count = 0

            while redirect_count < MAX_REDIRECT_HOPS:
                # Use streaming to prevent buffering entire response in memory
                with client.stream("GET", current_url) as response:
                    # If we got a redirect, validate the new URL before following it
                    if response.status_code in (301, 302, 303, 307, 308):
                        redirect_count += 1
                        location = response.headers.get("location")
                        if not location:
                            msg = "Redirect response missing Location header"
                            raise AvatarProcessingError(msg)

                        # Resolve relative redirects
                        next_url = urljoin(current_url, location)
                        logger.info(f"Following redirect {redirect_count}/{MAX_REDIRECT_HOPS}: {next_url}")

                        # Validate the redirect destination before following it
                        _validate_url_for_ssrf(next_url)

                        current_url = next_url
                        continue

                    # Not a redirect, process the response
                    response.raise_for_status()

                    # Check content type against strict whitelist
                    content_type = response.headers.get("content-type", "").lower().split(";")[0].strip()
                    if content_type not in ALLOWED_MIME_TYPES:
                        msg = (
                            f"Invalid image MIME type: {content_type}. "
                            f"Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
                        )
                        raise AvatarProcessingError(msg)

                    # Check Content-Length header before downloading (early size validation)
                    content_length_str = response.headers.get("content-length")
                    if content_length_str:
                        try:
                            content_length = int(content_length_str)
                            if content_length > MAX_AVATAR_SIZE_BYTES:
                                msg = (
                                    f"Avatar image too large: {content_length} bytes "
                                    f"(max: {MAX_AVATAR_SIZE_BYTES} bytes)"
                                )
                                raise AvatarProcessingError(msg)
                        except ValueError:
                            logger.warning(f"Invalid Content-Length header: {content_length_str}")

                    # Stream download with size limit enforcement
                    # This prevents buffering the entire response before size check
                    content = bytearray()
                    for chunk in response.iter_bytes(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        content.extend(chunk)
                        if len(content) > MAX_AVATAR_SIZE_BYTES:
                            msg = f"Avatar image too large: exceeded {MAX_AVATAR_SIZE_BYTES} bytes during download"
                            raise AvatarProcessingError(msg)

                    content = bytes(content)
                    break
            else:
                # Hit max redirects
                msg = f"Too many redirects (>{MAX_REDIRECT_HOPS})"
                raise AvatarProcessingError(msg)

            # Validate content matches declared MIME type (magic bytes check)
            _validate_image_content(content, content_type)

            # Validate image dimensions to prevent memory exhaustion
            _validate_image_dimensions(content)

            # Infer extension from content-type or URL
            if content_type.startswith("image/jpeg"):
                ext = ".jpg"
            elif content_type.startswith("image/png"):
                ext = ".png"
            elif content_type.startswith("image/gif"):
                ext = ".gif"
            elif content_type.startswith("image/webp"):
                ext = ".webp"
            else:
                # Try to infer from URL or default to jpg
                ext = _validate_image_format(url or ".jpg")

            # Generate UUID and determine file path
            avatar_uuid = _generate_avatar_uuid(content, group_slug)
            avatar_dir = _get_avatar_directory(docs_dir)
            avatar_path = avatar_dir / f"{avatar_uuid}{ext}"

            # Deduplication: Check if avatar already exists
            if avatar_path.exists():
                logger.info(f"Avatar already exists (deduplication): {avatar_path}")
                return avatar_uuid, avatar_path

            # Save using exclusive creation mode to prevent race conditions
            try:
                with avatar_path.open("xb") as f:
                    f.write(content)
                logger.info(f"Saved avatar to: {avatar_path}")
            except FileExistsError:
                # Another process/thread created it between our check and write
                logger.info(f"Avatar created concurrently: {avatar_path}")

            return avatar_uuid, avatar_path

    except httpx.HTTPError as e:
        logger.debug(f"HTTP error details: {e}")  # Full error in logs only
        msg = "Failed to download avatar. Please check the URL and try again."
        raise AvatarProcessingError(msg) from e
    except OSError as e:
        logger.debug(f"File system error details: {e}")  # Full error in logs only
        msg = "Failed to save avatar due to file system error."
        raise AvatarProcessingError(msg) from e


def extract_avatar_from_zip(
    zip_path: Path,
    media_filename: str,
    docs_dir: Path,
    group_slug: str,
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
    logger.info(f"Extracting avatar from ZIP: {media_filename}")

    try:
        # Validate extension
        ext = _validate_image_format(media_filename)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Find file in ZIP
            found = False
            for info in zf.infolist():
                if info.is_dir():
                    continue

                # Validate that the filename doesn't contain path traversal sequences
                if ".." in info.filename or info.filename.startswith("/"):
                    logger.warning(f"Skipping suspicious ZIP entry with path traversal: {info.filename}")
                    continue

                filename = Path(info.filename).name
                if filename == media_filename:
                    found = True

                    # Check size
                    if info.file_size > MAX_AVATAR_SIZE_BYTES:
                        msg = (
                            f"Avatar image too large: {info.file_size} bytes "
                            f"(max: {MAX_AVATAR_SIZE_BYTES} bytes)"
                        )
                        raise AvatarProcessingError(msg)

                    # Read content
                    content = zf.read(info)

                    # Infer MIME type from extension for validation
                    if ext in (".jpg", ".jpeg"):
                        mime_type = "image/jpeg"
                    elif ext == ".png":
                        mime_type = "image/png"
                    elif ext == ".gif":
                        mime_type = "image/gif"
                    elif ext == ".webp":
                        mime_type = "image/webp"
                    else:
                        msg = f"Unsupported extension: {ext}"
                        raise AvatarProcessingError(msg)

                    # Validate content matches extension (magic bytes check)
                    _validate_image_content(content, mime_type)

                    # Validate image dimensions to prevent memory exhaustion
                    _validate_image_dimensions(content)

                    # Generate UUID and save
                    avatar_uuid = _generate_avatar_uuid(content, group_slug)
                    avatar_dir = _get_avatar_directory(docs_dir)
                    avatar_path = avatar_dir / f"{avatar_uuid}{ext}"

                    # Save using exclusive creation mode to prevent race conditions
                    try:
                        with avatar_path.open("xb") as f:
                            f.write(content)
                        logger.info(f"Saved avatar to: {avatar_path}")
                    except FileExistsError:
                        logger.info(f"Avatar already exists: {avatar_path}")

                    return avatar_uuid, avatar_path

            if not found:
                msg = f"Media file not found in ZIP: {media_filename}"
                raise AvatarProcessingError(msg)

    except zipfile.BadZipFile as e:
        msg = f"Invalid ZIP file: {e}"
        raise AvatarProcessingError(msg) from e
    except OSError as e:
        msg = f"Failed to extract avatar: {e}"
        raise AvatarProcessingError(msg) from e

    # Should not reach here
    msg = f"Failed to extract avatar: {media_filename}"
    raise AvatarProcessingError(msg)


def enrich_and_moderate_avatar(
    avatar_uuid: uuid.UUID,
    avatar_path: Path,
    docs_dir: Path,
    model: str = "models/gemini-flash-latest",
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
    logger.info(f"Enriching and moderating avatar: {avatar_uuid}")

    # Create agent with configured model (already in pydantic-ai format)
    avatar_enrichment_agent = create_avatar_enrichment_agent(model)

    try:
        # Load image as binary content (no upload needed!)
        binary_content = load_file_as_binary_content(avatar_path)

        # Get relative path for enrichment context
        relative_path = avatar_path.relative_to(docs_dir).as_posix()

        # Create enrichment context
        context = AvatarEnrichmentContext(
            media_filename=avatar_path.name,
            media_path=relative_path,
        )

        # Use module-level avatar enrichment agent
        # Build multimodal message content
        message_content = [
            "Analyze and moderate this avatar image",
            binary_content,
        ]

        result = avatar_enrichment_agent.run_sync(message_content, deps=context)

        # Extract structured output
        is_appropriate = result.data.is_appropriate
        reason = result.data.reason
        description = result.data.description

        # Determine status and has_pii from agent output
        status = "approved" if is_appropriate else "blocked"
        has_pii = "pii" in reason.lower() or "personal" in reason.lower()

        # Save enrichment markdown
        enrichment_text = f"# Avatar Analysis\n\n{description}\n\n**Status**: {status}\n**Reason**: {reason}"
        enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
        enrichment_path.write_text(enrichment_text, encoding="utf-8")
        logger.info(f"Saved enrichment to: {enrichment_path}")

        # If PII detected or blocked, delete both files
        if has_pii or status == "blocked":
            logger.warning(f"Avatar {avatar_uuid} blocked (PII: {has_pii}, Status: {status})")

            if has_pii and status == "approved":
                status = "blocked"

            # Delete files
            try:
                avatar_path.unlink(missing_ok=True)
                logger.info(f"Deleted blocked avatar: {avatar_path}")
            except OSError as e:
                logger.exception(f"Failed to delete avatar {avatar_path}: {e}")

            try:
                enrichment_path.unlink(missing_ok=True)
                logger.info(f"Deleted enrichment file: {enrichment_path}")
            except OSError as e:
                logger.exception(f"Failed to delete enrichment {enrichment_path}: {e}")

        return AvatarModerationResult(
            status=status,
            reason=reason,
            has_pii=has_pii,
            avatar_uuid=str(avatar_uuid),
            avatar_path=avatar_path,
            enrichment_path=enrichment_path,
        )

    except Exception as e:
        logger.error(f"Avatar enrichment failed for {avatar_uuid}: {e}", exc_info=True)

        # Clean up avatar file on failure
        try:
            if avatar_path and avatar_path.exists():
                avatar_path.unlink(missing_ok=True)
                logger.info(f"Cleaned up avatar file after failure: {avatar_path}")
        except OSError as cleanup_error:
            logger.exception(f"Failed to clean up avatar {avatar_path}: {cleanup_error}")

        # Clean up enrichment file if it was created
        try:
            enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
            if enrichment_path.exists():
                enrichment_path.unlink(missing_ok=True)
                logger.info(f"Cleaned up enrichment file after failure: {enrichment_path}")
        except (OSError, AttributeError) as cleanup_error:
            logger.exception(f"Failed to clean up enrichment file: {cleanup_error}")

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
