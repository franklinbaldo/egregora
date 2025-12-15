"""Adapter implementation for WhatsApp exports."""

from __future__ import annotations

import logging
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict, Unpack

import ibis

from egregora.data_primitives.document import Document, DocumentType
from egregora.input_adapters.base import AdapterMeta, InputAdapter
from egregora.input_adapters.whatsapp.commands import EGREGORA_COMMAND_PATTERN
from egregora.input_adapters.whatsapp.parsing import WhatsAppExport, parse_source
from egregora.input_adapters.whatsapp.utils import discover_chat_file
from egregora.ops.media import detect_media_type
from egregora.utils.paths import slugify
from egregora.utils.zip import validate_zip_contents

logger = logging.getLogger(__name__)


class _EmptyKwargs(TypedDict):
    """Empty TypedDict for unused kwargs in adapter methods."""


class DeliverMediaKwargs(TypedDict, total=False):
    """Kwargs for WhatsAppAdapter.deliver_media method."""

    zip_path: Path


class WhatsAppAdapter(InputAdapter):
    """Source adapter for WhatsApp ZIP exports with granular privacy support."""

    def __init__(
        self,
        *,
        author_namespace: uuid.UUID | None = None,
        config: Any | None = None,
    ) -> None:
        """Initialize WhatsApp adapter with optional privacy configuration.

        Args:
            author_namespace: Namespace for deterministic UUID generation
            config: EgregoraConfig for privacy settings (optional)

        """
        self._author_namespace = author_namespace
        self._config = config

    @property
    def source_name(self) -> str:
        return "WhatsApp"

    @property
    def source_identifier(self) -> str:
        return "whatsapp"

    @property
    def content_summary(self) -> str:
        return (
            "This adapter parses a WhatsApp export to extract chat messages. Supported format: "
            'WhatsApp ZIP exports ("Chat export" in mobile clients)'
        )

    @property
    def description(self) -> str:
        return "Parses WhatsApp chat exports and attaches optional media references."

    def get_adapter_metadata(self) -> AdapterMeta:
        return AdapterMeta(
            name="WhatsApp",
            version="1.0.0",
            source="whatsapp",
            doc_url="https://github.com/franklinbaldo/egregora#whatsapp-exports",
            ir_version="v1",
        )

    def parse(self, input_path: Path, *, timezone: str | None = None, **_kwargs: _EmptyKwargs) -> ibis.Table:
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
            group_slug=group_name.lower().replace(" ", "-"),
            export_date=datetime.now(tz=UTC).date(),
            chat_file=chat_file,
            media_files=[],
        )
        messages_table = parse_source(
            export,
            timezone=timezone,
            expose_raw_author=True,  # Always expose raw initially
        )

        logger.debug("Parsed WhatsApp export with %s messages", messages_table.count().execute())
        return messages_table

    def deliver_media(self, media_reference: str, **kwargs: Unpack[DeliverMediaKwargs]) -> Document | None:
        """Deliver media file from WhatsApp ZIP as a Document."""
        if not self._validate_media_reference(media_reference):
            return None
        zip_path = self._get_validated_zip_path(kwargs)
        if not zip_path:
            return None

        return self._extract_media_from_zip(zip_path, media_reference)

    def _validate_media_reference(self, media_reference: str) -> bool:
        if ".." in media_reference or "/" in media_reference or "\\" in media_reference:
            logger.warning("Suspicious media reference (path traversal attempt): %s", media_reference)
            return False
        return True

    def _get_validated_zip_path(self, kwargs: DeliverMediaKwargs) -> Path | None:
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

    def _extract_media_from_zip(self, zip_path: Path, media_reference: str) -> Document | None:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                validate_zip_contents(zf)
                found_path = self._find_media_in_zip(zf, media_reference)
                if not found_path:
                    logger.debug("Media file not found in ZIP: %s", media_reference)
                    return None

                file_content = zf.read(found_path)
                logger.debug("Delivered media: %s", media_reference)

                media_type = self._detect_media_type(Path(media_reference))
                media_slug = slugify(Path(media_reference).stem) if media_reference else None

                return Document(
                    content=file_content,
                    type=DocumentType.MEDIA,
                    metadata={
                        "original_filename": media_reference,
                        "media_type": media_type,
                        "slug": media_slug or None,
                        "nav_exclude": True,
                        "hide": ["navigation"],
                    },
                )
        except zipfile.BadZipFile:
            logger.exception("Invalid ZIP file: %s", zip_path)
            return None
        except (KeyError, OSError, PermissionError):
            logger.exception("Failed to extract %s from %s", media_reference, zip_path)
            return None

    def _find_media_in_zip(self, zf: zipfile.ZipFile, media_reference: str) -> str | None:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if Path(info.filename).name.lower() == media_reference.lower():
                return info.filename
        return None

    def _detect_media_type(self, media_path: Path) -> str | None:
        return detect_media_type(media_path)

    def get_metadata(self, input_path: Path, **_kwargs: _EmptyKwargs) -> dict[str, Any]:
        if not input_path.exists():
            msg = f"Input path does not exist: {input_path}"
            raise FileNotFoundError(msg)
        group_name, chat_file = discover_chat_file(input_path)
        group_slug = group_name.lower().replace(" ", "-")
        return {
            "group_name": group_name,
            "group_slug": group_slug,
            "chat_file": chat_file,
            "export_date": datetime.now(tz=UTC).date().isoformat(),
        }

    def is_command(self, message: str) -> bool:
        """Identify if a message is an egregora control command."""
        return EGREGORA_COMMAND_PATTERN.match(message.strip()) is not None
