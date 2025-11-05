"""WhatsApp source adapter - parses WhatsApp ZIP exports into IR format.

This adapter wraps the existing WhatsApp parsing logic and exposes it through
the standard SourceAdapter interface, making WhatsApp just another source in
the pipeline.

Media Handling:
- parse() converts WhatsApp media references to markdown format
- deliver_media() extracts specific files from ZIP on demand
"""

from __future__ import annotations

import logging
import re
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import ibis
from ibis.expr.types import Table

from egregora.ingestion.parser import parse_export
from egregora.pipeline.adapters import MediaMapping, SourceAdapter
from egregora.pipeline.ir import create_ir_table
from egregora.sources.whatsapp.models import WhatsAppExport
from egregora.sources.whatsapp.pipeline import discover_chat_file
from egregora.types import GroupSlug

logger = logging.getLogger(__name__)

__all__ = ["WhatsAppAdapter"]

# WhatsApp attachment markers (in various languages)
ATTACHMENT_MARKERS = (
    "(arquivo anexado)",  # Portuguese
    "(file attached)",  # English
    "(archivo adjunto)",  # Spanish
    "\u200e<attached:",  # Unicode left-to-right mark + <attached:
)

# Pattern for WhatsApp media references
# Matches: "IMG-20250101-WA0001.jpg (file attached)" or bare "IMG-20250101-WA0001.jpg"
WA_MEDIA_PATTERN = re.compile(
    r"\b((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b"
)

# Media type detection by extension (for markdown alt text)
MEDIA_EXTENSIONS = {
    # Images
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".webp": "image",
    # Videos
    ".mp4": "video",
    ".mov": "video",
    ".3gp": "video",
    ".avi": "video",
    # Audio
    ".opus": "audio",
    ".ogg": "audio",
    ".mp3": "audio",
    ".m4a": "audio",
    ".aac": "audio",
    # Documents
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

    # Find all WhatsApp media filenames
    media_files = WA_MEDIA_PATTERN.findall(message)

    for filename in media_files:
        media_type = _detect_media_type(filename)

        # Generate markdown based on media type
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

        # Replace filename with attachment marker
        for marker in ATTACHMENT_MARKERS:
            pattern = re.escape(filename) + r"\s*" + re.escape(marker)
            result = re.sub(pattern, markdown, result, flags=re.IGNORECASE)

        # Also replace bare filename (if not already replaced)
        if filename in result and markdown not in result:
            result = re.sub(r"\b" + re.escape(filename) + r"\b", markdown, result)

    return result


class WhatsAppAdapter(SourceAdapter):
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

    def parse(
        self,
        input_path: Path,
        *,
        timezone: str | None = None,
        **kwargs: Any,
    ) -> Table:
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
            raise FileNotFoundError(f"Input path does not exist: {input_path}")

        if not input_path.is_file() or not str(input_path).endswith(".zip"):
            raise ValueError(f"Expected a ZIP file, got: {input_path}")

        # Discover chat file in ZIP
        group_name, chat_file = discover_chat_file(input_path)

        # Create WhatsAppExport metadata object
        export = WhatsAppExport(
            zip_path=input_path,
            group_name=group_name,
            group_slug=GroupSlug(group_name.lower().replace(" ", "-")),
            export_date=datetime.now().date(),
            chat_file=chat_file,
            media_files=[],
        )

        # Parse the export (this handles anonymization internally)
        messages_table = parse_export(export, timezone=timezone)

        # Convert WhatsApp media references to markdown format
        @ibis.udf.scalar.python
        def convert_media_to_markdown(message: str | None) -> str | None:
            if message is None:
                return None
            return _convert_whatsapp_media_to_markdown(message)

        messages_table = messages_table.mutate(
            message=convert_media_to_markdown(messages_table.message)
        )

        # Ensure IR schema compliance
        ir_table = create_ir_table(messages_table, timezone=timezone)

        logger.debug(f"Parsed WhatsApp export with {ir_table.count().execute()} messages")
        return ir_table

    def deliver_media(
        self,
        media_reference: str,
        temp_dir: Path,
        **kwargs: Any,
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
        # Get ZIP path from kwargs
        zip_path = kwargs.get("zip_path")
        if not zip_path:
            logger.warning("deliver_media() called without zip_path kwarg")
            return None

        if not isinstance(zip_path, Path):
            zip_path = Path(zip_path)

        if not zip_path.exists():
            logger.warning(f"ZIP file does not exist: {zip_path}")
            return None

        # Extract file from ZIP
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Search for the file in ZIP (WhatsApp may nest in subdirectories)
                found_path = None
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    # Check if filename matches (case-insensitive)
                    if Path(info.filename).name.lower() == media_reference.lower():
                        found_path = info.filename
                        break

                if not found_path:
                    logger.debug(f"Media file not found in ZIP: {media_reference}")
                    return None

                # Extract to temp directory
                file_content = zf.read(found_path)
                output_file = temp_dir / media_reference
                output_file.write_bytes(file_content)

                logger.debug(f"Delivered media: {media_reference} → {output_file}")
                return output_file

        except zipfile.BadZipFile as e:
            logger.error(f"Invalid ZIP file: {zip_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to extract {media_reference} from {zip_path}: {e}")
            return None

    def extract_media(
        self,
        input_path: Path,
        output_dir: Path,
        **kwargs: Any,
    ) -> MediaMapping:
        """Extract media files from WhatsApp ZIP (DEPRECATED).

        This method is deprecated in favor of deliver_media(). Media extraction
        is now handled lazily by the runner calling deliver_media() for each
        markdown reference found in messages.

        Args:
            input_path: Path to WhatsApp ZIP export
            output_dir: Directory where media should be extracted
            **kwargs: Additional parameters

        Returns:
            Empty dict (media extraction handled by deliver_media())
        """
        # Deprecated: Use deliver_media() instead for lazy extraction
        return {}

    def get_metadata(self, input_path: Path, **kwargs: Any) -> dict[str, Any]:
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
            raise FileNotFoundError(f"Input path does not exist: {input_path}")

        # Discover chat file and group name
        group_name, chat_file = discover_chat_file(input_path)
        group_slug = GroupSlug(group_name.lower().replace(" ", "-"))

        return {
            "group_name": group_name,
            "group_slug": str(group_slug),
            "chat_file": chat_file,
            "export_date": datetime.now().date().isoformat(),
        }
