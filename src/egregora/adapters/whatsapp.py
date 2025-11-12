"""WhatsApp source adapter - parses WhatsApp ZIP exports into IR format.

This adapter wraps the existing WhatsApp parsing logic and exposes it through
the standard InputAdapter interface, making WhatsApp just another source in
the pipeline.

Media Handling:
- parse() converts WhatsApp media references to markdown format
- deliver_media() extracts specific files from ZIP on demand
"""

from __future__ import annotations

import logging
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, Unpack

import ibis

from egregora.pipeline.validation import create_ir_table
from egregora.sources.base import AdapterMeta, InputAdapter
from egregora.sources.whatsapp.models import WhatsAppExport
from egregora.sources.whatsapp.parser import (
    parse_source,
)  # Phase 6: Renamed from parse_export (alpha - breaking)
from egregora.sources.whatsapp.pipeline import discover_chat_file
from egregora.types import GroupSlug

if TYPE_CHECKING:
    from ibis.expr.types import Table
logger = logging.getLogger(__name__)
__all__ = ["WhatsAppAdapter"]


class _EmptyKwargs(TypedDict):
    """Empty TypedDict for unused kwargs in adapter methods."""


class DeliverMediaKwargs(TypedDict, total=False):
    """Kwargs for WhatsAppAdapter.deliver_media method."""

    zip_path: Path


ATTACHMENT_MARKERS = ("(arquivo anexado)", "(file attached)", "(archivo adjunto)", "\u200e<attached:")
WA_MEDIA_PATTERN = re.compile("\\b((?:IMG|VID|AUD|PTT|DOC)-\\d+-WA\\d+\\.\\w+)\\b")
MEDIA_EXTENSIONS = {
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".webp": "image",
    ".mp4": "video",
    ".mov": "video",
    ".3gp": "video",
    ".avi": "video",
    ".opus": "audio",
    ".ogg": "audio",
    ".mp3": "audio",
    ".m4a": "audio",
    ".aac": "audio",
    ".pdf": "document",
    ".doc": "document",
    ".docx": "document",
}


def _detect_media_type(filename: str) -> str:
    """Detect media type from filename for markdown alt text."""
    ext = Path(filename).suffix.lower()
    return MEDIA_EXTENSIONS.get(ext, "file")


def _convert_whatsapp_media_to_markdown(message: str) -> str:
    """Convert WhatsApp media references to markdown format.

    Converts:
        "IMG-20250101-WA0001.jpg (file attached)" → "![Image](IMG-20250101-WA0001.jpg)"
        "VID-20250101-WA0001.mp4 (arquivo anexado)" → "[Video](VID-20250101-WA0001.mp4)"

    Args:
        message: Original WhatsApp message text

    Returns:
        Message with media references converted to markdown

    """
    if not message:
        return message
    result = message
    media_files = WA_MEDIA_PATTERN.findall(message)
    for filename in media_files:
        media_type = _detect_media_type(filename)
        if media_type == "image":
            markdown = f"![Image]({filename})"
        elif media_type == "video":
            markdown = f"[Video]({filename})"
        elif media_type == "audio":
            markdown = f"[Audio]({filename})"
        elif media_type == "document":
            markdown = f"[Document]({filename})"
        else:
            markdown = f"[File]({filename})"
        for marker in ATTACHMENT_MARKERS:
            pattern = re.escape(filename) + "\\s*" + re.escape(marker)
            result = re.sub(pattern, markdown, result, flags=re.IGNORECASE)
        if filename in result and markdown not in result:
            result = re.sub("\\b" + re.escape(filename) + "\\b", markdown, result)
    return result


class WhatsAppAdapter(InputAdapter):
    """Source adapter for WhatsApp ZIP exports.

    This adapter handles:
    1. Discovering the chat file in the ZIP
    2. Parsing WhatsApp message format
    3. Anonymizing author names
    4. Converting to standardized IR schema

    Example:
        >>> adapter = WhatsAppAdapter()
        >>> table = adapter.parse(Path("export.zip"), timezone="UTC")
        >>> metadata = adapter.get_metadata(Path("export.zip"))
        >>> print(metadata["group_name"])

    """

    @property
    def source_name(self) -> str:
        return "WhatsApp"

    @property
    def source_identifier(self) -> str:
        return "whatsapp"

    def get_adapter_metadata(self) -> AdapterMeta:
        """Return adapter metadata for plugin discovery.

        Returns:
            AdapterMeta with WhatsApp adapter information

        """
        return AdapterMeta(
            name="WhatsApp",
            version="1.0.0",
            source="whatsapp",
            doc_url="https://github.com/franklinbaldo/egregora#whatsapp-exports",
            ir_version="v1",
        )

    def parse(self, input_path: Path, *, timezone: str | None = None, **_kwargs: _EmptyKwargs) -> Table:
        """Parse WhatsApp ZIP export into IR-compliant table.

        Converts WhatsApp media references to standard markdown format:
        - "IMG-001.jpg (file attached)" → "![Image](IMG-001.jpg)"
        - "VID-001.mp4 (arquivo anexado)" → "[Video](VID-001.mp4)"

        Args:
            input_path: Path to WhatsApp ZIP export
            timezone: Timezone for timestamp normalization (phone export timezone)
            **kwargs: Additional parameters (unused)

        Returns:
            Ibis Table conforming to IR_SCHEMA with markdown media references

        Raises:
            ValueError: If ZIP is invalid or chat file not found
            FileNotFoundError: If input_path does not exist

        """
        if not input_path.exists():
            msg = f"Input path does not exist: {input_path}"
            raise FileNotFoundError(msg)
        if not input_path.is_file() or not str(input_path).endswith(".zip"):
            msg = f"Expected a ZIP file, got: {input_path}"
            raise ValueError(msg)
        group_name, chat_file = discover_chat_file(input_path)
        export = WhatsAppExport(
            zip_path=input_path,
            group_name=group_name,
            group_slug=GroupSlug(group_name.lower().replace(" ", "-")),
            export_date=datetime.now(tz=UTC).date(),
            chat_file=chat_file,
            media_files=[],
        )
        messages_table = parse_source(export, timezone=timezone)  # Phase 6: parse_source renamed

        @ibis.udf.scalar.python
        def convert_media_to_markdown(message: str | None) -> str | None:
            if message is None:
                return None
            return _convert_whatsapp_media_to_markdown(message)

        messages_table = messages_table.mutate(message=convert_media_to_markdown(messages_table.message))
        ir_table = create_ir_table(messages_table, timezone=timezone)
        logger.debug("Parsed WhatsApp export with %s messages", ir_table.count().execute())
        return ir_table

    def deliver_media(
        self, media_reference: str, temp_dir: Path, **kwargs: Unpack[DeliverMediaKwargs]
    ) -> Path | None:
        """Deliver media file from WhatsApp ZIP to temporary directory.

        Extracts the requested media file from the ZIP and writes it to temp_dir.
        The file is extracted with its original name for the runner to process.

        Args:
            media_reference: Media filename from markdown link (e.g., "IMG-20250101-WA0001.jpg")
            temp_dir: Temporary directory where file should be written
            **kwargs: Must include 'zip_path' (Path to WhatsApp ZIP export)

        Returns:
            Path to the delivered file in temp_dir, or None if not found

        Example:
            >>> adapter = WhatsAppAdapter()
            >>> # Message contains: ![Image](IMG-20250101-WA0001.jpg)
            >>> temp_file = adapter.deliver_media(
            ...     "IMG-20250101-WA0001.jpg",
            ...     Path("/tmp"),
            ...     zip_path=Path("export.zip")
            ... )
            >>> # Returns: Path("/tmp/IMG-20250101-WA0001.jpg")

        """
        # Validation guards
        if not self._validate_media_reference(media_reference):
            return None
        zip_path = self._get_validated_zip_path(kwargs)
        if not zip_path:
            return None

        # Extract and deliver media
        return self._extract_media_from_zip(zip_path, media_reference, temp_dir)

    def _validate_media_reference(self, media_reference: str) -> bool:
        """Validate media reference for path traversal attempts."""
        if ".." in media_reference or "/" in media_reference or "\\" in media_reference:
            logger.warning("Suspicious media reference (path traversal attempt): %s", media_reference)
            return False
        return True

    def _get_validated_zip_path(self, kwargs: DeliverMediaKwargs) -> Path | None:
        """Extract and validate zip_path from kwargs."""
        zip_path = kwargs.get("zip_path")
        if not zip_path:
            logger.warning("deliver_media() called without zip_path kwarg")
            return None
        if not isinstance(zip_path, Path):
            zip_path = Path(zip_path)
        if not zip_path.exists():
            logger.warning("ZIP file does not exist: %s", zip_path)
            return None
        return zip_path

    def _extract_media_from_zip(self, zip_path: Path, media_reference: str, temp_dir: Path) -> Path | None:
        """Extract media file from ZIP archive."""
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                found_path = self._find_media_in_zip(zf, media_reference)
                if not found_path:
                    logger.debug("Media file not found in ZIP: %s", media_reference)
                    return None

                file_content = zf.read(found_path)
                output_file = temp_dir / media_reference
                output_file.write_bytes(file_content)
                logger.debug("Delivered media: %s → %s", media_reference, output_file)
                return output_file
        except zipfile.BadZipFile:
            logger.exception("Invalid ZIP file: %s", zip_path)
            return None
        except (KeyError, OSError, PermissionError):
            logger.exception("Failed to extract %s from %s", media_reference, zip_path)
            return None

    def _find_media_in_zip(self, zf: zipfile.ZipFile, media_reference: str) -> str | None:
        """Find media file in ZIP archive by case-insensitive name match."""
        for info in zf.infolist():
            if info.is_dir():
                continue
            if Path(info.filename).name.lower() == media_reference.lower():
                return info.filename
        return None

    def get_metadata(self, input_path: Path, **_kwargs: _EmptyKwargs) -> dict[str, Any]:
        """Extract metadata from WhatsApp export.

        Args:
            input_path: Path to WhatsApp ZIP export
            **kwargs: Additional parameters

        Returns:
            Dictionary with:
                - group_name: Discovered group name
                - group_slug: URL-safe group identifier
                - chat_file: Name of chat file in ZIP
                - export_date: Current date

        """
        if not input_path.exists():
            msg = f"Input path does not exist: {input_path}"
            raise FileNotFoundError(msg)
        group_name, chat_file = discover_chat_file(input_path)
        group_slug = GroupSlug(group_name.lower().replace(" ", "-"))
        return {
            "group_name": group_name,
            "group_slug": str(group_slug),
            "chat_file": chat_file,
            "export_date": datetime.now(tz=UTC).date().isoformat(),
        }
