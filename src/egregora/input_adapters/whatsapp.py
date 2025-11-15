"""WhatsApp source adapter - parses WhatsApp ZIP exports into MESSAGE_SCHEMA.

This adapter uses vectorized Pandas operations for performance and produces
MESSAGE_SCHEMA-compliant tables with immediate anonymization.

Design:
- Vectorized processing (Pandas → Ibis)
- Privacy-first: author_raw never leaves adapter
- Two-level source identity: provider_type + provider_instance
- Generic field names (no whatsapp_* columns)

Media Handling:
- parse() converts WhatsApp media references to markdown format
- Media metadata stored in JSON metadata column
- deliver_media() extracts specific files from ZIP on demand
"""

from __future__ import annotations

import hashlib
import logging
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict, Unpack
from uuid import UUID, uuid5

import ibis
import pandas as pd

from egregora.database.ir_schema import MESSAGE_SCHEMA, validate_message_schema
from egregora.privacy.anonymizer import anonymize_author
from egregora.sources.base import AdapterMeta, InputAdapter
from egregora.sources.whatsapp.models import WhatsAppExport
from egregora.sources.whatsapp.parser import parse_source
from egregora.sources.whatsapp.pipeline import discover_chat_file

if TYPE_CHECKING:
    from ibis.expr.types import Table

logger = logging.getLogger(__name__)
__all__ = ["WhatsAppAdapter"]

# Namespace for deterministic message IDs
NAMESPACE_MESSAGE = UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

# Media detection patterns
ATTACHMENT_MARKERS = ("(arquivo anexado)", "(file attached)", "(archivo adjunto)", "\u200e<attached:")
WA_MEDIA_PATTERN = re.compile(r"\b((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)\b")
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


class _EmptyKwargs(TypedDict):
    """Empty TypedDict for unused kwargs in adapter methods."""


class DeliverMediaKwargs(TypedDict, total=False):
    """Kwargs for WhatsAppAdapter.deliver_media method."""

    zip_path: Path


def _detect_media_type(filename: str) -> str:
    """Detect media type from filename extension."""
    ext = Path(filename).suffix.lower()
    return MEDIA_EXTENSIONS.get(ext, "file")


def _convert_media_to_markdown(content: str, media_files: list[str]) -> str:
    """Convert WhatsApp media references to markdown format.

    Args:
        content: Original message content
        media_files: List of media filenames found in content

    Returns:
        Content with media references converted to markdown

    """
    if not content or not media_files:
        return content

    result = content

    for filename in media_files:
        media_type = _detect_media_type(filename)

        # Create markdown based on type
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

        # Replace with attachment markers
        for marker in ATTACHMENT_MARKERS:
            pattern = re.escape(filename) + r"\s*" + re.escape(marker)
            result = re.sub(pattern, markdown, result, flags=re.IGNORECASE)

        # Replace standalone filename
        if filename in result and markdown not in result:
            result = re.sub(r"\b" + re.escape(filename) + r"\b", markdown, result)

    return result


def _slugify(name: str) -> str:
    """Convert group name to provider_instance slug.

    Examples:
        "Family Group" → "family-group"
        "Engineering_Team" → "engineering-team"

    """
    return name.lower().replace(" ", "-").replace("_", "-")


class WhatsAppAdapter(InputAdapter):
    """Source adapter for WhatsApp ZIP exports.

    Produces MESSAGE_SCHEMA-compliant tables using vectorized processing.

    Example:
        >>> adapter = WhatsAppAdapter()
        >>> table = adapter.parse(Path("export.zip"), timezone="UTC")
        >>> validate_message_schema(table)  # Passes
        >>> # All authors are anonymized (8-char hex)
        >>> # provider_type = "whatsapp"
        >>> # provider_instance = "family-chat" (from group name)

    """

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
            version="2.0.0",  # Bumped for MESSAGE_SCHEMA
            source="whatsapp",
            doc_url="https://github.com/franklinbaldo/egregora#whatsapp-exports",
            ir_version="v2",  # MESSAGE_SCHEMA
        )

    def parse(self, input_path: Path, *, timezone: str | None = None, **_kwargs: _EmptyKwargs) -> Table:
        """Parse WhatsApp ZIP export into MESSAGE_SCHEMA table.

        Uses vectorized Pandas operations for performance:
        1. Parse to DataFrame
        2. Vectorized anonymization (immediate, author_raw dropped)
        3. Extract media to metadata JSON
        4. Generate deterministic message IDs
        5. Convert to Ibis MESSAGE_SCHEMA table

        Args:
            input_path: Path to WhatsApp ZIP export
            timezone: Timezone for timestamp normalization
            **_kwargs: Additional parameters (unused)

        Returns:
            Ibis Table conforming to MESSAGE_SCHEMA

        Raises:
            ValueError: If ZIP is invalid or chat file not found
            FileNotFoundError: If input_path does not exist

        """
        # Validate input
        if not input_path.exists():
            msg = f"Input path does not exist: {input_path}"
            raise FileNotFoundError(msg)
        if not input_path.is_file() or not str(input_path).endswith(".zip"):
            msg = f"Expected a ZIP file, got: {input_path}"
            raise ValueError(msg)

        # Discover group name and chat file
        group_name, chat_file = discover_chat_file(input_path)
        provider_instance = _slugify(group_name)

        # Parse using existing parser (returns old schema table)
        export = WhatsAppExport(
            zip_path=input_path,
            group_name=group_name,
            group_slug=provider_instance,
            export_date=datetime.now(tz=UTC).date(),
            chat_file=chat_file,
            media_files=[],
        )
        old_table = parse_source(export, timezone=timezone)

        # Convert to DataFrame for vectorized operations
        df = old_table.execute()

        # Transform to MESSAGE_SCHEMA (vectorized)
        df = self._transform_to_message_schema(
            df=df,
            provider_instance=provider_instance,
            timezone=timezone or "UTC",
        )

        # Convert back to Ibis table with MESSAGE_SCHEMA
        table = ibis.memtable(df, schema=MESSAGE_SCHEMA)

        # Validate schema
        validate_message_schema(table)

        logger.info(
            "✅ Parsed %d messages from WhatsApp group: %s",
            len(df),
            provider_instance,
        )

        return table

    def _transform_to_message_schema(
        self,
        df: pd.DataFrame,
        provider_instance: str,
        timezone: str,
    ) -> pd.DataFrame:
        """Transform old schema DataFrame to MESSAGE_SCHEMA.

        Vectorized transformation pipeline:
        1. Rename columns (timestamp, author, message → content)
        2. Add provider fields
        3. Anonymize authors (vectorized) + DROP author_raw
        4. Extract media to metadata
        5. Generate message IDs

        """
        # Step 1: Rename columns to MESSAGE_SCHEMA names
        df = df.rename(columns={"message": "content"})

        # Step 2: Add provider fields (vectorized)
        df["provider_type"] = "whatsapp"
        df["provider_instance"] = provider_instance

        # Step 3: Anonymize authors (vectorized mapping)
        # Build mapping once for all unique authors
        unique_authors = df["author"].unique()
        author_map = {author: anonymize_author(author) for author in unique_authors}

        # Create temporary author_raw for building metadata
        df["author_raw"] = df["author"]

        # Apply anonymization (vectorized)
        df["author"] = df["author"].map(author_map)

        # Step 4: Extract media to metadata (vectorized)
        df = self._extract_media_to_metadata(df)

        # Step 5: Generate deterministic message IDs (vectorized)
        df = self._generate_message_ids(df)

        # Step 6: Drop temporary and old schema columns
        columns_to_drop = [
            "author_raw",  # 🔒 CRITICAL: Drop raw names!
            "date",  # Not in MESSAGE_SCHEMA
            "original_line",  # Moved to metadata
            "tagged_line",  # Not needed
            "message_id",  # Old ID, replaced with new deterministic one
        ]
        df = df.drop(columns=[col for col in columns_to_drop if col in df.columns])

        # Step 7: Ensure column order matches MESSAGE_SCHEMA
        df = df[
            ["message_id", "provider_type", "provider_instance", "timestamp", "author", "content", "metadata"]
        ]

        return df

    def _extract_media_to_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract media references into metadata JSON column (vectorized)."""
        # Vectorized regex extraction
        df["media_files"] = df["content"].str.findall(WA_MEDIA_PATTERN)

        # Build metadata JSON for each row
        def build_metadata(row):
            meta = {}

            # Add media if present
            if row["media_files"]:
                meta["media"] = [
                    {"filename": filename, "type": _detect_media_type(filename)}
                    for filename in row["media_files"]
                ]

            # Add original line for debugging (if exists)
            if "original_line" in row and pd.notna(row["original_line"]):
                meta["original_line"] = row["original_line"]

            return meta if meta else None

        df["metadata"] = df.apply(build_metadata, axis=1)

        # Convert media to markdown in content (vectorized)
        df["content"] = df.apply(
            lambda row: _convert_media_to_markdown(row["content"], row["media_files"]), axis=1
        )

        # Drop temp column
        df = df.drop(columns=["media_files"])

        return df

    def _generate_message_ids(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate deterministic UUID5 message IDs (vectorized)."""

        def make_id(row):
            # Composite key for determinism
            composite = (
                f"{row['provider_type']}:"
                f"{row['provider_instance']}:"
                f"{row['timestamp'].isoformat()}:"
                f"{row['author']}:"  # Already anonymized!
                f"{row['content']}"
            )
            content_hash = hashlib.sha256(composite.encode()).hexdigest()
            return str(uuid5(NAMESPACE_MESSAGE, content_hash))

        df["message_id"] = df.apply(make_id, axis=1)
        return df

    def get_metadata(self, input_path: Path) -> dict[str, Any]:
        """Get metadata about WhatsApp export without parsing all messages.

        Args:
            input_path: Path to WhatsApp ZIP export

        Returns:
            Metadata dictionary with group_name, provider_instance

        """
        group_name, _ = discover_chat_file(input_path)
        return {
            "group_name": group_name,
            "provider_type": "whatsapp",
            "provider_instance": _slugify(group_name),
        }

    def deliver_media(
        self, media_reference: str, temp_dir: Path, **kwargs: Unpack[DeliverMediaKwargs]
    ) -> Path | None:
        """Deliver media file from WhatsApp ZIP to temporary directory.

        Extracts the requested media file from the ZIP and writes it to temp_dir.
        The file is extracted with its original name for the runner to process.

        Args:
            media_reference: Media filename from message content (e.g. "IMG-001.jpg")
            temp_dir: Temporary directory to extract media into
            **kwargs: Must include zip_path (Path to WhatsApp ZIP)

        Returns:
            Path to extracted media file, or None if not found

        Example:
            >>> adapter = WhatsAppAdapter()
            >>> path = adapter.deliver_media(
            ...     "IMG-001.jpg",
            ...     Path("/tmp/media"),
            ...     zip_path=Path("export.zip")
            ... )

        """
        zip_path = kwargs.get("zip_path")
        if not zip_path:
            logger.warning("deliver_media called without zip_path")
            return None

        try:
            with zipfile.ZipFile(zip_path) as zf:
                # Try to find media file in ZIP
                for member in zf.namelist():
                    if Path(member).name == media_reference:
                        # Extract to temp_dir
                        extracted = zf.extract(member, temp_dir)
                        # Rename to just filename (remove any path prefix)
                        final_path = temp_dir / media_reference
                        Path(extracted).rename(final_path)
                        logger.debug("Delivered media: %s", media_reference)
                        return final_path

            logger.warning("Media file not found in ZIP: %s", media_reference)
            return None

        except Exception:
            logger.exception("Failed to deliver media: %s", media_reference)
            return None
