"""Keyword extraction helpers used by :mod:`egregora.rag`."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Collection, Iterable

_TOKEN_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


def _normalise(token: str) -> str:
    return token.lower()


def tokenize_text(text: str, *, stop_words: Collection[str] | None = None) -> list[str]:
    """Return a list of lowercase tokens extracted from *text*.

    Parameters
    ----------
    text:
        Raw text that should be tokenised.
    stop_words:
        Optional collection of tokens that should be filtered out after
        normalisation. Comparison is always case-insensitive.
    """

    if not text:
        return []

    blocked = {word.lower() for word in stop_words} if stop_words else set()
    tokens = []
    for match in _TOKEN_RE.finditer(text):
        token = _normalise(match.group(0))
        if blocked and token in blocked:
            continue
        tokens.append(token)
    return tokens


@dataclass(slots=True)
class KeywordExtractor:
    """Light-weight keyword extractor based on token frequency."""

    max_keywords: int
    stop_words: Collection[str] | None = None
    min_token_length: int = 3
    _blocked: set[str] = field(init=False, repr=False, default_factory=set)

    def __post_init__(self) -> None:
        if self.max_keywords < 1:
            raise ValueError("max_keywords must be at least 1")
        self._blocked = {word.lower() for word in self.stop_words} if self.stop_words else set()

    def tokenize(self, text: str) -> list[str]:
        return tokenize_text(text, stop_words=self._blocked)

    def select_keywords(self, tokens: Iterable[str]) -> list[str]:
        counter = Counter(
            token for token in tokens if token and len(token) >= self.min_token_length
        )
        keywords = [token for token, _ in counter.most_common(self.max_keywords)]
        if keywords:
            return keywords
        # Fallback: preserve insertion order of first distinct tokens
        seen: list[str] = []
        for token in tokens:
            if not token:
                continue
            if token in seen:
                continue
            seen.append(token)
            if len(seen) >= self.max_keywords:
                break
        return seen

    def extract(self, text: str) -> list[str]:
        return self.select_keywords(self.tokenize(text))


__all__ = ["KeywordExtractor", "tokenize_text"]
