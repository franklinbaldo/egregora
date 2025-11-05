"""WhatsApp source adapter - parses WhatsApp ZIP exports into IR format.

This adapter wraps the existing WhatsApp parsing logic and exposes it through
the standard SourceAdapter interface, making WhatsApp just another source in
the pipeline.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ibis.expr.types import Table

from egregora.ingestion.parser import parse_export
from egregora.pipeline.adapters import MediaMapping, SourceAdapter
from egregora.pipeline.ir import create_ir_table
from egregora.sources.whatsapp.models import WhatsAppExport
from egregora.sources.whatsapp.pipeline import discover_chat_file
from egregora.types import GroupSlug

__all__ = ["WhatsAppAdapter"]


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

        Args:
            input_path: Path to WhatsApp ZIP export
            timezone: Timezone for timestamp normalization (phone export timezone)
            **kwargs: Additional parameters (unused)

        Returns:
            Ibis Table conforming to IR_SCHEMA

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

        # Ensure IR schema compliance
        ir_table = create_ir_table(messages_table, timezone=timezone)

        return ir_table

    def extract_media(
        self,
        input_path: Path,
        output_dir: Path,
        **kwargs: Any,
    ) -> MediaMapping:
        """Extract media files from WhatsApp ZIP.

        Note: Media extraction is handled per-period in the core pipeline,
        so this returns an empty mapping. The actual extraction is done by
        the enrichment stage using extract_and_replace_media().

        Args:
            input_path: Path to WhatsApp ZIP export
            output_dir: Directory where media should be extracted
            **kwargs: Additional parameters

        Returns:
            Empty dict (media extraction handled by pipeline stages)
        """
        # Media extraction for WhatsApp is complex and period-specific,
        # so it's handled by the enrichment stage rather than here.
        # This could be refactored in the future to move media extraction
        # fully into the adapter.
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
