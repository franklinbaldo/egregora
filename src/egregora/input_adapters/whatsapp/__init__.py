
"""WhatsApp input adapter and parsing utilities."""

from __future__ import annotations

import logging
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, Unpack

import ibis

from egregora.data_primitives import GroupSlug
from egregora.database.validation import create_ir_table
from egregora.input_adapters.base import AdapterMeta, InputAdapter
from egregora.orchestration.whatsapp import discover_chat_file

from .models import WhatsAppExport
from .parser import parse_source

if TYPE_CHECKING:
    from ibis.expr.types import Table

logger = logging.getLogger(__name__)
__all__ = ["WhatsAppAdapter", "WhatsAppExport"]


class _EmptyKwargs(TypedDict):
    """Empty TypedDict for unused kwargs in adapter methods."""


class DeliverMediaKwargs(TypedDict, total=False):
    """Kwargs for WhatsAppAdapter.deliver_media method."""

    zip_path: Path


ATTACHMENT_MARKERS = ("(arquivo anexado)", "(file attached)", "(archivo adjunto)", "‎<attached:")
WA_MEDIA_PATTERN = re.compile("\b((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b")
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
    """Convert WhatsApp media references to markdown format."""

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
            pattern = re.escape(filename) + "\s*" + re.escape(marker)
            result = re.sub(pattern, markdown, result, flags=re.IGNORECASE)
        if filename in result and markdown not in result:
            result = re.sub("\b" + re.escape(filename) + "\b", markdown, result)
    return result


class WhatsAppAdapter(InputAdapter):
    """Source adapter for WhatsApp ZIP exports."""

    @property
    def source_name(self) -> str:
        return "WhatsApp"

    @property
    def source_identifier(self) -> str:
        return "whatsapp"

    def get_adapter_metadata(self) -> AdapterMeta:
        """Return adapter metadata for plugin discovery."""

        return AdapterMeta(
            name="WhatsApp",
            version="1.0.0",
            source="whatsapp",
            doc_url="https://github.com/franklinbaldo/egregora#whatsapp-exports",
            ir_version="v1",
        )

    def parse(self, input_path: Path, *, timezone: str | None = None, **_kwargs: _EmptyKwargs) -> Table:
        """Parse WhatsApp ZIP export into an IR-compliant table."""

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
        messages_table = parse_source(export, timezone=timezone)

        @ibis.udf.scalar.python
        def convert_media_to_markdown(message: str | None) -> str | None:
            if message is None:
                return None
            return _convert_whatsapp_media_to_markdown(message)

        messages_table = messages_table.mutate(message=convert_media_to_markdown(messages_table.message))
        ir_table = create_ir_table(messages_table, timezone=timezone)
        logger.debug("Parsed WhatsApp export with %s messages", ir_table.count().execute())
        return ir_table

    def get_metadata(self, input_path: Path, **_kwargs: Unpack[_EmptyKwargs]) -> dict[str, Any]:
        """Extract metadata for the WhatsApp export."""

        group_name, chat_file = discover_chat_file(input_path)
        return {
            "group_name": group_name,
            "chat_file": chat_file,
        }

    def extract_media(self, input_path: Path, output_dir: Path, **_kwargs: Unpack[_EmptyKwargs]) -> dict[str, Path]:
        """Extract media files bundled with the WhatsApp export."""

        media_mapping: dict[str, Path] = {}
        with zipfile.ZipFile(input_path) as archive:
            for member in archive.namelist():
                if member.startswith("_"):
                    continue
                if member.endswith(".txt"):
                    continue
                target_path = output_dir / Path(member).name
                with archive.open(member) as source, target_path.open("wb") as target:
                    target.write(source.read())
                media_mapping[member] = target_path
        return media_mapping

    def deliver_media(
        self,
        *,
        input_path: Path,
        media_path: Path,
        output_path: Path,
        **kwargs: Unpack[DeliverMediaKwargs],
    ) -> None:
        """Deliver a single media file on demand."""

        zip_path = kwargs.get("zip_path", input_path)
        with zipfile.ZipFile(zip_path) as archive, archive.open(media_path.name) as source, output_path.open("wb") as target:
            target.write(source.read())
