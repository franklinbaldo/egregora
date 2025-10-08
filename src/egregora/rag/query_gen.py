"""Simple heuristics to generate search queries from transcripts."""

from __future__ import annotations

import copy
from dataclasses import dataclass

from ..config import RAGConfig
from .keyword_utils import KeywordExtractor


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
        self.config = copy.deepcopy(config) if config else RAGConfig()

    def _build_extractor(self) -> KeywordExtractor:
        return KeywordExtractor(
            max_keywords=self.config.max_keywords,
            stop_words=self.config.keyword_stop_words,
        )

    def generate(self, transcripts: str, *, model: str | None = None) -> QueryResult:
        """Return a :class:`QueryResult` derived from ``transcripts``."""

        cleaned = transcripts.strip()
        extractor = self._build_extractor()
        tokens = extractor.tokenize(cleaned)
        keywords = extractor.select_keywords(tokens)

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
