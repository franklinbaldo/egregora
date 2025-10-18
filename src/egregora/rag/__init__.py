"""Public interface for the simplified RAG utilities."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .config import RAGConfig  # noqa: F401
    from .duckdb_simple import DuckDBSimpleConfig, DuckDBSimpleRAG  # noqa: F401

__all__ = ["DuckDBSimpleConfig", "DuckDBSimpleRAG", "RAGConfig"]


def __getattr__(name: str):  # pragma: no cover
    if name == "RAGConfig":
        module = import_module("egregora.rag.config")
        return getattr(module, name)
    if name in {"DuckDBSimpleRAG", "DuckDBSimpleConfig"}:
        module = import_module("egregora.rag.duckdb_simple")
        return getattr(module, name)
    raise AttributeError(name)
