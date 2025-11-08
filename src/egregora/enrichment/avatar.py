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
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image

from egregora.config import MEDIA_DIR_NAME

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


def _get_avatar_directory(docs_dir: Path) -> Path:
    """Get or create the images directory for avatars.

    Simplified: avatars are just regular images, saved to media/images/ like all other images.
    """
    avatar_dir = docs_dir / MEDIA_DIR_NAME / "images"
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
    url: str, docs_dir: Path, timeout: float = DEFAULT_DOWNLOAD_TIMEOUT
) -> tuple[uuid.UUID, Path]:
    """Download avatar from URL and save to avatars directory.

    Args:
        url: URL of the avatar image
        docs_dir: MkDocs docs directory
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


__all__ = [
    "AvatarProcessingError",
    "download_avatar_from_url",
]
