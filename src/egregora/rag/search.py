"""DEPRECATED: Legacy TF-IDF search module.

The classic :mod:`egregora.rag.search` entrypoint has been superseded by the
unified retrieval pipeline. This module remains as a thin compatibility
layer for older integrations and will be removed in a future release.
"""

from __future__ import annotations

from typing import Any

import re

STOP_WORDS = frozenset(
    {
        "a",
        "as",
        "e",
        "o",
        "os",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "que",
        "para",
        "por",
        "com",
        "uma",
        "um",
        "na",
        "no",
        "nas",
        "nos",
        "em",
        "sobre",
        "and",
        "the",
        "to",
        "of",
        "in",
        "on",
    }
)

WORD_RE = re.compile(r"[\w'-]+", re.UNICODE)

__all__ = ["search", "tokenize", "STOP_WORDS"]


def tokenize(text: str, *, lowercase: bool = True) -> list[str]:
    """Return simple whitespace-and-punctuation tokenization for *text*."""

    if not text:
        return []

    tokens = WORD_RE.findall(text)
    if lowercase:
        tokens = [token.lower() for token in tokens]

    return [token for token in tokens if any(char.isalnum() for char in token)]


def search(*_: Any, **__: Any) -> None:
    """Placeholder search function that raises a helpful error.

    The historical TF-IDF implementation is no longer bundled with the
    project. Callers should migrate to :mod:`egregora.rag.index` for indexing
    and :mod:`egregora.rag.query_gen` for querying.
    """

    raise RuntimeError(
        "The TF-IDF search module has been removed. Use the new RAG pipeline "
        "under `egregora.rag` instead."
    )
