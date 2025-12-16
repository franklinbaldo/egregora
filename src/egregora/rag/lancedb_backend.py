"""LanceDB-based RAG backend.

Provides vector storage and similarity search using LanceDB with native Python.
Uses Arrow for zero-copy data transfer (no Pandas dependency).

DEPRECATED: This module is a compatibility shim for V3 infrastructure.
"""

from __future__ import annotations

# Re-export V3 implementation as V2 backend
from egregora_v3.infra.vector.lancedb import EmbedFn
from egregora_v3.infra.vector.lancedb import LanceDBVectorStore as LanceDBRAGBackend

__all__ = ["EmbedFn", "LanceDBRAGBackend"]
