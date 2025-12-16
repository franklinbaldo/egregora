"""RAG data models.

DEPRECATED: This module is a compatibility shim for V3 infrastructure.
"""

from __future__ import annotations

from egregora_v3.core.search import RAGHit, RAGQueryRequest, RAGQueryResponse

__all__ = [
    "RAGHit",
    "RAGQueryRequest",
    "RAGQueryResponse",
]
