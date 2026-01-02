"""Adapter implementation for WhatsApp exports."""

from __future__ import annotations

import logging
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, Unpack

from egregora.data_primitives.document import Document, DocumentType
from egregora.input_adapters.base import AdapterMeta, InputAdapter
from egregora.input_adapters.whatsapp.commands import EGREGORA_COMMAND_PATTERN
from egregora.input_adapters.whatsapp.exceptions import (
    InvalidMediaReferenceError,
    InvalidZipFileError,
    MediaExtractionError,
    MediaNotFoundError,
    MissingZipPathError,
    WhatsAppAdapterError,
    WhatsAppParsingError,
    ZipPathNotFoundError,
)
from egregora.input_adapters.whatsapp.parsing import WhatsAppExport, parse_source
from egregora.input_adapters.whatsapp.utils import discover_chat_file
from egregora.orchestration.pipelines.modules.media import detect_media_type
from egregora.security.zip import validate_zip_contents
from egregora.shared.paths import slugify

if TYPE_CHECKING:
    import uuid

    import ibis

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
        try:
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
                config=self._config,
            )

            logger.debug("Parsed WhatsApp export with %s messages", messages_table.count().execute())
            return messages_table
        except (FileNotFoundError, ValueError) as e:
            logger.exception("Validation failed for input path %s: %s", input_path, e)
            msg = f"Invalid input path: {input_path}"
            raise WhatsAppAdapterError(msg) from e
        except zipfile.BadZipFile as e:
            logger.exception("Invalid ZIP file provided at %s: %s", input_path, e)
            raise InvalidZipFileError(str(input_path)) from e
        except WhatsAppParsingError as e:
            logger.exception("Failed to parse WhatsApp export at %s: %s", input_path, e)
            msg = f"Failed to parse WhatsApp export: {e}"
            raise WhatsAppAdapterError(msg) from e

    def deliver_media(self, media_reference: str, **kwargs: Unpack[DeliverMediaKwargs]) -> Document:
        """Deliver media file from WhatsApp ZIP as a Document."""
        self._validate_media_reference(media_reference)
        zip_path = self._get_validated_zip_path(kwargs)
        return self._extract_media_from_zip(zip_path, media_reference)

    def _validate_media_reference(self, media_reference: str) -> None:
        if ".." in media_reference or "/" in media_reference or "\\" in media_reference:
            logger.warning("Suspicious media reference (path traversal attempt): %s", media_reference)
            raise InvalidMediaReferenceError(media_reference)

    def _get_validated_zip_path(self, kwargs: DeliverMediaKwargs) -> Path:
        zip_path_raw = kwargs.get("zip_path")
        if not zip_path_raw:
            raise MissingZipPathError

        zip_path = Path(zip_path_raw) if not isinstance(zip_path_raw, Path) else zip_path_raw

        if not zip_path.exists():
            raise ZipPathNotFoundError(str(zip_path))
        return zip_path

    def _extract_media_from_zip(self, zip_path: Path, media_reference: str) -> Document:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                validate_zip_contents(zf)
                found_path = self._find_media_in_zip(zip_path, zf, media_reference)

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
        except zipfile.BadZipFile as e:
            raise InvalidZipFileError(str(zip_path)) from e
        except (KeyError, OSError, PermissionError) as e:
            raise MediaExtractionError(
                media_reference, str(zip_path), f"Failed to extract file from ZIP: {e}"
            ) from e

    def _find_media_in_zip(self, zip_path: Path, zf: zipfile.ZipFile, media_reference: str) -> str:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if Path(info.filename).name.lower() == media_reference.lower():
                return info.filename
        raise MediaNotFoundError(str(zip_path), media_reference)

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
