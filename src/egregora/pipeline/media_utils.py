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

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ibis.expr.types import Table

from egregora.enrichment.media import get_media_subfolder
from egregora.pipeline.adapters import SourceAdapter

if TYPE_CHECKING:
    pass  # Imports moved to top level

logger = logging.getLogger(__name__)

# Regex patterns for markdown media references
# Matches: ![alt text](reference.jpg) or [link text](reference.mp4)
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")

__all__ = [
    "extract_markdown_media_refs",
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


def replace_markdown_media_refs(
    table: Table,
    media_mapping: dict[str, Path],
    docs_dir: Path,
    posts_dir: Path,
) -> Table:
    """Replace markdown media references with standardized paths.

    Updates message column by replacing original references with standardized
    UUID-based filenames from the media mapping. Computes relative paths from
    posts_dir to the media files for markdown links.

    Args:
        table: Ibis table with 'message' column
        media_mapping: Dict mapping original reference to absolute file path
                      Example: {"photo.jpg": Path("/abs/path/docs/media/images/a1b2c3d4.jpg")}
        docs_dir: MkDocs docs directory (for fallback relative path computation)
        posts_dir: Posts directory (for computing relative links)

    Returns:
        Updated table with replaced references

    Example:
        >>> table = ibis.memtable([{"message": "See ![photo](IMG-001.jpg)"}])
        >>> mapping = {"IMG-001.jpg": Path("/site/docs/media/abc123.jpg")}
        >>> updated = replace_markdown_media_refs(
        ...     table, mapping,
        ...     docs_dir=Path("/site/docs"),
        ...     posts_dir=Path("/site/docs/posts")
        ... )
        >>> # Message is now: "See ![photo](../media/abc123.jpg)"
    """
    if not media_mapping:
        return table

    # Execute table to pandas for efficient string replacement
    df = table.execute()

    # Replace references in message column
    for original_ref, absolute_path in media_mapping.items():
        # Compute relative path from posts_dir to media file
        # This matches the behavior of the old replace_media_mentions() function
        try:
            import os

            relative_link = Path(os.path.relpath(absolute_path, posts_dir)).as_posix()
        except ValueError:
            # Fallback: use docs_dir-relative path with leading slash
            try:
                relative_link = "/" + absolute_path.relative_to(docs_dir).as_posix()
            except ValueError:
                # Last resort: use absolute path
                relative_link = absolute_path.as_posix()

        # Replace in both image and link markdown formats
        # Image: ![alt](original) → ![alt](relative_link)
        df["message"] = df["message"].str.replace(
            f"]({original_ref})",
            f"]({relative_link})",
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
    docs_dir: Path,
    posts_dir: Path,
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
        docs_dir: MkDocs docs directory (for relative path computation)
        posts_dir: Posts directory (for relative path computation)
        **adapter_kwargs: Additional kwargs to pass to adapter.deliver_media()

    Returns:
        Tuple of (updated_table, media_mapping):
        - updated_table: Table with replaced media references
        - media_mapping: Dict mapping original refs to absolute file paths

    Example:
        >>> adapter = WhatsAppAdapter()
        >>> table, mapping = process_media_for_period(
        ...     period_table=day_table,
        ...     adapter=adapter,
        ...     media_dir=Path("output/media"),
        ...     temp_dir=Path("/tmp"),
        ...     docs_dir=Path("output"),
        ...     posts_dir=Path("output/posts"),
        ...     zip_path=Path("export.zip"),  # adapter-specific kwarg
        ... )
        >>> print(mapping)
        {'IMG-001.jpg': Path('/abs/path/output/media/images/abc-uuid.jpg')}
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

            # Step 4: Standardize media file using base class helper method
            # This handles: UUID generation, subfolder placement, deduplication
            standardized_path = adapter.standardize_media_file(
                source_file=delivered_file,
                media_dir=media_dir,
                get_subfolder=get_media_subfolder,
            )

            # Step 5: Store mapping with ABSOLUTE path for enrichment stage
            # The enrichment stage needs absolute paths to access files
            media_mapping[media_ref] = standardized_path
            processed_count += 1

        except Exception as e:
            logger.warning(f"Failed to process media '{media_ref}': {e}")
            failed_refs.append(media_ref)
            continue

    logger.info(f"Successfully processed {processed_count}/{len(media_refs)} media files")
    if failed_refs:
        logger.warning(f"Failed to process {len(failed_refs)} media files: {failed_refs}")

    # Step 9: Replace media references in messages with relative paths
    if media_mapping:
        updated_table = replace_markdown_media_refs(
            period_table,
            media_mapping,
            docs_dir=docs_dir,
            posts_dir=posts_dir,
        )
    else:
        updated_table = period_table

    return updated_table, media_mapping
