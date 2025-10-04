"""Public interface for RAG utilities with lazy imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .config import RAGConfig  # noqa: F401
    from .embeddings import CachedGeminiEmbedding  # noqa: F401
    from .index import IndexStats, NewsletterRAG  # noqa: F401
    from .query_gen import QueryGenerator  # noqa: F401


__all__ = [
    "CachedGeminiEmbedding",
    "IndexStats",
    "NewsletterRAG",
    "QueryGenerator",
    "RAGConfig",
]


def __getattr__(name: str):  # pragma: no cover
    if name == "RAGConfig":
        module = import_module("egregora.rag.config")
        return getattr(module, name)
    if name in {"CachedGeminiEmbedding"}:
        module = import_module("egregora.rag.embeddings")
        return getattr(module, name)
    if name in {"IndexStats", "NewsletterRAG"}:
        module = import_module("egregora.rag.index")
        return getattr(module, name)
    if name == "QueryGenerator":
        module = import_module("egregora.rag.query_gen")
        return getattr(module, name)
    raise AttributeError(name)
