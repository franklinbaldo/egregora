"""Simple heuristics to generate search queries from transcripts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from ..config import RAGConfig
from .search import STOP_WORDS, tokenize


@dataclass(slots=True)
class QueryResult:
    """Result returned by :class:`QueryGenerator`."""

    search_query: str
    keywords: list[str]
    main_topics: list[str]
    context: str


class QueryGenerator:
    """Create search queries derived from raw transcript text."""

    def __init__(self, config: RAGConfig | None = None) -> None:
        self.config = config.clone() if config else RAGConfig()

    def _select_keywords(self, tokens: Iterable[str]) -> list[str]:
        counter = Counter(
            token for token in tokens if token and token not in STOP_WORDS and len(token) > 2
        )
        most_common = [token for token, _ in counter.most_common(self.config.max_keywords)]
        return most_common

    def generate(self, transcripts: str, *, model: str | None = None) -> QueryResult:
        """Return a :class:`QueryResult` derived from ``transcripts``."""

        cleaned = transcripts.strip()
        tokens = tokenize(cleaned)
        keywords = self._select_keywords(tokens)
        if not keywords:
            keywords = list({token for token in tokens if token})[:3]

        main_topics = keywords[:3]
        search_query = ", ".join(keywords[:6]) if keywords else cleaned[:120]

        max_context = max(200, self.config.max_context_chars)
        context = cleaned[:max_context]

        return QueryResult(
            search_query=search_query,
            keywords=keywords,
            main_topics=main_topics,
            context=context,
        )
