"""Extracts enrichment candidates (URLs, media references) from message tables."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibis.expr.types import Table

from egregora.ops.media import extract_urls


def extract_unique_urls(messages_table: Table, max_enrichments: int) -> set[str]:
    """Extracts a unique set of URLs from the messages table."""
    unique_urls: set[str] = set()
    url_messages = messages_table.filter(messages_table.text.notnull()).execute()
    for row in url_messages.itertuples():
        if len(unique_urls) >= max_enrichments:
            break
        urls = extract_urls(row.text)
        for url in urls:
            if len(unique_urls) >= max_enrichments:
                break
            unique_urls.add(url)
    return unique_urls


def _build_media_filename_lookup(media_mapping: dict[str, Path]) -> dict[str, tuple[str, Path]]:
    """Build a lookup dict mapping media filenames to (original_filename, file_path)."""
    lookup: dict[str, tuple[str, Path]] = {}
    for original_filename, file_path in media_mapping.items():
        lookup[original_filename] = (original_filename, file_path)
        lookup[file_path.name] = (original_filename, file_path)
    return lookup


def extract_unique_media_references(messages_table: Table, media_mapping: dict[str, Path]) -> set[str]:
    """Extract unique media references from messages table."""
    media_filename_lookup = _build_media_filename_lookup(media_mapping)
    media_messages = messages_table.filter(messages_table.text.notnull()).execute()
    unique_media: set[str] = set()

    for row in media_messages.itertuples():
        from egregora.ops.media import find_media_references  # noqa: PLC0415

        refs = find_media_references(row.text)
        markdown_refs = re.findall("!\\[[^\\]]*\\]\\([^)]*?([a-f0-9\\-]+\\.\\w+)\\)", row.text)
        uuid_refs = re.findall(
            "\\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\\.\\w+)",
            row.text,
        )
        refs.extend(markdown_refs)
        refs.extend(uuid_refs)

        for ref in set(refs):
            if ref in media_filename_lookup:
                unique_media.add(ref)

    return unique_media
