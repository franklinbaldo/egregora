"""Media processing utilities for source-agnostic pipeline.

This module provides utilities for processing media files referenced in messages:
1. Extracting markdown media references from messages
2. Content-hash based UUID generation for deduplication
3. Lazy media delivery via source adapters
4. Standardizing media filenames and updating message references

The pipeline uses markdown format for media references:
- Images: ![alt text](filename.jpg)
- Videos/Files: [link text](filename.mp4)

Media files are renamed using UUIDv5 based on content hash, enabling:
- Deduplication: Same file content = same UUID across all sources
- Source-agnostic: Works with any adapter that implements deliver_media()
- Clean naming: No date prefixes, just {uuid}.{ext}
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from ibis.expr.types import Table

if TYPE_CHECKING:
    from egregora.pipeline.adapters import SourceAdapter

logger = logging.getLogger(__name__)

# Namespace for content-hash based UUIDs
# Using URL namespace as recommended for content-addressable identifiers
MEDIA_UUID_NAMESPACE = UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")  # URL namespace

# Regex patterns for markdown media references
# Matches: ![alt text](reference.jpg) or [link text](reference.mp4)
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")

__all__ = [
    "extract_markdown_media_refs",
    "generate_content_uuid",
    "process_media_for_period",
    "replace_markdown_media_refs",
]


def extract_markdown_media_refs(table: Table) -> set[str]:
    """Extract all markdown media references from message column.

    Finds both image references ![alt](ref) and link references [text](ref)
    in the 'message' column of the table.

    Args:
        table: Ibis table with 'message' column

    Returns:
        Set of unique media references (e.g., {"photo.jpg", "video.mp4"})

    Example:
        >>> table = ibis.memtable([
        ...     {"message": "Check this ![photo](IMG-001.jpg)"},
        ...     {"message": "Video here [video](VID-002.mp4)"},
        ... ])
        >>> extract_markdown_media_refs(table)
        {'IMG-001.jpg', 'VID-002.mp4'}
    """
    references = set()

    # Execute table and iterate over message column
    try:
        messages = table.select("message").execute()
        for row in messages.itertuples(index=False):
            message = row.message
            if not message:
                continue

            # Extract image references: ![alt](ref)
            for match in MARKDOWN_IMAGE_PATTERN.finditer(message):
                reference = match.group(2)
                references.add(reference)

            # Extract link references: [text](ref)
            # This might include non-media links, but the adapter's deliver_media()
            # will return None for those, which we handle gracefully
            for match in MARKDOWN_LINK_PATTERN.finditer(message):
                reference = match.group(2)
                # Skip obvious URLs (http://, https://)
                if not reference.startswith(("http://", "https://")):
                    references.add(reference)

    except Exception as e:
        logger.warning(f"Failed to extract media references: {e}")
        return set()

    logger.debug(f"Extracted {len(references)} unique media references")
    return references


def generate_content_uuid(file_path: Path) -> str:
    """Generate UUIDv5 based on file content hash.

    Creates a deterministic UUID from the file's SHA-256 hash, enabling
    deduplication: same content = same UUID.

    Args:
        file_path: Path to the media file

    Returns:
        UUID string (e.g., "a1b2c3d4-e5f6-5789-a1b2-c3d4e5f67890")

    Example:
        >>> # Same file content = same UUID
        >>> uuid1 = generate_content_uuid(Path("/tmp/photo1.jpg"))
        >>> uuid2 = generate_content_uuid(Path("/tmp/photo1_copy.jpg"))
        >>> uuid1 == uuid2  # True if content is identical
    """
    # Compute SHA-256 hash of file content
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)

    content_hash = sha256.hexdigest()

    # Generate UUIDv5 from content hash
    media_uuid = uuid5(MEDIA_UUID_NAMESPACE, content_hash)

    return str(media_uuid)


def replace_markdown_media_refs(
    table: Table,
    media_mapping: dict[str, Path],
) -> Table:
    """Replace markdown media references with standardized paths.

    Updates message column by replacing original references with standardized
    UUID-based filenames from the media mapping.

    Args:
        table: Ibis table with 'message' column
        media_mapping: Dict mapping original reference to standardized path
                      Example: {"photo.jpg": Path("media/a1b2c3d4.jpg")}

    Returns:
        Updated table with replaced references

    Example:
        >>> table = ibis.memtable([{"message": "See ![photo](IMG-001.jpg)"}])
        >>> mapping = {"IMG-001.jpg": Path("media/abc123.jpg")}
        >>> updated = replace_markdown_media_refs(table, mapping)
        >>> # Message is now: "See ![photo](media/abc123.jpg)"
    """
    if not media_mapping:
        return table

    # Execute table to pandas for efficient string replacement
    df = table.execute()

    # Replace references in message column
    for original_ref, standardized_path in media_mapping.items():
        # Convert Path to relative string (e.g., "media/abc123.jpg")
        standardized_ref = str(standardized_path)

        # Replace in both image and link markdown formats
        # Image: ![alt](original) → ![alt](standardized)
        df["message"] = df["message"].str.replace(
            f"]({original_ref})",
            f"]({standardized_ref})",
            regex=False,
        )

    # Convert back to Ibis table
    import ibis

    updated_table = ibis.memtable(df)

    logger.debug(f"Replaced {len(media_mapping)} media references in messages")
    return updated_table


def process_media_for_period(
    period_table: Table,
    adapter: SourceAdapter,
    media_dir: Path,
    temp_dir: Path,
    **adapter_kwargs,
) -> tuple[Table, dict[str, Path]]:
    """Process media files for a period: extract, standardize, and update references.

    This is the main media processing pipeline that:
    1. Extracts markdown media references from messages
    2. Calls adapter.deliver_media() to obtain actual files
    3. Computes content hashes and generates UUIDs
    4. Moves files to media_dir with standardized names
    5. Updates message references to point to standardized paths

    Args:
        period_table: Ibis table for this period (with 'message' column)
        adapter: Source adapter that implements deliver_media()
        media_dir: Directory where standardized media files should be stored
        temp_dir: Temporary directory for intermediate files
        **adapter_kwargs: Additional kwargs to pass to adapter.deliver_media()

    Returns:
        Tuple of (updated_table, media_mapping):
        - updated_table: Table with replaced media references
        - media_mapping: Dict mapping original refs to final paths

    Example:
        >>> adapter = WhatsAppAdapter()
        >>> table, mapping = process_media_for_period(
        ...     period_table=day_table,
        ...     adapter=adapter,
        ...     media_dir=Path("output/media"),
        ...     temp_dir=Path("/tmp"),
        ...     zip_path=Path("export.zip"),  # adapter-specific kwarg
        ... )
        >>> print(mapping)
        {'IMG-001.jpg': Path('media/a1b2c3d4-e5f6-5789-a1b2-c3d4e5f67890.jpg')}
    """
    media_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract all markdown media references
    media_refs = extract_markdown_media_refs(period_table)
    if not media_refs:
        logger.debug("No media references found in period")
        return period_table, {}

    logger.info(f"Found {len(media_refs)} media references to process")

    # Step 2: Process each media reference
    media_mapping: dict[str, Path] = {}
    processed_count = 0
    failed_refs = []

    for media_ref in media_refs:
        try:
            # Step 3: Call adapter to deliver media file
            delivered_file = adapter.deliver_media(
                media_reference=media_ref,
                temp_dir=temp_dir,
                **adapter_kwargs,
            )

            if delivered_file is None:
                logger.debug(f"Adapter could not deliver media: {media_ref}")
                continue

            if not delivered_file.exists():
                logger.warning(f"Adapter returned non-existent file: {delivered_file}")
                continue

            # Step 4: Generate content-based UUID
            media_uuid = generate_content_uuid(delivered_file)
            file_extension = delivered_file.suffix

            # Step 5: Create standardized filename (UUID + extension)
            standardized_name = f"{media_uuid}{file_extension}"
            standardized_path = media_dir / standardized_name

            # Step 6: Move file to media directory with standardized name
            if standardized_path.exists():
                # File already exists (deduplication working!)
                logger.debug(
                    f"Media file already exists (duplicate): {standardized_name}"
                )
                delivered_file.unlink()  # Remove temp file
            else:
                # Move temp file to final location
                delivered_file.rename(standardized_path)
                logger.debug(f"Standardized media: {media_ref} → {standardized_name}")

            # Step 7: Store mapping (relative path for markdown)
            media_mapping[media_ref] = Path("media") / standardized_name
            processed_count += 1

        except Exception as e:
            logger.warning(f"Failed to process media '{media_ref}': {e}")
            failed_refs.append(media_ref)
            continue

    logger.info(
        f"Successfully processed {processed_count}/{len(media_refs)} media files"
    )
    if failed_refs:
        logger.warning(f"Failed to process {len(failed_refs)} media files: {failed_refs}")

    # Step 8: Replace media references in messages
    if media_mapping:
        updated_table = replace_markdown_media_refs(period_table, media_mapping)
    else:
        updated_table = period_table

    return updated_table, media_mapping
