"""WhatsApp input source implementation."""

from __future__ import annotations

import logging
import zipfile
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from egregora.database.schemas import group_slug
from egregora.database.schemas import group_slug as create_slug
from egregora.enrichment.batch import _iter_table_record_batches
from egregora.enrichment.media import extract_media_from_zip, find_media_references
from egregora.sources.base import AdapterMeta, InputMetadata, InputSource
from egregora.sources.whatsapp.models import WhatsAppExport
from egregora.sources.whatsapp.parser import parse_source  # Phase 6: Renamed from parse_export

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

    from ibis.expr.types import Table
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
        try:
            with zipfile.ZipFile(source_path) as zf:
                txt_files = [f for f in zf.namelist() if f.endswith(".txt")]
                return len(txt_files) > 0
        except zipfile.BadZipFile:
            logger.debug("File %s is not a valid ZIP file (corrupted)", source_path)
            return False
        except PermissionError:
            logger.debug("Permission denied reading %s", source_path)
            return False
        except OSError as e:
            logger.debug("OS error reading %s: %s", source_path, e)
            return False

    def parse(
        self,
        source_path: Path,
        group_name: str | None = None,
        export_date: date | None = None,
        timezone: str | None = None,
        **_kwargs: Any,
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
            msg = f"Source path {source_path} is not a valid WhatsApp export ZIP"
            raise ValueError(msg)
        chat_file, media_files = self._detect_zip_contents(source_path)
        if group_name is None:
            group_name = self._infer_group_name(source_path)
        if export_date is None:
            export_date = datetime.now(tz=UTC).date()
        slug = group_slug(group_name)
        export = WhatsAppExport(
            zip_path=source_path,
            group_name=group_name,
            group_slug=slug,
            export_date=export_date,
            chat_file=chat_file,
            media_files=media_files,
        )
        try:
            table = parse_source(export, timezone=timezone)  # Phase 6: parse_source renamed
        except Exception as e:
            msg = f"Failed to parse WhatsApp export: {e}"
            raise RuntimeError(msg) from e
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
        return (table, metadata)

    def extract_media(
        self,
        source_path: Path,
        output_dir: Path,
        group_slug: str | None = None,
        table: Table | None = None,
        **_kwargs: Any,
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
            msg = f"Source path {source_path} is not a valid WhatsApp export ZIP"
            raise ValueError(msg)
        if group_slug is None:
            group_name = self._infer_group_name(source_path)
            group_slug = create_slug(group_name)
        media_filenames = set()
        if table is not None:
            batch_size = 1000
            for batch_records in _iter_table_record_batches(table.select("message"), batch_size):
                for row in batch_records:
                    message = row.get("message", "")
                    refs = find_media_references(message)
                    media_filenames.update(refs)
        if not media_filenames:
            _, media_files = self._detect_zip_contents(source_path)
            media_filenames = set(media_files)
        if not media_filenames:
            return {}
        # UUID generation is content-based only (global deduplication)
        extracted = extract_media_from_zip(
            zip_path=source_path, filenames=media_filenames, docs_dir=output_dir
        )
        result = {}
        for original, absolute_path in extracted.items():
            try:
                relative = absolute_path.relative_to(output_dir)
                result[original] = str(relative)
            except ValueError:
                logger.exception(
                    "Media file %s at %s is not relative to output_dir %s. This is a bug. Skipping file.",
                    original,
                    absolute_path,
                    output_dir,
                )
        return result

    def adapter_meta(self) -> AdapterMeta:
        """Return adapter metadata for plugin discovery.

        Returns:
            AdapterMeta with name, version, source, doc_url, ir_version

        """
        return {
            "name": "whatsapp",
            "version": "1.0.0",
            "source": "WhatsApp",
            "doc_url": "https://docs.egregora.dev/adapters/whatsapp",
            "ir_version": "v1",
        }

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
                txt_files = [f for f in all_files if f.endswith(".txt")]
                if not txt_files:
                    msg = f"No .txt chat file found in {zip_path}"
                    raise ValueError(msg)
                chat_file = txt_files[0]
                media_files = [f for f in all_files if f != chat_file]
                return (chat_file, media_files)
        except zipfile.BadZipFile as e:
            msg = f"Corrupted ZIP file: {zip_path}"
            raise ValueError(msg) from e
        except PermissionError as e:
            msg = f"Permission denied reading ZIP: {zip_path}"
            raise ValueError(msg) from e

    def _infer_group_name(self, zip_path: Path) -> str:
        """Infer group name from ZIP filename.

        Args:
            zip_path: Path to ZIP file

        Returns:
            Inferred group name

        """
        name = zip_path.stem
        prefixes = ["WhatsApp Chat - ", "WhatsApp-Chat-", "Chat-"]
        for prefix in prefixes:
            name = name.removeprefix(prefix)
        name = name.replace("_", " ").replace("-", " ")
        return name.strip() or "WhatsApp Export"
