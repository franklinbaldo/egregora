"""Public interface for the LlamaIndex-based RAG utilities."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "CachedGeminiEmbedding",
    "IndexStats",
    "NewsletterRAG",
    "QueryGenerator",
    "RAGConfig",
]


def __getattr__(name: str) -> Any:
    """Lazily import RAG components to avoid circular imports."""

    if name == "RAGConfig":
        from .config import RAGConfig as exported

        return exported
    if name == "CachedGeminiEmbedding":
        from .embeddings import CachedGeminiEmbedding as exported

        return exported
    if name == "IndexStats" or name == "NewsletterRAG":
        module = import_module("egregora.rag.index")
        return getattr(module, name)
    if name == "QueryGenerator":
        from .query_gen import QueryGenerator as exported

        return exported

    raise AttributeError(name)
