"""WhatsApp input source implementation."""

from __future__ import annotations

import logging
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from ibis.expr.types import Table

from ..augmentation.enrichment.batch import _iter_table_record_batches
from ..augmentation.enrichment.media import (
    extract_media_from_zip,
    find_media_references,
)
from ..core.input_source import InputMetadata, InputSource
from ..core.models import WhatsAppExport
from ..core.schema import group_slug
from .parser import parse_export

logger = logging.getLogger(__name__)


class WhatsAppInputSource(InputSource):
    """WhatsApp input source for ZIP exports.

    Parses WhatsApp export ZIP files into standardized Ibis Tables.
    Supports:
    - Text message parsing with date/time/author extraction
    - Media file extraction (images, videos, audio, documents)
    - Multi-line messages
    - Portuguese and English date formats
    """

    @property
    def source_type(self) -> str:
        """Return 'whatsapp' as the source type identifier."""
        return "whatsapp"

    def supports_format(self, source_path: Path) -> bool:
        """Check if the path is a valid WhatsApp export ZIP.

        Args:
            source_path: Path to check

        Returns:
            True if it's a ZIP file containing a .txt chat file
        """
        if not source_path.exists():
            return False

        if not source_path.is_file():
            return False

        if source_path.suffix.lower() != ".zip":
            return False

        # Check if ZIP contains a .txt file (chat export)
        try:
            with zipfile.ZipFile(source_path) as zf:
                txt_files = [f for f in zf.namelist() if f.endswith(".txt")]
                return len(txt_files) > 0
        except zipfile.BadZipFile:
            logger.debug(f"File {source_path} is not a valid ZIP file (corrupted)")
            return False
        except PermissionError:
            logger.debug(f"Permission denied reading {source_path}")
            return False
        except OSError as e:
            logger.debug(f"OS error reading {source_path}: {e}")
            return False

    def parse(
        self,
        source_path: Path,
        group_name: str | None = None,
        export_date: date | None = None,
        timezone: Any = None,
        **kwargs,
    ) -> tuple[Table, InputMetadata]:
        """Parse WhatsApp export ZIP into standardized Ibis Table.

        Args:
            source_path: Path to the WhatsApp export ZIP file
            group_name: Optional display name for the group/chat
            export_date: Optional export date (defaults to today)
            timezone: Optional ZoneInfo timezone object
            **kwargs: Additional options (ignored)

        Returns:
            tuple of (messages_table, metadata)

        Raises:
            ValueError: If source_path is not a valid WhatsApp export
            RuntimeError: If parsing fails
        """
        if not self.supports_format(source_path):
            raise ValueError(f"Source path {source_path} is not a valid WhatsApp export ZIP")

        # Detect chat file and media files in ZIP
        chat_file, media_files = self._detect_zip_contents(source_path)

        # Infer group name from filename if not provided
        if group_name is None:
            group_name = self._infer_group_name(source_path)

        # Use today's date if export_date not provided
        if export_date is None:
            from datetime import date as date_type

            export_date = date_type.today()

        # Create WhatsAppExport metadata
        slug = group_slug(group_name)
        export = WhatsAppExport(
            zip_path=source_path,
            group_name=group_name,
            group_slug=slug,
            export_date=export_date,
            chat_file=chat_file,
            media_files=media_files,
        )

        # Parse using existing parser
        try:
            table = parse_export(export, timezone=timezone)
        except Exception as e:
            raise RuntimeError(f"Failed to parse WhatsApp export: {e}") from e

        # Create metadata
        metadata = InputMetadata(
            source_type=self.source_type,
            group_name=group_name,
            group_slug=slug,
            export_date=export_date,
            timezone=str(timezone) if timezone else None,
            additional_metadata={
                "chat_file": chat_file,
                "media_count": len(media_files),
                "zip_path": str(source_path),
            },
        )

        return table, metadata

    def extract_media(
        self,
        source_path: Path,
        output_dir: Path,
        group_slug: str | None = None,
        table: Table | None = None,
        **kwargs,
    ) -> dict[str, str]:
        """Extract media files from WhatsApp export ZIP.

        Args:
            source_path: Path to the WhatsApp export ZIP file
            output_dir: Directory to extract media files to (typically docs_dir)
            group_slug: Slug for generating deterministic UUIDs
            table: Optional Ibis Table to scan for media references
            **kwargs: Additional options

        Returns:
            Mapping of original filename -> relative path from output_dir
            Example: {"IMG-001.jpg": "media/images/abc123.jpg"}
        """
        if not self.supports_format(source_path):
            raise ValueError(f"Source path {source_path} is not a valid WhatsApp export ZIP")

        if group_slug is None:
            # Infer from filename
            from ..core.schema import group_slug as create_slug

            group_name = self._infer_group_name(source_path)
            group_slug = create_slug(group_name)

        # Find media references in messages
        media_filenames = set()

        if table is not None:
            # Scan table for media references using streaming (Ibis-first policy)
            try:
                batch_size = 1000
                for batch_records in _iter_table_record_batches(
                    table.select("message"), batch_size
                ):
                    for row in batch_records:
                        message = row.get("message", "")
                        refs = find_media_references(message)
                        media_filenames.update(refs)
            except Exception as e:
                logger.warning(f"Failed to scan table for media references: {e}")

        # If no table provided or scan failed, extract all media
        if not media_filenames:
            _, media_files = self._detect_zip_contents(source_path)
            media_filenames = set(media_files)

        if not media_filenames:
            return {}

        # Extract media files
        extracted = extract_media_from_zip(
            zip_path=source_path,
            filenames=media_filenames,
            docs_dir=output_dir,
            group_slug=group_slug,
        )

        # Convert absolute paths to relative paths from output_dir
        # Security: Never return absolute paths as they could leak system info
        result = {}
        for original, absolute_path in extracted.items():
            try:
                relative = absolute_path.relative_to(output_dir)
                result[original] = str(relative)
            except ValueError as e:
                # This should never happen if extract_media_from_zip works correctly
                # Log error and skip this file rather than exposing absolute paths
                logger.error(
                    f"Media file {original} at {absolute_path} is not relative to "
                    f"output_dir {output_dir}. This is a bug. Skipping file. Error: {e}"
                )
                # Skip this file - don't add to result

        return result

    def _detect_zip_contents(self, zip_path: Path) -> tuple[str, list[str]]:
        """Detect chat file and media files in ZIP.

        Returns:
            tuple of (chat_file, media_files)

        Raises:
            ValueError: If no .txt chat file found
            zipfile.BadZipFile: If ZIP is corrupted
            PermissionError: If permission denied
        """
        try:
            with zipfile.ZipFile(zip_path) as zf:
                all_files = [f for f in zf.namelist() if not f.endswith("/")]

                # Find .txt chat file
                txt_files = [f for f in all_files if f.endswith(".txt")]
                if not txt_files:
                    raise ValueError(f"No .txt chat file found in {zip_path}")

                # Use the first .txt file as chat file
                chat_file = txt_files[0]

                # Other files are media
                media_files = [f for f in all_files if f != chat_file]

                return chat_file, media_files
        except zipfile.BadZipFile as e:
            raise ValueError(f"Corrupted ZIP file: {zip_path}") from e
        except PermissionError as e:
            raise ValueError(f"Permission denied reading ZIP: {zip_path}") from e

    def _infer_group_name(self, zip_path: Path) -> str:
        """Infer group name from ZIP filename.

        Args:
            zip_path: Path to ZIP file

        Returns:
            Inferred group name
        """
        # Remove .zip extension and use filename
        name = zip_path.stem

        # Remove common prefixes like "WhatsApp Chat - "
        prefixes = ["WhatsApp Chat - ", "WhatsApp-Chat-", "Chat-"]
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix) :]

        # Clean up underscores and dashes
        name = name.replace("_", " ").replace("-", " ")

        return name.strip() or "WhatsApp Export"
