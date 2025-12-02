"""WhatsApp adapter implementation."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from egregora.config.settings import EgregoraConfig
from egregora.data_primitives.document import Document, DocumentType
from egregora.input_adapters.base import AdapterMeta, Export, InputAdapter
from egregora.input_adapters.whatsapp.commands import extract_commands, filter_egregora_messages
from egregora.input_adapters.whatsapp.parsing import parse_source

if TYPE_CHECKING:
    from ibis.expr.types import Table

logger = logging.getLogger(__name__)


class WhatsAppAdapter(InputAdapter):
    """Adapter for WhatsApp chat exports (ZIP files)."""

    def __init__(self, config: EgregoraConfig | None = None) -> None:
        """Initialize adapter."""
        self.config = config

    @property
    def source_name(self) -> str:
        return "WhatsApp"

    @property
    def source_identifier(self) -> str:
        return "whatsapp"

    def get_adapter_metadata(self) -> AdapterMeta:
        return {
            "name": "WhatsApp",
            "version": "1.0.0",
            "source": "whatsapp",
            "doc_url": "https://franklinbaldo.github.io/egregora/adapters/whatsapp/",
            "ir_version": "v1",
        }

    def parse(self, input_path: Path, *, timezone: str | None = None, **kwargs: Any) -> Table:
        """Parse WhatsApp export ZIP file."""
        return parse_source(input_path, timezone=timezone, output_adapter=kwargs.get("output_adapter"))

    def deliver_media(self, media_reference: str, **kwargs: Any) -> Document | None:
        """Deliver media file from ZIP archive."""
        import zipfile

        zip_path = kwargs.get("zip_path")
        if not zip_path:
            return None

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                try:
                    content = zf.read(media_reference)
                    return Document(
                        content=content,
                        type=DocumentType.MEDIA,
                        metadata={"filename": media_reference},
                    )
                except KeyError:
                    return None
        except (zipfile.BadZipFile, FileNotFoundError):
            return None

    def get_metadata(self, input_path: Path, **kwargs: Any) -> dict[str, Any]:
        """Extract metadata from WhatsApp export."""
        # Simple implementation - could be enhanced to parse group name from filename or content
        import zipfile

        try:
            with zipfile.ZipFile(input_path, "r") as zf:
                file_list = zf.namelist()
                txt_files = [f for f in file_list if f.endswith(".txt")]
                chat_file = txt_files[0] if txt_files else "unknown"

                # Try to guess group name from filename if possible, else "WhatsApp Chat"
                group_name = input_path.stem.replace("WhatsApp Chat - ", "")

                return {
                    "group_name": group_name,
                    "file_count": len(file_list),
                    "chat_file": chat_file,
                }
        except Exception:
            return {}

    @property
    def content_summary(self) -> str:
        return (
            "This is a WhatsApp group chat archive. "
            "Messages are informal, often short, and may contain slang, emojis, and media references. "
            "Participants often reply to specific messages (quoted text)."
        )

    @property
    def generation_instructions(self) -> str:
        return (
            "When summarizing or rewriting, capture the informal and conversational tone of the group. "
            "Pay attention to the flow of conversation and how participants interact."
        )

    def extract_commands(self, table: Table) -> list[Any]:
        """Extract /egregora commands from WhatsApp messages."""
        return extract_commands(table)

    def filter_messages(self, table: Table) -> tuple[Table, int]:
        """Filter out egregora commands from the message stream."""
        return filter_egregora_messages(table)
