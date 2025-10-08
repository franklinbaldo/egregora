"""Utilities shared by the MCP server implementation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

try:  # pragma: no cover - optional dependency
    from llama_index.core.schema import NodeWithScore
except ModuleNotFoundError:  # pragma: no cover - allows running without llama-index
    NodeWithScore = Any  # type: ignore[assignment]


def _node_metadata(hit: NodeWithScore) -> dict:
    metadata = getattr(hit.node, "metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def format_search_hits(hits: Iterable[NodeWithScore]) -> str:
    """Return a Markdown snippet summarising ``hits``."""

    hits = list(hits)
    if not hits:
        return "Nenhum resultado encontrado nas posts arquivadas."

    lines: list[str] = ["# Trechos Relevantes de Posts Anteriores\n"]
    for index, hit in enumerate(hits, start=1):
        metadata = _node_metadata(hit)
        date_label = metadata.get("date") or metadata.get("file_name") or "????-??-??"
        heading = f"## Trecho {index} — {date_label}"
        if hit.score is not None:
            heading += f" (relevância: {hit.score:.0%})"
        lines.append(heading)
        section = metadata.get("section")
        if section:
            lines.append(f"*{section}*\n")
        content = hit.node.get_content()
        lines.append(content.strip())
        lines.append("\n---\n")

    return "\n".join(lines).rstrip()


def serialize_hits(hits: Iterable[NodeWithScore]) -> list[dict]:
    """Return ``hits`` converted to dictionaries for transport."""

    items: list[dict] = []
    for hit in hits:
        metadata = _node_metadata(hit)
        node_id = getattr(hit.node, "node_id", None) or getattr(hit.node, "id_", None)
        items.append(
            {
                "score": hit.score,
                "chunk": {
                    "id": node_id,
                    "path": metadata.get("file_path"),
                    "date": metadata.get("date"),
                    "section": metadata.get("section"),
                    "text": hit.node.get_content(),
                },
            }
        )
    return items


def format_post_listing(entries: Iterable[dict]) -> str:
    """Format a list of post metadata dictionaries as Markdown."""

    entries = list(entries)
    if not entries:
        return "Nenhuma post encontrada no histórico."

    lines = ["# Posts Disponíveis\n"]
    for entry in entries:
        lines.append(
            f"- **{entry.get('date', '????-??-??')}** ― {entry.get('path', '')} "
            f"({entry.get('size_kb', 0)} KB)"
        )

    return "\n".join(lines).rstrip()
