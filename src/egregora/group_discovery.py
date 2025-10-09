"""Auto-discovery of WhatsApp groups from validated WhatsApp ZIP files."""

from __future__ import annotations

import logging
import re
import unicodedata
import zipfile
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

from .date_utils import parse_flexible_date
from .models import WhatsAppExport
from .types import GroupSlug
from .zip_utils import ZipValidationError, ensure_safe_member_size, validate_zip_contents

logger = logging.getLogger(__name__)


def discover_groups(zips_dir: Path) -> dict[GroupSlug, list[WhatsAppExport]]:
    """
    Scan ZIP files and return discovered groups.

    Returns:
        {slug: [exports]} ordered by date
    """

    groups: defaultdict[GroupSlug, list[WhatsAppExport]] = defaultdict(list)

    for zip_path in sorted(zips_dir.rglob("*.zip")):
        if zip_path.is_symlink():
            logger.warning("Skipping %s: refusing to follow symlink", zip_path.name)
            continue
        if not zip_path.is_file():
            logger.debug("Skipping %s: not a regular file", zip_path)
            continue
        try:
            export = _extract_metadata(zip_path)
        except (ValueError, ZipValidationError) as exc:
            logger.warning("Skipping %s: %s", zip_path.name, exc)
            continue
        except zipfile.BadZipFile:
            logger.warning("Skipping %s: invalid ZIP archive", zip_path.name)
            continue

        groups[export.group_slug].append(export)
        logger.debug("Discovered export for %s (%s)", export.group_name, export.group_slug)

    # Sort exports by date
    for slug in groups:
        groups[slug].sort(key=lambda e: e.export_date)

    return dict(groups)


def _extract_metadata(zip_path: Path) -> WhatsAppExport:
    """Extract metadata from a ZIP file."""

    with zipfile.ZipFile(zip_path) as zf:
        validate_zip_contents(zf)

        txt_files = _safe_text_members(zf.namelist())
        if not txt_files:
            raise ValueError("No chat file found")

        chat_file = txt_files[0]

        # Extract group name
        group_name = _extract_group_name(chat_file)
        group_slug = _slugify(group_name)

        # Extract date
        export_date = _extract_date(zip_path, zf, chat_file)

        media_files = [f for f in zf.namelist() if f != chat_file and not f.startswith("__MACOSX")]

        return WhatsAppExport(
            zip_path=zip_path,
            group_name=group_name,
            group_slug=group_slug,
            export_date=export_date,
            chat_file=chat_file,
            media_files=media_files,
        )


def _extract_group_name(filename: str) -> str:
    """
    Extract group name from internal .txt file.
    Supports PT, EN, ES.
    """

    patterns = [
        r"Conversa do WhatsApp com (.+?)\.txt",  # PT
        r"WhatsApp Chat with (.+?)\.txt",  # EN
        r"Chat de WhatsApp con (.+?)\.txt",  # ES
        r"Conversación de WhatsApp con (.+?)\.txt",  # ES alt
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Fallback
    return filename.replace(".txt", "").strip()


def _slugify(text: str) -> GroupSlug:
    """Convert to filesystem-safe slug."""

    # Remove accents
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Lowercase, remove special chars, replace spaces
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)

    return GroupSlug(text.strip("-"))


def _extract_date(zip_path: Path, zf: zipfile.ZipFile, chat_file: str) -> date:
    """Extract date from export (ZIP name > content > mtime)."""

    match = re.search(r"(\d{4}-\d{2}-\d{2})", zip_path.name)
    if match:
        detected_date = date.fromisoformat(match.group(1))
        logger.debug("ZIP '%s': Date extracted from filename (%s)", zip_path.name, detected_date)
        return detected_date

    try:
        ensure_safe_member_size(zf, chat_file)
    except ZipValidationError:
        logger.debug("Skipping content-based date extraction for %s", chat_file)
    else:
        try:
            with zf.open(chat_file) as raw:
                for line in _iter_preview_lines(raw, limit=20):
                    match = re.search(r"(\d{1,2}/\d{1,2}/(?:\d{4}|\d{2}))", line)
                    if not match:
                        continue

                    parsed_date = parse_flexible_date(match.group(1))
                    if parsed_date:
                        logger.debug(
                            "ZIP '%s': Date extracted from content (%s)", zip_path.name, parsed_date
                        )
                        return parsed_date
        except (UnicodeDecodeError, ZipValidationError) as exc:
            logger.debug("Failed to parse date from %s: %s", chat_file, exc)

    timestamp = zip_path.stat().st_mtime
    fallback_date = datetime.fromtimestamp(timestamp).date()

    logger.warning(
        "ZIP '%s': Date extracted from file mtime (%s). "
        "Consider renaming to '%s-%s' for explicit control.",
        zip_path.name,
        fallback_date,
        fallback_date,
        zip_path.name,
    )

    return fallback_date


def _safe_text_members(members: Iterable[str]) -> list[str]:
    return [m for m in members if m.endswith(".txt") and not m.startswith("__MACOSX")]


def _iter_preview_lines(raw_file, *, limit: int) -> Iterable[str]:
    max_line_bytes = 16_384
    for _ in range(limit):
        chunk = raw_file.readline(max_line_bytes + 1)
        if not chunk:
            break
        if len(chunk) > max_line_bytes:
            raise ZipValidationError("Line length exceeds safety threshold")
        yield chunk.decode("utf-8")
