"""Simple heuristics to generate search queries from transcripts."""

from __future__ import annotations

import copy
from dataclasses import dataclass

from ..config import RAGConfig
from .keyword_utils import KeywordExtractor, KeywordProvider


@dataclass(slots=True)
class QueryResult:
    """Result returned by :class:`QueryGenerator`."""

    search_query: str
    keywords: list[str]
    main_topics: list[str]
    context: str


class QueryGenerator:
    """Create search queries derived from raw transcript text."""

    def __init__(
        self,
        config: RAGConfig | None = None,
        keyword_provider: KeywordProvider | None = None,
    ) -> None:
        self.config = copy.deepcopy(config) if config else RAGConfig()
        self._keyword_provider = keyword_provider

    def _build_extractor(
        self, keyword_provider: KeywordProvider | None
    ) -> KeywordExtractor:
        provider = keyword_provider or self._keyword_provider
        return KeywordExtractor(
            max_keywords=self.config.max_keywords,
            keyword_provider=provider,
        )

    def generate(
        self,
        transcripts: str,
        *,
        keyword_provider: KeywordProvider | None = None,
    ) -> QueryResult:
        """Return a :class:`QueryResult` derived from ``transcripts``."""

        cleaned = transcripts.strip()
        extractor = self._build_extractor(keyword_provider)
        keywords = extractor.extract(cleaned)

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
