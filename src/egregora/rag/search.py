"""DEPRECATED: Legacy TF-IDF search utilities.

The classic :mod:`egregora.rag.search` entrypoint has been superseded by the
unified retrieval pipeline. This module remains as a thin compatibility
layer for older integrations and will be removed in a future release.
"""

from __future__ import annotations

import re
from typing import Iterable, Any

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

STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "as",
        "com",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "essa",
        "esse",
        "franklin",
        "grupo",
        "legal",
        "para",
        "sobre",
        "teste",
        "vamos",
    }
)

__all__ = ["search", "tokenize", "STOP_WORDS"]


def _normalise_stop_words(extra: Iterable[str] | None) -> frozenset[str]:
    if not extra:
        return STOP_WORDS
    return frozenset({*(word.lower().strip() for word in extra if word.strip()), *STOP_WORDS})


def tokenize(
    text: str,
    *,
    stop_words: Iterable[str] | None = None,
    min_token_length: int = 2,
) -> list[str]:
    """Return a list of unique lowercase tokens from ``text``.

    The behaviour mirrors the minimal keyword extraction used in previous
    integration tests: tokens are normalised to lowercase, short tokens are
    skipped and duplicates/stop words are removed.
    """

    if min_token_length < 1:
        raise ValueError("min_token_length must be positive")

    resolved_stop_words = _normalise_stop_words(stop_words)
    seen: set[str] = set()
    tokens: list[str] = []

    for candidate in _TOKEN_RE.findall(text.lower()):
        if len(candidate) < min_token_length:
            continue
        if candidate in resolved_stop_words or candidate in seen:
            continue
        tokens.append(candidate)
        seen.add(candidate)

    return tokens


def search(*_: Any, **__: Any) -> None:
    """Placeholder search function that raises a helpful error."""

    raise RuntimeError(
        "The TF-IDF search module has been removed. Use the new RAG pipeline "
        "under `egregora.rag` instead."
    )
