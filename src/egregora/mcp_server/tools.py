"""Utilities shared by the MCP server implementation."""

from __future__ import annotations

from typing import Iterable, List

from ..rag.core import SearchHit


def format_search_hits(hits: Iterable[SearchHit]) -> str:
    """Return a Markdown snippet summarising ``hits``."""

    hits = list(hits)
    if not hits:
        return "Nenhum resultado encontrado nas newsletters arquivadas."

    lines: list[str] = ["# Trechos Relevantes de Newsletters Anteriores\n"]
    for index, hit in enumerate(hits, start=1):
        chunk = hit.chunk
        heading = f"## Trecho {index} — {chunk.newsletter_date.isoformat()}"
        heading += f" (relevância: {hit.score:.0%})"
        lines.append(heading)
        if chunk.section_title:
            lines.append(f"*{chunk.section_title}*\n")
        lines.append(chunk.text.strip())
        lines.append("\n---\n")

    return "\n".join(lines).rstrip()


def serialize_hits(hits: Iterable[SearchHit]) -> List[dict]:
    """Return ``hits`` converted to dictionaries for transport."""

    items: list[dict] = []
    for hit in hits:
        chunk = hit.chunk
        items.append(
            {
                "score": hit.score,
                "chunk": {
                    "id": chunk.chunk_id,
                    "path": str(chunk.newsletter_path),
                    "date": chunk.newsletter_date.isoformat(),
                    "section": chunk.section_title,
                    "text": chunk.text,
                },
            }
        )
    return items


def format_newsletter_listing(entries: Iterable[dict]) -> str:
    """Format a list of newsletter metadata dictionaries as Markdown."""

    entries = list(entries)
    if not entries:
        return "Nenhuma newsletter encontrada no histórico."

    lines = ["# Newsletters Disponíveis\n"]
    for entry in entries:
        lines.append(
            f"- **{entry.get('date', '????-??-??')}** ― {entry.get('path', '')} "
            f"({entry.get('size_kb', 0)} KB)"
        )

    return "\n".join(lines).rstrip()
