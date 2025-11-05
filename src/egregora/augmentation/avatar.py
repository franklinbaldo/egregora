"""Avatar processing with moderation for user profiles."""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

from ..config import MEDIA_DIR_NAME
from ..prompt_templates import AvatarEnrichmentPromptTemplate
from ..utils.gemini_dispatcher import GeminiDispatcher

logger = logging.getLogger(__name__)

# Avatar moderation status
ModerationStatus = Literal["approved", "questionable", "blocked"]

# Supported image formats
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Max avatar file size (10MB)
MAX_AVATAR_SIZE_BYTES = 10 * 1024 * 1024


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

    pass


def _get_avatar_directory(docs_dir: Path) -> Path:
    """Get or create the avatars directory."""
    avatar_dir = docs_dir / MEDIA_DIR_NAME / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    return avatar_dir


def _generate_avatar_uuid(content: bytes, group_slug: str) -> uuid.UUID:
    """Generate deterministic UUID for avatar based on content."""
    namespace = uuid.uuid5(uuid.NAMESPACE_DNS, group_slug)
    content_hash = hashlib.sha256(content).hexdigest()
    return uuid.uuid5(namespace, content_hash)


def _validate_image_format(filename: str) -> str:
    """
    Validate image format.

    Returns the file extension if valid.
    Raises AvatarProcessingError if invalid.
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        raise AvatarProcessingError(
            f"Unsupported image format: {ext}. "
            f"Supported formats: {', '.join(SUPPORTED_IMAGE_EXTENSIONS)}"
        )
    return ext


def download_avatar_from_url(
    url: str,
    docs_dir: Path,
    group_slug: str,
    timeout: float = 30.0,
) -> tuple[uuid.UUID, Path]:
    """
    Download avatar from URL and save to avatars directory.

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

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

            # Check content type
            content_type = response.headers.get("content-type", "").lower()
            if not content_type.startswith("image/"):
                raise AvatarProcessingError(
                    f"URL does not point to an image (content-type: {content_type})"
                )

            # Check size
            content = response.content
            if len(content) > MAX_AVATAR_SIZE_BYTES:
                raise AvatarProcessingError(
                    f"Avatar image too large: {len(content)} bytes "
                    f"(max: {MAX_AVATAR_SIZE_BYTES} bytes)"
                )

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

            # Generate UUID and save
            avatar_uuid = _generate_avatar_uuid(content, group_slug)
            avatar_dir = _get_avatar_directory(docs_dir)
            avatar_path = avatar_dir / f"{avatar_uuid}{ext}"

            # Save if not already exists
            if not avatar_path.exists():
                avatar_path.write_bytes(content)
                logger.info(f"Saved avatar to: {avatar_path}")
            else:
                logger.info(f"Avatar already exists: {avatar_path}")

            return avatar_uuid, avatar_path

    except httpx.HTTPError as e:
        raise AvatarProcessingError(f"Failed to download avatar from URL: {e}") from e
    except OSError as e:
        raise AvatarProcessingError(f"Failed to save avatar: {e}") from e


def extract_avatar_from_zip(
    zip_path: Path,
    media_filename: str,
    docs_dir: Path,
    group_slug: str,
) -> tuple[uuid.UUID, Path]:
    """
    Extract avatar image from WhatsApp ZIP export.

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

                filename = Path(info.filename).name
                if filename == media_filename:
                    found = True

                    # Check size
                    if info.file_size > MAX_AVATAR_SIZE_BYTES:
                        raise AvatarProcessingError(
                            f"Avatar image too large: {info.file_size} bytes "
                            f"(max: {MAX_AVATAR_SIZE_BYTES} bytes)"
                        )

                    # Read content
                    content = zf.read(info)

                    # Generate UUID and save
                    avatar_uuid = _generate_avatar_uuid(content, group_slug)
                    avatar_dir = _get_avatar_directory(docs_dir)
                    avatar_path = avatar_dir / f"{avatar_uuid}{ext}"

                    # Save if not already exists
                    if not avatar_path.exists():
                        avatar_path.write_bytes(content)
                        logger.info(f"Saved avatar to: {avatar_path}")
                    else:
                        logger.info(f"Avatar already exists: {avatar_path}")

                    return avatar_uuid, avatar_path

            if not found:
                raise AvatarProcessingError(f"Media file not found in ZIP: {media_filename}")

    except zipfile.BadZipFile as e:
        raise AvatarProcessingError(f"Invalid ZIP file: {e}") from e
    except OSError as e:
        raise AvatarProcessingError(f"Failed to extract avatar: {e}") from e

    # Should not reach here
    raise AvatarProcessingError(f"Failed to extract avatar: {media_filename}")


def _parse_moderation_result(enrichment_text: str) -> tuple[ModerationStatus, str, bool]:
    """
    Parse moderation result from enrichment text.

    Returns:
        Tuple of (status, reason, has_pii)
    """
    # Check for moderation status on first line
    first_line = enrichment_text.split("\n", 1)[0].strip()
    status_match = re.match(r"MODERATION_STATUS:\s*(APPROVED|QUESTIONABLE|BLOCKED)", first_line)

    if not status_match:
        logger.warning("No moderation status found in enrichment, defaulting to QUESTIONABLE")
        return "questionable", "No moderation status found in enrichment", False

    status = status_match.group(1).lower()

    # Check for PII detection
    has_pii = "PII_DETECTED" in enrichment_text[:500]  # Check first 500 chars

    # Extract reason from markdown
    reason = "No reason provided"
    reason_match = re.search(r"\*\*Reason:\*\*\s*(.+?)(?:\n|$)", enrichment_text)
    if reason_match:
        reason = reason_match.group(1).strip()

    return status, reason, has_pii  # type: ignore


def enrich_and_moderate_avatar(
    avatar_uuid: uuid.UUID,
    avatar_path: Path,
    docs_dir: Path,
    vision_client: GeminiDispatcher,
    model: str = "gemini-2.0-flash-exp",
) -> AvatarModerationResult:
    """
    Enrich avatar image with AI description and moderation.

    Args:
        avatar_uuid: UUID of the avatar
        avatar_path: Path to avatar image
        docs_dir: MkDocs docs directory
        vision_client: Gemini vision client
        model: Model name for vision processing

    Returns:
        AvatarModerationResult with moderation verdict

    Raises:
        AvatarProcessingError: If enrichment fails
    """
    logger.info(f"Enriching and moderating avatar: {avatar_uuid}")

    try:
        # Upload image to Gemini
        uploaded_file = vision_client.client.files.upload(
            path=str(avatar_path),
        )

        # Generate enrichment prompt
        relative_path = avatar_path.relative_to(docs_dir).as_posix()
        prompt_template = AvatarEnrichmentPromptTemplate(
            media_filename=avatar_path.name,
            media_path=relative_path,
        )
        prompt = prompt_template.render()

        # Call vision model with retry
        response = vision_client.generate_content_with_retry(
            prompt=prompt,
            files=[uploaded_file],
            model=model,
        )

        enrichment_text = response.text

        # Parse moderation result
        status, reason, has_pii = _parse_moderation_result(enrichment_text)

        # Save enrichment markdown
        enrichment_path = avatar_path.with_suffix(avatar_path.suffix + ".md")
        enrichment_path.write_text(enrichment_text, encoding="utf-8")
        logger.info(f"Saved enrichment to: {enrichment_path}")

        # If PII detected or blocked, delete the avatar file
        if has_pii or status == "blocked":
            logger.warning(f"Avatar {avatar_uuid} blocked (PII: {has_pii}, Status: {status})")
            if avatar_path.exists():
                avatar_path.unlink()
                logger.info(f"Deleted blocked avatar: {avatar_path}")

        return AvatarModerationResult(
            status=status,
            reason=reason,
            has_pii=has_pii,
            avatar_uuid=str(avatar_uuid),
            avatar_path=avatar_path,
            enrichment_path=enrichment_path,
        )

    except Exception as e:
        raise AvatarProcessingError(f"Failed to enrich avatar: {e}") from e


__all__ = [
    "AvatarModerationResult",
    "AvatarProcessingError",
    "ModerationStatus",
    "download_avatar_from_url",
    "extract_avatar_from_zip",
    "enrich_and_moderate_avatar",
]
