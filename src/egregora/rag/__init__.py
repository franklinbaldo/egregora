"""RAG system for blog post and media indexing and retrieval."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "VectorStore",
    "query_similar_posts",
    "index_post",
    "index_media_enrichment",
    "index_all_media",
    "query_media",
]

_EXPORTS = {
    "VectorStore": (".store", "VectorStore"),
    "query_similar_posts": (".retriever", "query_similar_posts"),
    "index_post": (".retriever", "index_post"),
    "index_media_enrichment": (".retriever", "index_media_enrichment"),
    "index_all_media": (".retriever", "index_all_media"),
    "query_media": (".retriever", "query_media"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError:
        msg = f"module '{__name__}' has no attribute '{name}'"
        raise AttributeError(msg) from None
    module = import_module(module_name, package=__name__)
    return getattr(module, attr_name)


def __dir__() -> list[str]:
    return sorted(__all__)
