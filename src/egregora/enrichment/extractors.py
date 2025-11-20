"""Extracts enrichment candidates (URLs, media references) from message tables."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from egregora.data_primitives.document import Document
from egregora.input_adapters.base import MediaMapping
from egregora.ops.media import extract_urls

if TYPE_CHECKING:
    from ibis.expr.types import Table


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


def _build_media_filename_lookup(media_mapping: MediaMapping) -> dict[str, tuple[str, Document]]:
    """Build a lookup dict mapping media filenames to (original_filename, Document)."""
    lookup: dict[str, tuple[str, Document]] = {}
    for original_filename, document in media_mapping.items():
        filename = document.metadata.get("filename") or original_filename
        lookup[original_filename] = (original_filename, document)
        lookup[filename] = (original_filename, document)
    return lookup


def extract_unique_media_references(messages_table: Table, media_mapping: MediaMapping) -> set[str]:
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
